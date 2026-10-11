import importlib
import unittest


class SourceMatchingTests(unittest.TestCase):
    def setUp(self):
        try:
            self.matching = importlib.import_module('spotify_sync.source_matching')
        except ModuleNotFoundError:
            self.fail('duration-aware source_matching module is missing')
        self.track = {'id': 'track', 'title': "I'm So Happy", 'artist': 'Ms. Rachel, Mr. Aron', 'duration_ms': 120000}

    def entry(self, **kwargs):
        return dict({'id': 'video', 'title': "I'm So Happy Official Audio", 'uploader': 'Ms Rachel', 'duration': 120}, **kwargs)

    def test_duration_tolerance_and_invalid_values(self):
        for actual, expected, matches in [(108,120,True),(132,120,True),(107,120,False),(133,120,False),(85,95,True),(84,95,False),(3600,120,False)]:
            self.assertEqual(self.matching.duration_matches(actual,expected), matches)
        for bad in [None,0,-1,float('nan'),float('inf'),'unknown',True]:
            self.assertFalse(self.matching.duration_matches(bad,120))
            self.assertFalse(self.matching.duration_matches(120,bad))

    def test_nearest_valid_source_beats_compilation(self):
        entries = [self.entry(duration=3600), self.entry(id='near', duration=121), self.entry(id='far', duration=130)]
        self.assertEqual(self.matching.select_candidate(entries,self.track)['id'],'near')

    def test_primary_artist_must_be_corroborated(self):
        for fields in [{'uploader':'Mr Aron'}, {'uploader':'Unrelated'}, {'uploader':'Rachelson'}]:
            with self.assertRaises(ValueError):
                self.matching.select_candidate([self.entry(**fields)],self.track)
        self.assertEqual(self.matching.select_candidate([self.entry(uploader='Songs for Littles',channel='Rachel')],self.track)['id'],'video')

    def test_title_missing_duration_and_unrequested_variants_rejected(self):
        for fields in [{'title':'Different song'}, {'duration':None}, {'duration':float('nan')}, {'title':"I'm So Happy 1 hour"}, {'title':"I'm So Happy 60 minutes"}, {'title':"I'm So Happy compilation"}, {'title':"I'm So Happy live"}, {'title':"I'm So Happy cover"}, {'is_live':True}]:
            with self.assertRaises(ValueError):
                self.matching.select_candidate([self.entry(**fields)],self.track)

    def test_requested_cover_is_allowed(self):
        track = dict(self.track,title="I'm So Happy Cover")
        self.assertEqual(self.matching.select_candidate([self.entry(title="I'm So Happy Cover")],track)['id'],'video')

    def test_articles_and_ampersands_normalize_but_effects_do_not(self):
        track = dict(self.track, title='The Wheels on the Bus')
        self.assertEqual(self.matching.select_candidate([self.entry(title='Wheels on the Bus Ms Rachel')],track)['id'],'video')
        track = dict(self.track, title='Up and Down')
        self.assertEqual(self.matching.select_candidate([self.entry(title='Up & Down Ms Rachel')],track)['id'],'video')
        for variant in ('Remix','Effects','Tutorial','Beeping Version','Instrumental','Karaoke','FAN-MADE'):
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                self.matching.select_candidate([self.entry(title="I'm So Happy "+variant)],self.track)

    def test_expected_duration_is_required(self):
        for bad in [None,0,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):
                self.matching.select_candidate([self.entry()],dict(self.track,duration_ms=bad))


if __name__ == '__main__':
    unittest.main()
