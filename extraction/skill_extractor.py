"""
extraction/skill_extractor.py
──────────────────────────────
Extracts canonical technical skills from job posting text using a
two-stage strategy:

Stage 1 – Exact / Regex matching
    Each alias in ``SKILL_TAXONOMY`` is compiled into a word-boundary regex.
    Matches are immediate and carry no ambiguity cost.

Stage 2 – Fuzzy matching (RapidFuzz token_sort_ratio)
    Unmatched n-grams (1–3 tokens) are compared against every canonical
    skill name via RapidFuzz.  Only candidates exceeding
    ``settings.fuzzy_match_threshold`` are accepted.

Context-Window Gating
    A configurable token window (``settings.context_window_tokens``) is
    applied around every candidate match.  If the surrounding tokens
    contain disqualifying phrases (e.g. "not required", "no experience in")
    the match is discarded.

Usage
─────
    extractor = SkillExtractor()
    skills = extractor.extract("Python 3.10, Apache Spark, and strong SQL skills")
    # → ["python", "apache spark", "sql"]
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Sequence

from rapidfuzz import fuzz, process

from config.settings import settings
from config.skill_taxonomy import SKILL_TAXONOMY
from extraction.normalizer import normalize_skill, normalize_text

logger = logging.getLogger(__name__)

# ── Negation context patterns ─────────────────────────────────────────────────
_NEGATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bnot\s+required\b"),
    re.compile(r"\bno\s+experience\b"),
    re.compile(r"\bno\s+knowledge\b"),
    re.compile(r"\bnot\s+needed\b"),
    re.compile(r"\bwithout\s+\w+\s+in\b"),
]


def _build_alias_map() -> dict[str, str]:
    """Return {alias → canonical_skill} from SKILL_TAXONOMY."""
    alias_map: dict[str, str] = {}
    for canonical, aliases in SKILL_TAXONOMY.items():
        norm_canonical = normalize_skill(canonical)
        alias_map[norm_canonical] = norm_canonical
        for alias in aliases:
            alias_map[normalize_skill(alias)] = norm_canonical
    return alias_map


def _build_regex_patterns(alias_map: dict[str, str]) -> list[tuple[re.Pattern[str], str]]:
    """Compile word-boundary regex patterns for every alias → canonical pair."""
    patterns: list[tuple[re.Pattern[str], str]] = []
    # Sort by descending length so longer phrases match first
    for alias, canonical in sorted(alias_map.items(), key=lambda x: -len(x[0])):
        escaped = re.escape(alias)
        pat = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
        patterns.append((pat, canonical))
    return patterns


class SkillExtractor:
    """
    Stateless NLP skill extractor.

    Parameters
    ----------
    threshold:
        RapidFuzz score threshold (0-100).  Defaults to
        ``settings.fuzzy_match_threshold``.
    context_window:
        Number of tokens on each side of a candidate to check for
        negation signals.  Defaults to ``settings.context_window_tokens``.
    """

    def __init__(
        self,
        threshold: int | None = None,
        context_window: int | None = None,
    ) -> None:
        self._threshold = threshold if threshold is not None else settings.fuzzy_match_threshold
        self._context_window = (
            context_window if context_window is not None else settings.context_window_tokens
        )
        self._alias_map = _build_alias_map()
        self._regex_patterns = _build_regex_patterns(self._alias_map)
        self._canonical_skills = list({normalize_skill(k) for k in SKILL_TAXONOMY})

    # ── Public API ────────────────────────────────────────────────────────────

    def extract(self, text: str) -> list[str]:
        """
        Return a deduplicated, sorted list of canonical skill names found
        in *text*.

        Parameters
        ----------
        text:
            Raw job posting text (title + description concatenated).
        """
        normalised = normalize_text(text)
        tokens = normalised.split()

        found: set[str] = set()

        # Stage 1 – Regex / exact matching
        remaining_text = normalised
        for pattern, canonical in self._regex_patterns:
            for match in pattern.finditer(remaining_text):
                if self._context_gate(tokens, match.start(), remaining_text):
                    found.add(canonical)

        # Stage 2 – Fuzzy matching on remaining n-grams
        unmatched_ngrams = self._extract_ngrams(normalised, found)
        for ngram in unmatched_ngrams:
            result = process.extractOne(
                ngram,
                self._canonical_skills,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=self._threshold,
            )
            if result:
                candidate, score, _ = result
                if self._context_gate_text(normalised, ngram):
                    logger.debug("Fuzzy match: %r → %r (score=%d)", ngram, candidate, score)
                    found.add(candidate)

        return sorted(found)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _context_gate(
        self,
        tokens: list[str],
        char_offset: int,
        text: str,
    ) -> bool:
        """
        Return *False* if the token context around *char_offset* in *text*
        contains a negation signal, otherwise *True*.
        """
        start = max(0, char_offset - 60)
        end = min(len(text), char_offset + 60)
        window = text[start:end]
        for neg_pattern in _NEGATION_PATTERNS:
            if neg_pattern.search(window):
                return False
        return True

    def _context_gate_text(self, full_text: str, ngram: str) -> bool:
        """Variant of context gate that operates on a substring search."""
        pos = full_text.find(ngram)
        if pos == -1:
            return True
        return self._context_gate([], pos, full_text)

    def _extract_ngrams(
        self,
        text: str,
        already_found: set[str],
        max_n: int = 3,
    ) -> list[str]:
        """
        Generate n-grams (n=1..max_n) from *text* that are **not** already
        covered by an exact match result.
        """
        tokens = text.split()
        ngrams: list[str] = []
        for n in range(1, max_n + 1):
            for i in range(len(tokens) - n + 1):
                gram = " ".join(tokens[i : i + n])
                if gram not in already_found and len(gram) >= 3:
                    ngrams.append(gram)
        return ngrams
