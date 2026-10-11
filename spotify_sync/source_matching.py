"""Fail-closed metadata selection for individual Spotify songs."""
import math
import re
import unicodedata


def _positive_seconds(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and value > 0 else None


def duration_matches(actual_seconds, expected_seconds):
    """Accept finite positive durations within max(10s, 10% expected)."""
    actual = _positive_seconds(actual_seconds)
    expected = _positive_seconds(expected_seconds)
    return actual is not None and expected is not None and abs(actual - expected) <= max(10.0, expected * 0.1)


def _tokens(text):
    text = unicodedata.normalize('NFKD', str(text or '')).casefold()
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = text.replace("'", '').replace('’', '').replace('&', ' and ')
    return [word for word in re.findall(r'[a-z0-9]+', text) if word not in {'the', 'a', 'an'}]


def primary_artist(track):
    return re.split(r',|\s+(?:feat\.?|ft\.?|featuring|&)\s+', track['artist'], maxsplit=1, flags=re.I)[0].strip()


def validate_track(track):
    if not isinstance(track, dict) or any(not isinstance(track.get(key), str) or not track[key].strip() for key in ('id', 'title', 'artist')):
        raise ValueError('Track requires nonempty id, title, artist')
    duration = _positive_seconds(track.get('duration_ms'))
    if duration is None:
        raise ValueError('Spotify duration_ms must be finite and positive')
    if not _tokens(track['title']) or not (set(_tokens(primary_artist(track))) - {'ms', 'mr', 'mrs', 'miss', 'the'}):
        raise ValueError('Track title and primary artist must have meaningful tokens')
    return duration / 1000.0


def select_candidate(entries, track):
    """Return best eligible entry, never an unvalidated first result."""
    expected = validate_track(track)
    wanted_title = _tokens(track['title'])
    artist = set(_tokens(primary_artist(track))) - {'ms', 'mr', 'mrs', 'miss', 'the'}
    requested = set(wanted_title)
    ranked = []
    for entry in entries or []:
        if not isinstance(entry, dict) or not re.fullmatch(r'[A-Za-z0-9_-]+', str(entry.get('id') or '')):
            continue
        if not duration_matches(entry.get('duration'), expected):
            continue
        title = _tokens(entry.get('title'))
        if not any(title[i:i + len(wanted_title)] == wanted_title for i in range(len(title))):
            continue
        if any(token in title and token not in requested for token in ('compilation', 'compilations', 'live', 'cover', 'covers', 'remix', 'effects', 'tutorial', 'beeping', 'instrumental', 'karaoke', 'fan', 'parody')):
            continue
        if entry.get('is_live') or entry.get('live_status') in ('is_live', 'is_upcoming', 'was_live'):
            continue
        normalized = ' '.join(title)
        if re.search(r'\b(?:1|one)\s+(?:hour|hr)\b|\b60\s+(?:minutes|mins|min)\b', normalized) and not re.search(r'\b(?:1|one)\s+(?:hour|hr)\b|\b60\s+(?:minutes|mins|min)\b', ' '.join(wanted_title)):
            continue
        evidence = set(_tokens(' '.join(str(entry.get(k) or '') for k in ('title', 'uploader', 'channel'))))
        if not artist.issubset(evidence):
            continue
        ranked.append((abs(float(entry['duration']) - expected), len(title) - len(wanted_title), str(entry['id']), entry))
    if not ranked:
        raise ValueError('No eligible individual YouTube song matches title, primary artist and Spotify duration')
    return min(ranked, key=lambda row: row[:3])[3]
