"""Fail-closed Spotify metadata and finished-file duration checks."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from subprocess import CompletedProcess
from spotify_sync import sync


class DurationGuardTests(unittest.TestCase):
    def test_playlist_preserves_expected_duration(self):
        client = Mock()
        client.playlist_items.return_value = {'items': [{'item': {
            'id': 'A'*22, 'name': 'Song', 'artists': [{'name': 'Artist'}],
            'duration_ms': 120000, 'type': 'track'}}], 'next': None}
        self.assertEqual(sync.fetch_playlist_tracks(client, 'playlist')[0]['duration_ms'], 120000)

    def test_hour_compilation_never_enters_watch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def download(command, **kwargs):
                (root/'staging'/'Card'/'song.mp3').write_bytes(b'fixture')
                return CompletedProcess(command, 0, '', '')
            with patch.object(sync, 'STAGING_DIR', root/'staging'), patch.object(sync, 'WATCH_DIR', root/'watch'), patch.object(sync.subprocess, 'run', side_effect=download), patch.object(sync, 'audio_duration_seconds', return_value=3600, create=True):
                with self.assertRaises(ValueError):
                    sync.download_track({'id': 'A'*22, 'title': 'Song', 'artist': 'Artist', 'duration_ms': 120000}, 'Card')
            self.assertFalse(list((root/'watch').rglob('*.mp3')))

    def test_missing_expected_duration_fails_before_download(self):
        with patch.object(sync.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                sync.download_track({'id': 'A'*22}, 'Card')
            run.assert_not_called()

    def test_short_matching_audio_can_enter_watch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def download(command, **kwargs):
                (root/'staging'/'Card'/'song.mp3').write_bytes(b'fixture')
                return CompletedProcess(command, 0, '', '')
            with patch.object(sync, 'STAGING_DIR', root/'staging'), patch.object(sync, 'WATCH_DIR', root/'watch'), patch.object(sync.subprocess, 'run', side_effect=download), patch.object(sync, 'audio_duration_seconds', return_value=123, create=True):
                name = sync.download_track({'id': 'A'*22, 'title': 'Song', 'artist': 'Artist', 'duration_ms': 120000}, 'Card')
            self.assertTrue((root/'watch'/'Card'/name).exists())

    def test_missing_or_nonfinite_duration_is_rejected(self):
        for duration in (0, -1, float('nan'), float('inf'), None, True, '120000'):
            with self.subTest(duration=duration), patch.object(sync.subprocess, 'run') as run:
                with self.assertRaises(ValueError):
                    sync.download_track({'id':'A'*22, 'duration_ms':duration}, 'Card')
                run.assert_not_called()

    def test_extra_mp3_files_are_not_arbitrarily_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def download(command, **kwargs):
                for name in ('one.mp3', 'two.mp3'):
                    (root/'staging'/'Card'/name).write_bytes(b'fixture')
                return CompletedProcess(command, 0, '', '')
            with patch.object(sync, 'STAGING_DIR', root/'staging'), patch.object(sync, 'WATCH_DIR', root/'watch'), patch.object(sync.subprocess, 'run', side_effect=download):
                with self.assertRaises(ValueError):
                    sync.download_track({'id':'A'*22,'title':'Song','artist':'Artist','duration_ms':120000}, 'Card')
            self.assertFalse(list((root/'watch').rglob('*.mp3')))
