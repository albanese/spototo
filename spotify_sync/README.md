# spotify-sync

Polls a Spotify playlist and downloads new tracks as MP3s into `../data/watch/`,
where the Yoto pixel pipeline container picks them up.

## Setup

```bash
cd ~/yoto-automation
python3 -m venv spotify_sync/.venv
source spotify_sync/.venv/bin/activate
pip install -r spotify_sync/requirements.txt
deactivate
```

Requires `ffmpeg` on PATH (used by `spotify_dl`'s YouTube-audio backend).

## Config

Reads from `../.env` (or the environment): `SPOTIPY_CLIENT_ID`,
`SPOTIPY_CLIENT_SECRET`, `SPOTIFY_PLAYLIST_URL`. Optional: `WATCH_DIR`,
`SPOTIFY_STATE_FILE`.

## Run once manually

```bash
source spotify_sync/.venv/bin/activate
python spotify_sync/sync.py
```

## Run on a schedule

See `../systemd/spotify-sync.service` and `../systemd/spotify-sync.timer`,
installed per `../BEELINK_AGENT_PLAN.md` Phase 4d.

## Notes

- Audio comes from YouTube (via `spotify_dl`), not Spotify directly — Spotify's
  API doesn't serve full-length audio. Occasional wrong version (live, remix,
  cover).
- `SPOTIFY_PLAYLIST_URL` must be a **public** playlist: this script uses the
  client-credentials OAuth flow, which can't see private playlists. If you
  need a private playlist, swap in a user-authorized `spotipy.SpotifyOAuth`
  flow instead.
- State lives in `../data/spotify_state.json` — delete a track's entry there
  to force a re-download.
