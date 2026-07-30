"""
Deterministic, non-AI icon selection: matches a song title against Yoto's
own official icon library by keyword/tag overlap. No LLM, no image
generation -- this is the alternative to art_generator.py for anyone who
doesn't want any AI involved in icon selection (Config.ICON_SOURCE = "yoto-library").

If nothing overlaps well enough to count as a real match, returns None
rather than guessing -- callers should leave the chapter without a custom
icon in that case, not fall back to generation.
"""
import re

_STOPWORDS = {
    "the", "a", "an", "of", "by", "and", "or", "is", "in", "on", "to", "for",
    "with", "feat", "featuring", "remix", "version", "from", "original",
    "soundtrack",
}

_library_cache = None  # [(mediaId, {tokens}), ...] -- fetched once per process


def _tokens(text: str) -> set:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _load_library(client):
    global _library_cache
    if _library_cache is None:
        icons = client.list_library_icons()
        _library_cache = [
            (
                icon["mediaId"],
                _tokens(icon.get("title", "")) | {t.lower() for t in icon.get("publicTags", [])},
            )
            for icon in icons
            if icon.get("mediaId")
        ]
    return _library_cache


def find_library_icon(client, title: str):
    """Returns the mediaId of the best-matching official Yoto icon for
    `title`, or None if no icon shares even one meaningful keyword/tag."""
    query = _tokens(title)
    if not query:
        return None
    best_id, best_score = None, 0
    for media_id, tags in _load_library(client):
        score = len(query & tags)
        if score > best_score:
            best_id, best_score = media_id, score
    return best_id if best_score > 0 else None
