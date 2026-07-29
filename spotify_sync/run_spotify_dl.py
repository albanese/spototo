#!/usr/bin/env python3
"""
Thin wrapper around the `spotify_dl` CLI entry point.

spotify_dl calls yt_dlp.YoutubeDL(...) directly with its own hardcoded
options dict, so there's no CLI flag to pass through extra yt-dlp options.
Modern YouTube requires yt-dlp to run a JS challenge solver to extract
formats (plain requests get "This video is not available"), which needs
`js_runtimes` and `remote_components` set on the YoutubeDL instance.

This patches YoutubeDL.__init__ to inject those defaults before calling
spotify_dl's own main(), so sync.py can invoke this script in place of the
bare `spotify_dl` executable. See
https://github.com/yt-dlp/yt-dlp/wiki/EJS for background on the JS
challenge requirement.
"""
import sys

import yt_dlp

_orig_init = yt_dlp.YoutubeDL.__init__


def _patched_init(self, params=None, *args, **kwargs):
    params = dict(params or {})
    params.setdefault("js_runtimes", {"node": {}})
    params.setdefault("remote_components", ["ejs:github"])
    _orig_init(self, params, *args, **kwargs)


yt_dlp.YoutubeDL.__init__ = _patched_init

from spotify_dl.spotify_dl import spotify_dl  # noqa: E402

if __name__ == "__main__":
    sys.exit(spotify_dl())
