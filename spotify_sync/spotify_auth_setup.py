#!/usr/bin/env python3
"""
One-time Spotify user-OAuth setup. Run this on a machine WITH a browser (the
Beelink is headless), then copy the resulting token cache to the box.

The pipeline needs to *list your playlists* to find the ones named `Yoto-*`,
which requires user-level auth (the older app-level client-credentials flow
can only fetch a single public playlist by ID). This performs the standard
Authorization Code flow via spotipy and writes the refresh token to
data/spotify_token.json.

    pip install -r requirements.txt
    python spotify_auth_setup.py
    # browser opens -> approve -> data/spotify_token.json is written
    # then: scp data/spotify_token.json yo@<box>:/opt/stack/yoto-automation/data/

Prereq: add the redirect URI (default http://127.0.0.1:8888/callback) to your
app at https://developer.spotify.com/dashboard before running.
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheFileHandler

SCOPE = "playlist-read-private"
REDIRECT_URI = os.environ.get("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
CACHE_PATH = os.environ.get(
    "SPOTIFY_TOKEN_CACHE", str(REPO_ROOT / "data" / "spotify_token.json")
)


def main() -> int:
    client_id = os.environ.get("SPOTIPY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIPY_CLIENT_SECRET", "")
    if not (client_id and client_secret):
        print(
            "Set SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET (in .env or env).",
            file=sys.stderr,
        )
        return 1

    Path(CACHE_PATH).parent.mkdir(parents=True, exist_ok=True)
    auth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_handler=CacheFileHandler(cache_path=CACHE_PATH),
        open_browser=True,
    )

    print(f"Redirect URI: {REDIRECT_URI}")
    print("Opening browser for Spotify login...")
    # Forces the interactive flow and writes the refresh token to the cache.
    auth.get_access_token(as_dict=False)

    print(f"\nSuccess. Token cached at {CACHE_PATH}")
    print("Copy it to the box:")
    print(f"  scp {CACHE_PATH} yo@<box>:/opt/stack/yoto-automation/data/spotify_token.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
