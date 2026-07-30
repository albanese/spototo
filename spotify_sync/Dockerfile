FROM python:3.11-slim

# ffmpeg: audio conversion (yt-dlp's postprocessing).
# nodejs: yt-dlp needs a JS runtime to solve YouTube's extraction challenge --
# without it, downloads silently fail with "This video is not available".
# Debian's own `nodejs` package is too old for yt-dlp's solver (tested: v20 is
# rejected as "unsupported"; NodeSource's current LTS works), hence NodeSource.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY spotify_sync/requirements.txt spotify_sync/requirements.txt
RUN pip install --no-cache-dir -r spotify_sync/requirements.txt

COPY spotify_sync/ spotify_sync/

ENV PYTHONUNBUFFERED=1

CMD ["python", "spotify_sync/loop.py"]
