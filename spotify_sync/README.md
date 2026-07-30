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

## Notes

- Audio comes from YouTube (via `yt-dlp`), not Spotify directly — Spotify's
  API doesn't serve full-length audio. Occasional wrong version (live, remix,
  cover).
- Deleting a song from the playlist removes its chapter from the Yoto card
  too, but only chapters this tool created — see the main README.
- State lives in `../data/spotify_state.json`, per playlist. Deleting a
  track's entry there forces a re-download next run.
