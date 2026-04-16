"""
extraction/normalizer.py
========================
Pure function module — zero file I/O, zero side effects.

Responsibilities
----------------
- clean_text(text)              Strip whitespace, collapse runs, drop non-printables.
- normalize_skill(raw)          Lower + clean + alias resolution via taxonomy.
- parse_relative_date(rel, ref) "3 hours ago" / "2 days ago" → datetime (UTC).
- tokenize(text)                Split text into candidate token strings for fuzzy pass.

All functions are stateless and deterministic. They may be called from any
module without risking I/O or global mutation.

Design notes
------------
- parse_relative_date never raises — returns None if the input cannot be parsed.
- tokenize produces both unigrams and bigrams so multi-word skills (e.g. "machine
  learning", "spring boot") can be matched by the regex and fuzzy layers.
- The alias map is accessed via get_canonical() from skill_taxonomy, which
  already handles lower-casing internally.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Iterator

from config.skill_taxonomy import get_canonical

# ---------------------------------------------------------------------------
# Regex patterns (compiled once at module load)
# ---------------------------------------------------------------------------

# Matches runs of whitespace (including non-breaking spaces)
_RE_WHITESPACE = re.compile(r"[\s\u00a0]+")

# Matches characters that are not printable ASCII or common Unicode letters/digits.
# We preserve: letters, digits, spaces, hyphens, slashes, dots, #, +, _
_RE_NON_PRINTABLE = re.compile(r"[^\w\s\-/.#+]", re.UNICODE)

# Pattern for relative date strings:
# "just now", "2 minutes ago", "1 hour ago", "3 days ago",
# "1 week ago", "2 months ago", "1 year ago"
_RE_RELATIVE_DATE = re.compile(
    r"""
    (?:
        (?P<just>just\s+now|today)
        |
        (?P<value>\d+)\s+
        (?P<unit>second|minute|hour|day|week|month|year)s?
        \s+ago
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Token splitter: split on whitespace AND punctuation except hyphens (for "c#", "c++")
_RE_TOKEN_SPLIT = re.compile(r"[\s,;|/\\()\[\]{}<>\"']+")

# ---------------------------------------------------------------------------
# Unit → timedelta mapping for parse_relative_date
# ---------------------------------------------------------------------------
_UNIT_DELTAS: dict[str, timedelta] = {
    "second":  timedelta(seconds=1),
    "minute":  timedelta(minutes=1),
    "hour":    timedelta(hours=1),
    "day":     timedelta(days=1),
    "week":    timedelta(weeks=1),
    "month":   timedelta(days=30),   # approximation
    "year":    timedelta(days=365),  # approximation
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def clean_text(text: str | None) -> str:
    """
    Normalise a raw text string for downstream processing.

    Steps applied (in order)
    ------------------------
    1. Return empty string immediately if input is None or empty.
    2. Decode/normalise Unicode to NFC (canonical composition).
    3. Replace runs of whitespace (including NBSP) with a single space.
    4. Strip leading/trailing whitespace.

    Note: We intentionally do NOT lowercase here — case is preserved so that
    canonical skill matching (which is case-aware for proper nouns like
    "Python", "Django") works correctly at the caller level.

    Parameters
    ----------
    text : str | None

    Returns
    -------
    str
        Cleaned text, or "" if input was None / empty.
    """
    if not text:
        return ""
    # NFC normalisation consolidates accented characters and ligatures
    text = unicodedata.normalize("NFC", text)
    # Collapse whitespace runs
    text = _RE_WHITESPACE.sub(" ", text)
    return text.strip()


def normalize_skill(raw: str | None) -> str | None:
    """
    Resolve a raw skill string to its canonical form.

    Resolution pipeline
    -------------------
    1. Clean and strip the input.
    2. Delegate to get_canonical(raw) from skill_taxonomy, which:
       a. Checks SKILL_ALIAS_MAP (lower-cased key).
       b. Falls back to a case-insensitive direct match against canonical skills.
       c. Returns None if neither matches.

    Parameters
    ----------
    raw : str | None
        Raw skill text (e.g. "reactjs", "  React.JS ", "k8s").

    Returns
    -------
    str | None
        Canonical skill (e.g. "React"), or None if not resolvable.

    Examples
    --------
    >>> normalize_skill("  React.JS ")
    'React'
    >>> normalize_skill("golang")
    'Go'
    >>> normalize_skill("banana")
    None
    """
    if not raw:
        return None
    cleaned = clean_text(raw)
    if not cleaned:
        return None
    return get_canonical(cleaned)


def parse_relative_date(
    relative_str: str | None,
    reference_dt: datetime | None = None,
) -> datetime | None:
    """
    Convert a relative date string to an absolute UTC datetime.

    Supported formats
    -----------------
    - "just now" / "today"     → reference_dt (now)
    - "X minutes ago"          → reference_dt − X minutes
    - "X hours ago"            → reference_dt − X hours
    - "X days ago"             → reference_dt − X days
    - "X weeks ago"            → reference_dt − X weeks
    - "X months ago"           → reference_dt − 30 × X days
    - "X years ago"            → reference_dt − 365 × X days

    Parameters
    ----------
    relative_str : str | None
        Raw relative date text as scraped from Wuzzuf (e.g. "3 hours ago").
    reference_dt : datetime | None
        The reference point in time. Defaults to datetime.now(UTC).
        Useful for deterministic unit testing.

    Returns
    -------
    datetime | None
        UTC-aware datetime, or None if the string cannot be parsed.

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> ref = datetime(2026, 4, 16, 12, 0, 0, tzinfo=timezone.utc)
    >>> parse_relative_date("3 hours ago", ref)
    datetime.datetime(2026, 4, 16, 9, 0, tzinfo=datetime.timezone.utc)
    >>> parse_relative_date("2 days ago", ref)
    datetime.datetime(2026, 4, 14, 12, 0, tzinfo=datetime.timezone.utc)
    >>> parse_relative_date("gibberish", ref)
    None
    """
    if not relative_str:
        return None

    if reference_dt is None:
        reference_dt = datetime.now(tz=timezone.utc)
    # Ensure reference is UTC-aware
    if reference_dt.tzinfo is None:
        reference_dt = reference_dt.replace(tzinfo=timezone.utc)

    cleaned = clean_text(relative_str).lower()
    m = _RE_RELATIVE_DATE.search(cleaned)
    if not m:
        return None

    if m.group("just"):
        return reference_dt

    value = int(m.group("value"))
    unit = m.group("unit").rstrip("s")   # normalise "hours" → "hour"
    delta = _UNIT_DELTAS.get(unit)
    if delta is None:
        return None

    return reference_dt - (delta * value)


def tokenize(text: str | None) -> list[str]:
    """
    Split text into a flat list of candidate token strings suitable for
    fuzzy skill matching (Layer 3 in the extractor).

    Produces BOTH unigrams and bigrams so multi-word skills like
    "machine learning" or "spring boot" are represented as single tokens.

    Filtering rules
    ---------------
    - Unigrams shorter than 2 characters are discarded (too ambiguous).
    - Bigrams are formed from adjacent unigrams (no cross-sentence bigrams).
    - Tokens are returned in their original casing (fuzzy matching is
      case-insensitive at the match site).

    Parameters
    ----------
    text : str | None

    Returns
    -------
    list[str]
        Flat list: unigrams first, then bigrams.

    Examples
    --------
    >>> tokenize("experience with Python and machine learning")
    ['experience', 'with', 'Python', 'and', 'machine', 'learning',
     'experience with', 'with Python', 'Python and', 'and machine',
     'machine learning']
    """
    if not text:
        return []

    raw_tokens = _RE_TOKEN_SPLIT.split(clean_text(text))
    unigrams = [t for t in raw_tokens if len(t) >= 2]

    bigrams = [
        f"{unigrams[i]} {unigrams[i + 1]}"
        for i in range(len(unigrams) - 1)
    ]

    return unigrams + bigrams
