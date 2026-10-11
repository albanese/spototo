"""Exercise installed sync APIs and real media tools without provider I/O."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import spotipy
import yt_dlp
from spotify_sync import sync
from spotify_sync.source_matching import duration_matches


class SyncRuntimeTests(unittest.TestCase):
    def test_installed_spotipy_uses_items_endpoint(self):
        client = spotipy.Spotify(auth='offline-fixture')
        with patch.object(client, '_get', return_value={'items': [], 'next': None}) as get:
            self.assertEqual(sync.fetch_playlist_tracks(client, 'A' * 22), [])
        self.assertEqual(get.call_args.args, ('playlists/' + 'A' * 22 + '/items',))
        self.assertEqual(get.call_args.kwargs['additional_types'], 'track')

    def test_real_ffmpeg_ffprobe_and_mutagen_duration(self):
        from mutagen import File
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'tone.mp3'
            subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                            '-i', 'sine=frequency=440:duration=2', '-b:a', '128k', str(path)], check=True)
            duration = sync.audio_duration_seconds(path)
            self.assertGreater(path.stat().st_size, 0)
            self.assertTrue(duration_matches(duration, 2))
            self.assertAlmostEqual(File(path).info.length, duration, places=3)

    def test_installed_ytdlp_calls_filter_with_incomplete_keyword(self):
        calls = []
        def match_filter(info, *, incomplete=False):
            calls.append(incomplete)
            return None
        with yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True, 'match_filter': match_filter}) as downloader:
            downloader._match_entry({'id': 'fixture', 'title': 'Fixture', 'duration': 2}, incomplete=True)
            downloader._match_entry({'id': 'fixture', 'title': 'Fixture', 'duration': 2}, incomplete=False)
        self.assertEqual(calls, [True, False])
