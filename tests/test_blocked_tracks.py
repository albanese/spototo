"""Explicit playlist blocks survive removal/re-add and never download."""
import unittest
from unittest.mock import Mock, patch
from spotify_sync import sync


class BlockedTrackTests(unittest.TestCase):
    def test_block_is_not_overwritten_by_sync_or_playlist_readdition(self):
        blocked={'bad': {'title':'Wrong source','reason':'No verified original'}}
        state={'playlists':{'playlist':{'downloaded':{},'blocked':blocked}}}
        client=Mock()
        track={'id':'bad','title':'Wrong source','artist':'Artist','duration_ms':120000}
        with patch.object(sync,'SPOTIPY_CLIENT_ID','fixture'),patch.object(sync,'SPOTIPY_CLIENT_SECRET','fixture'),patch.object(sync,'load_state',return_value=state),patch.object(sync,'build_client',return_value=client),patch.object(sync,'discover_playlists',return_value=[{'id':'playlist','name':'Yoto-Test'}]),patch.object(sync,'fetch_playlist_tracks',side_effect=[[track],[],[track]]),patch.object(sync,'write_manifest'),patch.object(sync,'write_track_metadata'),patch.object(sync,'save_state'),patch.object(sync,'download_track') as download,patch.object(sync.Path,'mkdir'):
            for _ in range(3):self.assertEqual(sync.main(),0)
        download.assert_not_called()
        self.assertEqual(state['playlists']['playlist']['blocked'],blocked)

    def test_unblocked_new_track_still_downloads(self):
        state={'playlists':{'playlist':{'downloaded':{},'blocked':{'bad':{'reason':'No original'}}}}}
        track={'id':'good','title':'Good','artist':'Artist','duration_ms':120000}
        with patch.object(sync,'SPOTIPY_CLIENT_ID','fixture'),patch.object(sync,'SPOTIPY_CLIENT_SECRET','fixture'),patch.object(sync,'load_state',return_value=state),patch.object(sync,'build_client',return_value=Mock()),patch.object(sync,'discover_playlists',return_value=[{'id':'playlist','name':'Yoto-Test'}]),patch.object(sync,'fetch_playlist_tracks',return_value=[track]),patch.object(sync,'write_manifest'),patch.object(sync,'write_track_metadata'),patch.object(sync,'save_state'),patch.object(sync,'download_track',return_value='good.mp3') as download,patch.object(sync.Path,'mkdir'):
            self.assertEqual(sync.main(),0)
        download.assert_called_once_with(track,'Test')
