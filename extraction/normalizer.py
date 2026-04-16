"""
extraction/normalizer.py
────────────────────────
Lightweight text-normalization utilities used before and after skill
extraction to ensure consistent canonical skill names throughout the
pipeline.
"""

from __future__ import annotations

import re
import unicodedata


_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALPHANUM_RE = re.compile(r"[^a-z0-9\s\.\+\#\-\/]")


def normalize_text(text: str) -> str:
    """
    Normalize free-form text before skill extraction.

    Steps
    ─────
    1. Unicode NFKC normalization (e.g. ligatures → plain ASCII).
    2. Lowercase.
    3. Strip accents.
    4. Collapse whitespace.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def normalize_skill(skill: str) -> str:
    """
    Return the canonical lowercase form of a skill name.

    Strips leading/trailing whitespace and collapses internal spaces.
    Preserves meaningful characters such as ``+``, ``#``, ``/``, and ``.``.

    Examples
    ────────
    >>> normalize_skill("  Apache Spark  ")
    'apache spark'
    >>> normalize_skill("C++")
    'c++'
    >>> normalize_skill("Node.JS")
    'node.js'
    """
    skill = unicodedata.normalize("NFKC", skill)
    skill = skill.lower().strip()
    skill = _WHITESPACE_RE.sub(" ", skill)
    return skill


def clean_job_text(title: str, description: str) -> str:
    """
    Concatenate and lightly clean job title + description into a single
    string suitable for NLP extraction.
    """
    combined = f"{title} {description}"
    combined = normalize_text(combined)
    return combined
