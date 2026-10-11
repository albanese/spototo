#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${SPOTOTO_ENV_FILE:-$repo_dir/.env}"

if [[ ! -f "$env_file" ]]; then
  printf 'Missing environment file: %s\n' "$env_file" >&2
  exit 1
fi

read -r -p 'Spotify Client ID: ' spotify_client_id
read -r -s -p 'Spotify Client Secret: ' spotify_client_secret
printf '\n'

if [[ -z "$spotify_client_id" || -z "$spotify_client_secret" ]]; then
  printf 'Both Spotify values are required; .env was not changed.\n' >&2
  exit 1
fi

printf '%s\0%s\0' "$spotify_client_id" "$spotify_client_secret" |
  SPOTOTO_ENV_FILE="$env_file" python3 -c '
from pathlib import Path
import os
import re
import sys
import tempfile

path = Path(os.environ["SPOTOTO_ENV_FILE"])
client_id, client_secret, _ = sys.stdin.buffer.read().split(b"\0")
values = {
    "SPOTIPY_CLIENT_ID": client_id.decode(),
    "SPOTIPY_CLIENT_SECRET": client_secret.decode(),
}
text = path.read_text()
for key, value in values.items():
    text, count = re.subn(rf"(?m)^{key}=.*$", f"{key}={value}", text, count=1)
    if count != 1:
        raise SystemExit(f"Missing {key}= entry in {path}; no change made.")

with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, prefix=".env.", delete=False) as output:
    output.write(text)
    temp_path = Path(output.name)
os.chmod(temp_path, 0o600)
temp_path.replace(path)
'

unset spotify_client_id spotify_client_secret
printf 'Spotify credentials saved to %s\n' "$env_file"
