"""Yoto upload boundary and in-place chapter replacement regressions."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'spotify_sync'))
import main as pipeline


class UploadBoundaryTests(unittest.TestCase):
    def test_compilation_rejected_before_icon_or_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/('A'*22+'--Song.mp3');path.write_bytes(b'fixture')
            (root/'.spotify_tracks.json').write_text(json.dumps({'A'*22:{'duration_ms':120000}}))
            client=Mock();state=Mock()
            with patch.object(pipeline, 'wait_for_stable_file'), patch.object(pipeline, 'MutagenFile', return_value=SimpleNamespace(info=SimpleNamespace(length=3600))), patch.object(pipeline,'resolve_icon') as icon:
                with self.assertRaises(ValueError):pipeline.process_file(path,client,state)
            client.upload_audio.assert_not_called();icon.assert_not_called()

    def test_missing_metadata_rejected_before_upload(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/('A'*22+'--Song.mp3');path.write_bytes(b'fixture');client=Mock()
            with patch.object(pipeline,'wait_for_stable_file'),patch.object(pipeline,'resolve_icon'),patch.object(pipeline,'read_tags',return_value=('Song','Artist')):
                with self.assertRaises(ValueError):pipeline.process_file(path,client,Mock())
            client.upload_audio.assert_not_called()

    def test_existing_track_replaces_same_chapter_not_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);card=root/'watch'/'Card';card.mkdir(parents=True)
            path=card/('A'*22+'--Song.mp3');path.write_bytes(b'fixture')
            (card/'.spotify_tracks.json').write_text(json.dumps({'A'*22:{'duration_ms':120000}}))
            from state import State
            state=State(root/'state.json');state.update(cards={'Card':'card-id'},chapters={'Card':{'A'*22:'01'}})
            old={'key':'01','title':'old'};manual={'key':'03','title':'manual'};new={'key':'01','title':'correct'}
            client=Mock();client.get_card_and_chapters.return_value=('card-id',[old,manual]);client.build_chapter.return_value=new;client.save_chapters.return_value='card-id';client.upload_audio.return_value={'sha256':'test'}
            with patch.object(pipeline.Config,'WATCH_DIR',root/'watch'),patch.object(pipeline.Config,'PROCESSED_DIR',root/'processed'),patch.object(pipeline,'wait_for_stable_file'),patch.object(pipeline,'MutagenFile',return_value=SimpleNamespace(info=SimpleNamespace(length=121))),patch.object(pipeline,'read_tags',return_value=('Song','Artist')),patch.object(pipeline,'resolve_icon',return_value=None):
                pipeline.process_file(path,client,state)
            client.save_chapters.assert_called_once_with('card-id',[new,manual],title='Card')
            chapters_map = state.get('chapters') or {}
            self.assertEqual(chapters_map['Card']['A'*22],'01')
            self.assertTrue((root/'processed'/'Card'/'Song.mp3').exists())
