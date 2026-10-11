"""Downloader compatibility regression tests; no network or real audio."""
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import spotipy
from spotify_sync import sync
# Load the project's CLI compatibility shims, without running the CLI.
from spotify_sync import run_spotify_dl


class DownloaderWrapperTests(unittest.TestCase):
    track = {'id': 'track', 'title': "I'm So Happy", 'artist': 'Ms. Rachel', 'duration_ms': 120000}
    candidate = {'id': 'video', 'title': "I'm So Happy", 'uploader': 'Ms Rachel', 'duration': 120}

    def test_direct_download_options_filter_tags_and_provenance(self):
        import json
        from unittest.mock import MagicMock
        self.assertTrue(hasattr(run_spotify_dl, 'download_track'), 'canonical downloader is missing')
        ydl = MagicMock()
        ydl.__enter__.return_value = ydl
        ydl.extract_info.side_effect = [{'entries': [self.candidate]}, self.candidate]
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / 'video.mp3'
            audio.write_bytes(b'fixture')
            with patch.object(run_spotify_dl.yt_dlp, 'YoutubeDL', return_value=ydl) as factory, patch.object(run_spotify_dl, 'tag_audio') as tags:
                run_spotify_dl.download_track(self.track, Path(directory))
            calls = ydl.extract_info.call_args_list
            self.assertIn('official audio', calls[0].args[0])
            self.assertFalse(calls[0].kwargs['download'])
            self.assertEqual(calls[-1].args[0], 'https://www.youtube.com/watch?v=video')
            self.assertTrue(calls[-1].kwargs['download'])
            options = factory.call_args_list[-1].args[0]
            self.assertTrue(options['noplaylist'])
            self.assertEqual(options['js_runtimes'], {'node': {}})
            self.assertEqual(options['remote_components'], ['ejs:github'])
            self.assertEqual(options['postprocessors'][0]['preferredquality'], '128')
            self.assertIsNone(options['match_filter'](self.candidate))
            self.assertIsNotNone(options['match_filter'](dict(self.candidate,duration=3600)))
            self.assertIsNotNone(options['match_filter'](dict(self.candidate,duration=None), incomplete=True))
            tags.assert_called_once_with(audio, self.track)
            provenance = json.loads((Path(directory) / 'source.json').read_text())
            self.assertEqual(provenance['id'],'video')
            self.assertEqual(provenance['expected_duration'],120)

    def test_no_eligible_results_never_downloads(self):
        from unittest.mock import MagicMock
        self.assertTrue(hasattr(run_spotify_dl, 'download_track'), 'canonical downloader is missing')
        ydl = MagicMock()
        ydl.__enter__.return_value = ydl
        ydl.extract_info.return_value = {'entries': [dict(self.candidate,duration=3600)]}
        with tempfile.TemporaryDirectory() as directory, patch.object(run_spotify_dl.yt_dlp,'YoutubeDL',return_value=ydl):
            with self.assertRaises(ValueError):
                run_spotify_dl.download_track(self.track,Path(directory))
        self.assertEqual(ydl.extract_info.call_count,3)
        self.assertTrue(all(not c.kwargs['download'] for c in ydl.extract_info.call_args_list))

    def test_full_extraction_duration_mismatch_fails_without_provenance(self):
        from unittest.mock import MagicMock
        ydl = MagicMock()
        ydl.__enter__.return_value = ydl
        ydl.extract_info.side_effect = [{'entries': [self.candidate]}, dict(self.candidate,duration=3600)]
        with tempfile.TemporaryDirectory() as directory, patch.object(run_spotify_dl.yt_dlp,'YoutubeDL',return_value=ydl), patch.object(run_spotify_dl,'tag_audio') as tags:
            with self.assertRaises(ValueError):
                run_spotify_dl.download_track(self.track,Path(directory))
            self.assertFalse((Path(directory) / 'source.json').exists())
            tags.assert_not_called()

    def test_real_mutagen_title_artist_tags(self):
        from mutagen.id3 import ID3
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / 'fixture.mp3'
            audio.write_bytes(b'')
            run_spotify_dl.tag_audio(audio,self.track)
            tags = ID3(audio)
            self.assertEqual(tags['TIT2'].text,[self.track['title']])
            self.assertEqual(tags['TPE1'].text,[self.track['artist']])

    def test_invalid_track_and_relative_output_fail_before_search(self):
        self.assertTrue(hasattr(run_spotify_dl, 'download_track'), 'canonical downloader is missing')
        with patch.object(run_spotify_dl.yt_dlp,'YoutubeDL') as factory:
            with self.assertRaises(ValueError):
                run_spotify_dl.download_track(dict(self.track,duration_ms=0),Path('/scratch'))
            with self.assertRaises(ValueError):
                run_spotify_dl.download_track(self.track,Path('relative'))
            factory.assert_not_called()


class DownloadFilesystemTests(unittest.TestCase):
    def test_downloader_runs_on_staging_filesystem(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            staging = root / "staging" / "Card"
            watch = root / "watch"
            calls = []

            def download(command, **kwargs):
                calls.append(kwargs)
                (staging / "fixture.mp3").write_bytes(b"unit-test fixture, not audio")
                return CompletedProcess(command, 0, "", "")

            with patch.object(sync, "STAGING_DIR", root / "staging"), patch.object(sync, "WATCH_DIR", watch), patch.object(sync.subprocess, "run", side_effect=download), patch.object(sync, "audio_duration_seconds", return_value=120):
                filename = sync.download_track({"id": "A" * 22, "title": "Song", "artist": "Artist", "duration_ms": 120000}, "Card")
            self.assertTrue((watch / "Card" / filename).exists())
            self.assertEqual(calls[0].get("cwd"), str(staging))
            self.assertFalse(staging.exists())


if __name__ == "__main__":
    unittest.main()
