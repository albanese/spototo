"""
Container entrypoint: runs sync.main() on a fixed interval.

A plain sleep loop rather than cron/systemd inside the container -- "run
this every N minutes" doesn't need an init system, just a loop. This is
what lets spotify-sync run identically on any OS with Docker (Windows/Mac/
Linux via Docker Desktop) instead of depending on a Linux-only systemd timer.
"""
import logging
import os
import time

from sync import main

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("spotify-sync-loop")

POLL_SECONDS = int(os.environ.get("SPOTIFY_POLL_SECONDS", "300"))

if __name__ == "__main__":
    log.info(f"Starting spotify-sync loop, polling every {POLL_SECONDS}s")
    while True:
        try:
            main()
        except Exception:
            log.exception("sync run failed; will retry next interval")
        time.sleep(POLL_SECONDS)
