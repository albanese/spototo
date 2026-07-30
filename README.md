# 🎵 Spototo

Turn Spotify playlists into self-updating [Yoto](https://yoto.io) Make-Your-Own
cards — complete with custom AI-generated pixel art icons for every song.

Name a playlist `Yoto-Bedtime`, add songs to it, and Spototo automatically:

- downloads new tracks as they're added
- generates a 16×16 pixel-art icon for each one (with a little AI help — see below)
- appends it as a chapter on a Yoto card called **"Bedtime"** (created for you on the first track)
- removes the chapter again if you delete the song from the playlist

Name another playlist `Yoto-Dinosaurs` and you get a second, independent card.
No per-playlist configuration — just the naming convention.

> ⚠️ **Audio comes from YouTube search results via `yt-dlp`**, not licensed
> Spotify streams — there's no way around this without label deals. It's a
> personal/family tool, not a distribution service. See [Legal](#legal--scope) below.

## How it works

```
Spotify (Yoto-* playlists)
        │  poll every few min, user OAuth
        ▼
spotify_sync/   (host, systemd timer)
        │  yt-dlp download → data/watch/<card name>/
        ▼
src/            (Docker container)
        │  title → LLM subject → 8 candidate icons → vision judge picks best
        │  audio upload + transcode
        ▼
Yoto API  →  MYO card chapter
```

### Icon generation, the part that took the most tuning

Feeding a raw song title straight to an image model produces mush — the two
things that actually work:

1. **Distill the title to one concrete subject first.** A small LLM (Llama 3
   8B) turns *"Candy Cane Crush!"* into *"candy cane"*, *"Gorilla Smash!"*
   into *"gorilla"*. The image model draws a clear object beautifully; it
   draws a compound song title as noise.
2. **Generate several candidates and judge them.** Any single generation is a
   coin flip — some come out clean, some come out mush. Spototo generates
   several candidates natively at 16×16 (the Yoto screen's real resolution;
   generating bigger and downscaling just moves the mush to a different step)
   and a vision model picks whichever one most clearly reads as the subject.

| ![Baby Shark](showcase/Baby%20Shark.png) | ![Gorilla Smash](showcase/Gorilla%20Smash.png) | ![Chug Like a Train](showcase/Chug%20Like%20a%20Train.png) |
|:---:|:---:|:---:|
| ![Dinosaur Dance](showcase/Dinosaur%20Dance.png) | ![Twinkle Twinkle](showcase/Twinkle%20Twinkle.png) | ![Robot Dance](showcase/Robot%20Dance.png) |
| ![Zoom to the Moon](showcase/Zoom%20to%20the%20Moon.png) | ![Baby Beluga](showcase/Baby%20Beluga.png) | ![Candy Cane](showcase/Candy%20Cane.png) |

Results are hit-and-miss — concrete nouns (shark, gorilla, train) come out
clean almost every time; abstract titles are more of a gamble — but usually
good enough that a kid can tell chapters apart by the icon.

**Cost is a dial, not fixed.** Each candidate icon is about $0.015 on
Replicate; the LLM subject-extraction and the judging pass are effectively
free by comparison. So cost per song ≈ `ICON_CANDIDATES × $0.015`:

| `ICON_CANDIDATES` | ~cost/song | quality |
|---|---|---|
| 8 (default) | ~$0.12 | most reliable |
| 4 | ~$0.06 | reliably good for concrete subjects |
| 1 | ~$0.015 | single-shot, no best-of |

Set it in `.env` — no rebuild needed, just a container restart.

### Deletion is safety-scoped

Delete a song from the playlist and its chapter is removed from the Yoto
card too — but **only** chapters Spototo itself created and tracked. It will
never touch or guess about a chapter added any other way, even on a card you
also edit by hand.

## Components

| Path | What it does | Runs as |
|---|---|---|
| `spotify_sync/` | Discovers `Yoto-*` playlists, downloads new tracks, tracks deletions | Docker (`spototo-sync`) or host systemd timer |
| `src/` | Watches the download folder, generates icons, talks to the Yoto API | Docker (`spototo`) |
| `spotify_sync/spotify_auth_setup.py` | One-time Spotify OAuth login (needs a browser) | run manually, once |
| `auth_setup.py` | One-time Yoto OAuth login (needs a browser) | run manually, once |

Everything runs in Docker — no systemd, no Python venvs, no `apt install`.
It's been developed and run in production on Linux; it *should* work the
same via Docker Desktop on Windows and macOS since nothing in the containers
is Linux-specific, but that hasn't been verified firsthand yet. If you try it
on Windows/macOS, an issue report either way (works / doesn't) is welcome.

## Setup

```bash
cp .env.example .env
nano .env   # YOTO_CLIENT_ID, REPLICATE_API_TOKEN, SPOTIPY_CLIENT_ID/SECRET

# 1. Yoto login (run on a machine with a browser — the server itself can be headless)
python auth_setup.py --client-id YOUR_YOTO_CLIENT_ID
scp data/state.json you@server:/path/to/spototo/data/

# 2. Spotify login (needs playlist-read-private to list your playlists)
python spotify_sync/spotify_auth_setup.py
scp data/spotify_token.json you@server:/path/to/spototo/data/

# 3. bring up both services
docker compose up --build -d
docker compose logs -f
```

Then rename or create a Spotify playlist as `Yoto-<name>` and wait for the
next sync (every 5 min by default — see `SPOTIFY_POLL_SECONDS` in `.env.example`).

Steps 1 and 2 need a one-time browser login, so run them on your laptop, then
copy the two resulting files over — the server running the containers can be
completely headless.

<details>
<summary>Prefer a host-level systemd timer instead of the spototo-sync container? (Linux only)</summary>

⚠️ Pick **one** — the Docker `spototo-sync` service and this systemd timer both
poll and download independently. Running both against the same `data/`
directory means duplicate, racing downloads. If you use this path, don't
also start the `spototo-sync` container (`docker compose up` without listing
it by name brings up every service, so start `spototo` explicitly instead).

```bash
docker compose up --build -d spototo   # just this one service

python3 -m venv spotify_sync/.venv
source spotify_sync/.venv/bin/activate
pip install -r spotify_sync/requirements.txt

sudo cp systemd/spotify-sync.* /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now spotify-sync.timer
```

Requires `ffmpeg` and Node.js on the host (used by `yt-dlp`). See `spotify_sync/README.md`.
</details>

## Requirements

- A [Yoto](https://yoto.dev) developer account (public client)
- A [Replicate](https://replicate.com) API token (LLM + image generation + vision judge)
- A Spotify Developer app (`playlist-read-private` scope)
- Docker (Docker Desktop on Windows/Mac, Docker Engine on Linux)

## Legal / scope

This is a **personal, single-user tool** — one Spotify account, one Yoto
account, run on your own hardware. It is **not** designed to be hosted as a
multi-tenant service on other people's behalf; doing so raises real copyright
and platform-ToS exposure that a personal self-hosted instance doesn't
(Spotify's Developer Terms explicitly prohibit using their API to enable
downloading of audio, and centralizing the download/redistribution step for
other users is a materially different legal posture than each person running
their own instance — see e.g. *A&M Records v. Napster*, which established
that "we don't charge for it" doesn't shield an operator of centralized
infrastructure that facilitates unlicensed copying at scale). Run your own
instance under your own accounts.

## Known limitations

- Single Spotify account, single Yoto account — see Legal above.
- Audio quality is bounded by whatever YouTube has for a given track.
- No automated tests yet.

## License

[MIT](LICENSE)
