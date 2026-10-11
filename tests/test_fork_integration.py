"""Offline maintained-fork seams: safe defaults, audio/icons, locks and API shapes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import main as pipeline
from runtime_lock import pipeline_lock
from state import State
from yoto_client import YotoClient


class ForkIntegrationTests(unittest.TestCase):
    def test_clean_environment_defaults_to_library_and_zero_allowance(self):
        env = {name: os.environ[name] for name in ('PATH', 'PYTHONPATH', 'TMPDIR') if name in os.environ}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        result = subprocess.run([sys.executable, '-c',
            'import json; from config import Config; print(json.dumps([Config.ICON_SOURCE, Config.ICON_AI_MAX_GENERATIONS, Config.REPLICATE_API_TOKEN]))'],
            env=env, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout), ['yoto-library', 0, ''])

    def test_valid_audio_uses_shared_library_resolver_without_paid_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            card = root / 'watch' / 'Card'
            card.mkdir(parents=True)
            path = card / ('A' * 22 + '--Song.mp3')
            path.write_bytes(b'fixture')
            (card / '.spotify_tracks.json').write_text(json.dumps({'A' * 22: {'duration_ms': 120000}}))
            state = State(root / 'state.json')
            client = Mock(spec=YotoClient)
            client.upload_audio.return_value = {'sha256': 'fixture'}
            client.get_card_and_chapters.return_value = (None, [])
            client.build_chapter.return_value = {'key': '01'}
            client.save_chapters.return_value = 'card-id'
            with patch.object(pipeline.Config, 'WATCH_DIR', root / 'watch'), \
                 patch.object(pipeline.Config, 'PROCESSED_DIR', root / 'processed'), \
                 patch.object(pipeline.Config, 'ICON_SOURCE', 'yoto-library'), \
                 patch.object(pipeline.Config, 'REPLICATE_API_TOKEN', 'fake-not-a-secret'), \
                 patch.object(pipeline.Config, 'ICON_AI_MAX_GENERATIONS', 1), \
                 patch.object(pipeline, 'wait_for_stable_file'), \
                 patch.object(pipeline, 'MutagenFile', return_value=SimpleNamespace(info=SimpleNamespace(length=120))), \
                 patch.object(pipeline, 'read_tags', return_value=('Song', 'Artist')), \
                 patch('icon_resolver.find_library_icon', return_value='library-id'), \
                 patch('art_generator.extract_subject') as subject, \
                 patch('art_generator.generate_pixel_art') as generate:
                pipeline.process_file(path, client, state)
                resolver = client._spototo_icon_resolver
                self.assertEqual(pipeline.resolve_icon(client, 'Other Song', 'other'), 'library-id')
                self.assertIs(client._spototo_icon_resolver, resolver)
                subject.assert_not_called()
                generate.assert_not_called()
            client.upload_icon.assert_not_called()
            client.build_chapter.assert_called_once_with(1, 'Song', 'Artist', {'sha256': 'fixture'}, 'library-id')
            self.assertEqual(state.get('chapters'), {'Card': {'A' * 22: '01'}})
            self.assertTrue((root / 'processed' / 'Card' / 'Song.mp3').exists())

    def test_main_lock_prevents_state_load_when_maintenance_holds_it(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            with patch.object(pipeline.Config, 'STATE_FILE', path), \
                 patch.object(pipeline.Config, 'validate'), \
                 patch.object(pipeline, 'State') as state, \
                 patch.object(pipeline, '_run_pipeline') as run, pipeline_lock(path):
                with self.assertRaisesRegex(RuntimeError, 'already running'):
                    pipeline.main()
                state.assert_not_called()
                run.assert_not_called()

    def test_invalid_upload_durations_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ('A' * 22 + '--Song.mp3')
            path.write_bytes(b'fixture')
            for value in (None, True, 0, -1, float('nan'), float('inf'), '120000'):
                with self.subTest(expected=value):
                    (path.parent / '.spotify_tracks.json').write_text(json.dumps({'A' * 22: {'duration_ms': value}}))
                    with patch.object(pipeline, 'MutagenFile', return_value=SimpleNamespace(info=SimpleNamespace(length=120))):
                        with self.assertRaises(ValueError):
                            pipeline.validate_spotify_audio(path, 'A' * 22)

    def test_actual_yoto_wrapped_and_flat_content_parsers(self):
        chapters = [{'key': '003', 'tracks': [{'key': '01', 'trackUrl': 'yoto:#fixture'}]}]
        for payload in ({'card': {'content': {'chapters': chapters}}}, {'content': {'chapters': chapters}}):
            self.assertEqual(YotoClient.extract_existing_chapters(payload), chapters)
        for payload in ({'card': {'cardId': 'fixture'}}, {'cardId': 'fixture'}):
            self.assertEqual(YotoClient._extract_card_id(payload), 'fixture')
        for payload in ({}, {'content': {'chapters': None}}):
            with self.assertRaises(ValueError):
                YotoClient.extract_existing_chapters(payload)

    def test_actual_yoto_media_shapes_and_chapter_builder(self):
        client = YotoClient(SimpleNamespace(), Mock())
        with patch.object(client, '_get', return_value={'displayIcons': [{'mediaId': 'library', 'title': 'Moon', 'tags': []}]}):
            self.assertEqual(client.list_library_icons()[0]['mediaId'], 'library')
        with patch.object(client, '_post_binary', return_value={'displayIcon': {'mediaId': 'uploaded'}}):
            self.assertEqual(client.upload_icon(b'fixture'), 'uploaded')
        chapter = client.build_chapter(3, 'Song', 'Artist', {'trackUrl': 'yoto:#fixture', 'duration': 120}, 'library')
        self.assertEqual(chapter['key'], '03')
        self.assertEqual(chapter['display']['icon16x16'], 'yoto:#library')
        self.assertEqual(chapter['tracks'][0]['trackUrl'], 'yoto:#fixture')
        self.assertNotIn('display', client.build_chapter(3, 'Song', None, {'trackUrl': 'yoto:#fixture'}))
