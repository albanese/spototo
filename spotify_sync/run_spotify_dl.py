#!/usr/bin/env python3
"""Canonical direct yt-dlp downloader; no Spotify API calls or CLI shims."""
import argparse
import json
from pathlib import Path
import sys

import yt_dlp
from mutagen.id3 import ID3, ID3NoHeaderError, TIT2, TPE1

if __package__:
    from .source_matching import duration_matches, primary_artist, select_candidate, validate_track
else:
    from source_matching import duration_matches, primary_artist, select_candidate, validate_track


def tag_audio(path, track):
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()
    tags.add(TIT2(encoding=3, text=track['title']))
    tags.add(TPE1(encoding=3, text=track['artist']))
    tags.save(path)


def download_track(track, output):
    expected = validate_track(track)
    output = Path(output)
    if not output.is_absolute():
        raise ValueError('--output must be an absolute directory')
    common = {'js_runtimes': {'node': {}}, 'remote_components': ['ejs:github'], 'noplaylist': True,
              'quiet': True, 'socket_timeout': 20, 'retries': 2}
    candidate = None
    with yt_dlp.YoutubeDL(dict(common, extract_flat='in_playlist', skip_download=True)) as search:
        for suffix in ('official audio', 'Lyrics', ''):
            count = 30 if not suffix else 15
            query = f"ytsearch{count}:{primary_artist(track)} {track['title']} {suffix}".strip()
            results = search.extract_info(query, download=False)
            try:
                candidate = select_candidate((results or {}).get('entries', []), track)
            except ValueError:
                continue
            break
    if candidate is None:
        raise ValueError('No eligible YouTube source after official audio, Lyrics and title searches')

    def match_filter(info, *, incomplete=False):
        # Fail closed even at preliminary filtering; flat search duration is not trusted.
        if not duration_matches(info.get('duration'), expected):
            return 'Source duration missing or outside Spotify tolerance'
        try:
            select_candidate([info], track)
        except ValueError as exc:
            return str(exc)
        return None

    output.mkdir(parents=True, exist_ok=True)
    options = dict(common, format='bestaudio/best', match_filter=match_filter,
                   outtmpl=str(output / '%(id)s.%(ext)s'),
                   postprocessors=[{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '128'}])
    url = f"https://www.youtube.com/watch?v={candidate['id']}"
    with yt_dlp.YoutubeDL(options) as downloader:
        source = downloader.extract_info(url, download=True)
    if not isinstance(source, dict) or match_filter(source) is not None:
        raise ValueError('Full YouTube extraction failed source validation')
    if source.get('id') != candidate['id']:
        raise ValueError('Downloaded source ID differs from selected video')
    audio = output / f"{candidate['id']}.mp3"
    if not audio.is_file() or audio.stat().st_size == 0:
        raise ValueError('Downloader did not produce a nonempty MP3')
    tag_audio(audio, track)
    provenance = {key: source.get(key) for key in ('id', 'title', 'duration', 'uploader')}
    provenance['expected_duration'] = expected
    (output / 'source.json').write_text(json.dumps(provenance, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    return audio


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--track-json', required=True, help='JSON with id, title, artist, duration_ms')
    parser.add_argument('--output', required=True, help='Absolute output directory')
    args = parser.parse_args(argv)
    try:
        audio = download_track(json.loads(args.track_json), args.output)
    except (ValueError, OSError, yt_dlp.utils.DownloadError) as exc:
        print(f'Download failed: {exc}', file=sys.stderr)
        return 1
    print(audio)
    return 0


if __name__ == '__main__':
    sys.exit(main())
