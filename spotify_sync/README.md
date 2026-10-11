# spotify-sync

Discovers every Spotify playlist named `Yoto-<name>` and downloads new tracks
as MP3s into `../data/watch/<name>/`, where the Yoto pixel pipeline container
picks them up and turns them into chapters on a matching card.

## Run via Docker (recommended — works on Windows/Mac/Linux)

See the root `docker-compose.yml` — this runs as the `spototo-sync` service,
polling on a plain sleep loop (`loop.py`) rather than cron/systemd.

```bash
docker compose up --build -d spototo-sync
```

## Run via a host systemd timer instead (Linux only)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
```

Requires `ffmpeg` and Node.js on the host (`yt-dlp` needs a JS runtime to
solve YouTube's extraction challenge — without it, downloads silently fail
with "This video is not available").

Edit `../systemd/spotify-sync.service` first — it has placeholder paths/user
(`User=`, `WorkingDirectory=`, `EnvironmentFile=`, `ExecStart=`) that need to
match your actual username and where you cloned this repo.

```bash
sudo cp ../systemd/spotify-sync.* /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now spotify-sync.timer
```

## Config

Reads from `../.env` (or the environment): `SPOTIPY_CLIENT_ID`,
`SPOTIPY_CLIENT_SECRET`, `SPOTIFY_PLAYLIST_PREFIX` (default `Yoto-`),
`SPOTIPY_REDIRECT_URI`. Needs `data/spotify_token.json` — see
`spotify_auth_setup.py` / the main README's Setup section.

## Run once manually

```bash
source .venv/bin/activate   # if using the venv path
python sync.py
```

## Compatibility checks

Playlist parsing accepts both Spotify's current `item` field and legacy
`track` field, skips episodes and unavailable items, and follows pagination.
Spotify's `duration_ms` is retained in `.spotify_tracks.json` for validation
before download publication and again before Yoto upload.

The downloader uses `yt-dlp` directly: search multiple results (official audio,
Lyrics, then a broader artist/title query), normalize articles and ampersands,
require song and primary-artist matching, reject compilations and unrequested
live/cover/remix/effects/tutorial versions, and select a source within **10 seconds or 10%** of the Spotify
length (whichever is larger). The full extracted source and finished MP3 must
also pass that bound. Missing duration or no acceptable source means the
track is skipped for retry; never trim a compilation or take the first hit.
Chosen-source evidence is retained as `.<track-id>.source.json` in the watch
folder. MP3s use 128 kbps, sufficient for this spoken/song-content workflow.

Spotify-sourced files already on a card replace their recorded chapter key
in place after a verified replacement upload, preserving other chapters.
Recovery copies under `data/recovery/` are outside the watcher tree and ignored
by Git because snapshots may contain authorization state.

Explicitly rejected sources can be held in a playlist's `blocked` map in
`data/spotify_state.json` (`track ID -> title, reason, blocked_at`). Blocked IDs
are never downloaded, even after removing/re-adding them on Spotify. The
Spotify playlist itself is unchanged; clearing a block requires an explicit
review of a suitable original recording.

Run sync regression tests from the repository root (with sync dependencies
installed); upload-boundary tests additionally require the main image's
requirements:

```bash
python -m unittest discover -s tests -v
```

After changing sync code, rebuild and recreate `spototo-sync`; a restart alone
continues using the old code embedded in the image.

## Notes

- Audio comes from YouTube (via `yt-dlp`), not Spotify directly — Spotify's
  API doesn't serve full-length audio. Occasional wrong version (live, remix,
  cover).
- Deleting a song from the playlist removes its chapter from the Yoto card
  too, but only chapters this tool created — see the main README.
- State lives in `../data/spotify_state.json`, per playlist. Deleting a
  track's entry there forces a re-download next run.
