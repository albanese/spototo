"""Regression tests for Spotify's legacy and current playlist item shapes."""
import unittest
from unittest.mock import Mock

from spotify_sync.sync import fetch_playlist_tracks


def song(identifier="song-id", title="Test Song"):
    return {"id": identifier, "name": title, "type": "track", "artists": [{"name": "Test Artist"}], "duration_ms": 120000}


class PlaylistTrackTests(unittest.TestCase):
    def fetch(self, items):
        client = Mock()
        client.playlist_items.return_value = {"items": items, "next": None}
        return fetch_playlist_tracks(client, "playlist-id")

    def test_current_item_field(self):
        self.assertEqual(self.fetch([{"item": song()}]), [{"id": "song-id", "title": "Test Song", "artist": "Test Artist", "duration_ms": 120000}])

    def test_legacy_track_field(self):
        self.assertEqual(self.fetch([{"track": song()}]), [{"id": "song-id", "title": "Test Song", "artist": "Test Artist", "duration_ms": 120000}])

    def test_skip_unavailable_and_local_items(self):
        self.assertEqual(self.fetch([{"item": None}, {"track": None}, {"item": {"id": None}}, {}]), [])

    def test_skip_episodes_in_current_response(self):
        episode = {"id": "episode-id", "name": "Podcast", "type": "episode"}
        self.assertEqual(self.fetch([{"item": episode}]), [])

    def test_pagination_with_both_formats(self):
        client = Mock()
        client.playlist_items.return_value = {"items": [{"item": song("first")}], "next": "next-page"}
        client.next.return_value = {"items": [{"track": song("second")}], "next": None}
        self.assertEqual([row["id"] for row in fetch_playlist_tracks(client, "playlist-id")], ["first", "second"])
        client.next.assert_called_once()


if __name__ == "__main__":
    unittest.main()
