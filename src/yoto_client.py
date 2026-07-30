"""
Minimal Yoto API client: OAuth token refresh, MYO card content, audio
transcode upload, and 16x16 icon upload.

Based on public docs at yoto.dev (Content API, media upload, icons). The
exact response shapes for GET/POST /content are not fully pinned down in the
public docs, so parsing there is guarded — see extract_existing_chapters()
and _extract_card_id(). If Yoto changes/clarifies the shape, fix it there.
"""
import time

import requests


class YotoClient:
    def __init__(self, config, state):
        self.config = config
        self.state = state

    # ---- auth -----------------------------------------------------

    def _refresh(self):
        refresh_token = self.state.get("yoto_refresh_token")
        if not refresh_token:
            raise RuntimeError(
                "No refresh token in state file. Run auth_setup.py on a "
                "machine with a browser and copy data/state.json here."
            )
        resp = requests.post(
            self.config.YOTO_AUTH_BASE + "/oauth/token",
            json={
                "grant_type": "refresh_token",
                "client_id": self.config.YOTO_CLIENT_ID,
                "refresh_token": refresh_token,
            },
            timeout=30,
        )
        resp.raise_for_status()
        tokens = resp.json()
        self.state.update(
            yoto_access_token=tokens["access_token"],
            yoto_access_token_expires_at=time.time() + float(tokens.get("expires_in", 3600)),
            # Yoto rotates refresh tokens on use; fall back to the old one if absent.
            yoto_refresh_token=tokens.get("refresh_token", refresh_token),
        )

    def _access_token(self):
        expires_at = self.state.get("yoto_access_token_expires_at", 0)
        if not self.state.get("yoto_access_token") or time.time() > expires_at - 60:
            self._refresh()
        return self.state.get("yoto_access_token")

    def _headers(self):
        return {"Authorization": f"Bearer {self._access_token()}"}

    # ---- low-level HTTP --------------------------------------------

    def _get(self, path, params=None):
        r = requests.get(
            self.config.YOTO_API_BASE + path,
            headers=self._headers(),
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def _post_json(self, path, payload):
        r = requests.post(
            self.config.YOTO_API_BASE + path,
            headers={**self._headers(), "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def _post_binary(self, path, params, data, content_type):
        r = requests.post(
            self.config.YOTO_API_BASE + path,
            headers={**self._headers(), "Content-Type": content_type},
            params=params,
            data=data,
            timeout=60,
        )
        r.raise_for_status()
        return r.json()

    # ---- content (MYO card) -----------------------------------------

    def get_content(self, card_id):
        """Returns the raw card JSON, or None if the card doesn't exist yet."""
        try:
            return self._get(f"/content/{card_id}")
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                return None
            raise

    @staticmethod
    def extract_existing_chapters(card_json):
        try:
            content = card_json["card"]["content"] if "card" in card_json else card_json["content"]
            chapters = content.get("chapters", [])
            if not isinstance(chapters, list):
                raise TypeError(f"chapters is not a list: {type(chapters)}")
            return chapters
        except (KeyError, TypeError) as exc:
            raise ValueError(
                "Couldn't parse existing chapters from GET /content response; "
                "inspect the raw JSON and fix extract_existing_chapters() in "
                "src/yoto_client.py."
            ) from exc

    @staticmethod
    def _extract_card_id(resp_json):
        try:
            if "card" in resp_json:
                return resp_json["card"]["cardId"]
            return resp_json["cardId"]
        except (KeyError, TypeError) as exc:
            raise ValueError(
                "Couldn't parse cardId from POST /content response; inspect "
                "the raw JSON and fix _extract_card_id() in src/yoto_client.py."
            ) from exc

    def get_card_and_chapters(self, card_id):
        """Returns (card_id, existing_chapters). card_id is None if no card yet."""
        if not card_id:
            return None, []
        card = self.get_content(card_id)
        if card is None:
            return None, []
        # Yoto returns 200 with deleted=true rather than 404 for a card
        # that's been soft-deleted server-side; POSTing to it 400s with
        # "Deleted card cannot be restored", so treat it like no card yet.
        card_obj = card.get("card", card)
        if card_obj.get("deleted"):
            return None, []
        return card_id, self.extract_existing_chapters(card)

    def save_chapters(self, card_id, chapters, title=None):
        payload = {
            "title": title or self.config.YOTO_CARD_TITLE,
            "content": {"chapters": chapters},
        }
        if card_id:
            payload["cardId"] = card_id
        resp = self._post_json("/content", payload)
        new_card_id = self._extract_card_id(resp)
        self.state.set("yoto_card_id", new_card_id)
        return new_card_id

    # ---- audio upload (presigned URL -> PUT -> poll transcode) --------

    def _request_audio_upload_url(self):
        resp = self._get("/media/transcode/audio/uploadUrl")
        try:
            upload = resp["upload"]
            return upload["uploadUrl"], upload["uploadId"]
        except (KeyError, TypeError) as exc:
            raise ValueError(
                "Couldn't parse upload URL from GET /media/transcode/audio/uploadUrl"
            ) from exc

    def _put_audio_file(self, upload_url, file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        r = requests.put(
            upload_url, data=data, headers={"Content-Type": "audio/mpeg"}, timeout=120
        )
        r.raise_for_status()

    def _poll_transcode(self, upload_id, timeout=180, interval=3):
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = self._get(
                f"/media/upload/{upload_id}/transcoded", params={"loudnorm": "false"}
            )
            transcode = resp.get("transcode", {})
            if transcode.get("transcodedSha256"):
                return transcode
            time.sleep(interval)
        raise TimeoutError(
            f"Audio transcode did not complete within {timeout}s for upload {upload_id}"
        )

    def upload_audio(self, mp3_path):
        upload_url, upload_id = self._request_audio_upload_url()
        self._put_audio_file(upload_url, mp3_path)
        transcode = self._poll_transcode(upload_id)
        info = transcode.get("transcodedInfo", {})
        sha256 = transcode["transcodedSha256"]
        return {
            "sha256": sha256,
            "trackUrl": f"yoto:#{sha256}",
            "duration": info.get("duration"),
            "fileSize": info.get("fileSize"),
            "channels": info.get("channels", "stereo"),
            "format": info.get("format", "mp3"),
        }

    # ---- icon upload / library ------------------------------------------

    def upload_icon(self, png_bytes, filename="icon.png"):
        resp = self._post_binary(
            "/media/displayIcons/user/me/upload",
            params={"autoConvert": "true", "filename": filename},
            data=png_bytes,
            content_type="image/png",
        )
        try:
            return resp["displayIcon"]["mediaId"]
        except (KeyError, TypeError) as exc:
            raise ValueError(
                "Couldn't parse mediaId from icon upload response; inspect "
                "the raw JSON and fix upload_icon() in src/yoto_client.py."
            ) from exc

    def list_library_icons(self):
        """Yoto's official icon library (title + tags per icon) -- used by
        icon_library.py for non-AI keyword matching."""
        resp = self._get("/media/displayIcons/user/yoto")
        try:
            return resp["displayIcons"]
        except (KeyError, TypeError) as exc:
            raise ValueError(
                "Couldn't parse displayIcons from GET /media/displayIcons/user/yoto"
            ) from exc

    # ---- chapter building --------------------------------------------

    @staticmethod
    def build_chapter(chapter_num, title, artist, audio_info, icon_media_id=None):
        """icon_media_id may be None (Config.ICON_SOURCE = "none", or no
        library match found) -- the chapter is then built without a custom
        icon, and Yoto shows its own default instead."""
        display = {"display": {"icon16x16": f"yoto:#{icon_media_id}"}} if icon_media_id else {}
        chapter_title = f"{title} — {artist}" if artist else title
        track = {
            "key": "01",
            "title": title,
            "trackUrl": audio_info["trackUrl"],
            "format": audio_info.get("format", "mp3"),
            "type": "audio",
            "duration": audio_info.get("duration"),
            "fileSize": audio_info.get("fileSize"),
            "channels": audio_info.get("channels", "stereo"),
            **display,
        }
        return {
            "key": f"{chapter_num:02d}",
            "title": chapter_title,
            "tracks": [track],
            **display,
        }
