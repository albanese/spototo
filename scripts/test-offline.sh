#!/usr/bin/env bash
# Existing local images only; no credentials, runtime data, installs or network.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
docker_bin="${DOCKER_BIN:-docker}"
if ! command -v "$docker_bin" >/dev/null 2>&1; then
  docker_bin=/Applications/Docker.app/Contents/Resources/bin/docker
fi
common=(--rm --pull never --network none --cpus 1 --memory 512m
  --tmpfs /scratch:rw,nosuid,size=64m
  -e TMPDIR=/scratch -e PYTHONDONTWRITEBYTECODE=1
  -v "$repo_dir/tests:/feature/tests:ro" -w /feature)

"$docker_bin" run "${common[@]}" \
  -v "$repo_dir/spotify_sync:/feature/spotify_sync:ro" \
  -e PYTHONPATH=/feature:/feature/spotify_sync \
  "${SPOTOTO_SYNC_TEST_IMAGE:-spototo-spototo-sync}" python -c '
import unittest
names = ["test_spotify_sync.py", "test_spotify_download.py", "test_source_matching.py", "test_audio_duration_guard.py", "test_blocked_tracks.py", "test_sync_runtime.py"]
suite = unittest.TestSuite(unittest.defaultTestLoader.discover("tests", pattern=name) for name in names)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())'

"$docker_bin" run "${common[@]}" \
  -v "$repo_dir/src:/feature/src:ro" \
  -v "$repo_dir/spotify_sync/source_matching.py:/matching/source_matching.py:ro" \
  -e PYTHONPATH=/feature/src:/matching \
  "${SPOTOTO_MAIN_TEST_IMAGE:-spototo-spototo}" python -c '
import unittest
names = ["test_icon_library.py", "test_icon_resolver.py", "test_backfill_icons.py", "test_yoto_audio_guard.py", "test_fork_integration.py"]
suite = unittest.TestSuite(unittest.defaultTestLoader.discover("tests", pattern=name) for name in names)
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())'
