"""
extraction/skill_extractor.py
==============================
Three-layer skill extraction pipeline.

This is the ONLY module in the project permitted to write to
output/extracted_skills.csv. normalizer.py and skill_taxonomy.py are
pure functions and perform no I/O.

PUBLIC API
----------
extract_skills(jobs)   -> list[dict]
    Run the full three-layer pipeline over a list of job dicts.
    Returns a flat list of skill-row dicts (one per job×skill pair).
    Writes output to extracted_skills.csv automatically.

extract_skills_for_job(job) -> list[dict]
    Extract skills for a SINGLE job dict (used in unit tests and
    resumable incremental mode). Does NOT write to CSV.

EXTRACTION LAYERS
-----------------
Layer 1 — Wuzzuf Tags  (confidence = 1.0)
    Source : job["category_tags"] comma-separated chip texts.
    Method : Each chip is passed through normalize_skill() (alias resolution).
    Why first: These are Wuzzuf's own curated tags — highest signal quality.

Layer 2 — Regex Scan   (confidence = 0.95)
    Source : job["job_title"] + " " + job["category_tags"] (combined text).
    Method : For each canonical skill in the taxonomy, build a word-boundary
             regex and scan the combined text (case-insensitive).
    Ambiguous-term guard: single-word terms flagged in AMBIGUOUS_TERMS must
    appear within a ±60-char window of at least one context indicator.
    Why second: Catches skills mentioned in title/tags that weren't in L1.

Layer 3 — Fuzzy Match  (confidence = raw_score / 100)
    Source : same combined text, tokenized into unigrams + bigrams.
    Method : rapidfuzz.process.extractOne() against the full skills list,
             threshold = 85 (FUZZY_THRESHOLD).
    Ambiguous-term guard: same context window check as Layer 2.
    De-duplication: skills already found in L1 or L2 are skipped entirely
    in L3 (no double-counting, no inflated confidence).
    Why third: Safety net for spelling variants, transliterations
    (e.g. "pithon" → "Python"), and locale-specific spellings.

OUTPUT SCHEMA (extracted_skills.csv)
-------------------------------------
job_id, skill_canonical, skill_category, extraction_source, confidence

AMBIGUOUS SINGLE-WORD TERMS
----------------------------
The following canonical skills are short, common English words that appear
frequently in non-technical contexts. They are ONLY matched when a
"context indicator" appears within ±60 characters of the match in the
source text.

Term        → False positive risk
---------     -------------------
"Go"        → "go to the office", "go-getter"
"C"         → "C-suite", "C-level", "category C"
"R"         → "R&D", letter in an acronym
"Spring"    → "spring semester", "spring cleaning"
"Rust"      → "rust belt", "rusty skills"
"Lean"      → "lean management", "lean startup"
"Vault"     → "vault of records"
"Gem"       → not in taxonomy, but guard pattern for future additions
"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path

from rapidfuzz import fuzz, process as rf_process

from config import settings
from config.skill_taxonomy import (
    SKILL_TAXONOMY,
    classify_role,
    get_all_skills,
    get_canonical,
    get_skill_category,
)
from extraction.normalizer import clean_text, normalize_skill, tokenize

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

# Fuzzy match minimum score (0–100). Scores below this are discarded.
FUZZY_THRESHOLD: int = 85

# Characters of context window to scan on each side of an ambiguous match
AMBIGUOUS_CONTEXT_WINDOW: int = 60

# Skills that are short common English words requiring context confirmation.
# Maps canonical skill name → list of context indicator strings (lowercase).
# A match is accepted only if at least ONE indicator appears within
# ±AMBIGUOUS_CONTEXT_WINDOW chars of the match position.
AMBIGUOUS_TERMS: dict[str, list[str]] = {
    "Go": [
        "golang", "go lang", "go programming", "go developer",
        "go backend", "go engineer", "go routine", "goroutine",
        "go module", "go framework", "go microservice",
    ],
    "C": [
        "c programming", "c language", "c developer", "c99", "c11",
        "embedded c", "c standard library", "gcc", "clang",
    ],
    "R": [
        "r programming", "r language", "r developer", "rstudio",
        "tidyverse", "dplyr", "ggplot", "cran", "r package",
        "statistical computing", "r script",
    ],
    "Spring Boot": [
        "java", "spring boot", "spring mvc", "spring cloud",
        "spring security", "spring framework", "spring data",
        "microservice", "restful", "jvm",
    ],
    "Spring Framework": [
        "java", "spring boot", "spring mvc", "spring cloud",
        "spring security", "spring framework", "spring data",
        "jvm",
    ],
    "Rust": [
        "rust lang", "rust programming", "rust developer",
        "cargo", "rustc", "crates.io", "systems programming",
        "memory safe", "webassembly rust",
    ],
    "Lean": [
        "lean software", "lean development", "lean agile",
        "lean startup", "lean manufacturing software",
        "value stream", "kanban lean",
    ],
    "Vault": [
        "hashicorp", "hashicorp vault", "secrets management",
        "secret store", "vault agent", "vault policy",
    ],
    # Core Data is an Apple iOS persistence framework.
    # Without iOS context it fuzzy-matches Firebase, Realm, and other mobile
    # tags at scores ≥ 85 because "core" and "data" are very common words.
    "Core Data": [
        "ios", "swift", "xcode", "apple", "mobile", "swiftui",
        "core data", "ios development", "iphone", "ipad",
    ],
    # Time Series Analysis fuzzy matches generic 'Full-Time' and 'Analysis'
    # without gating. Require the word 'series'.
    "Time Series Analysis": [
        "series",
    ],
}

# ---------------------------------------------------------------------------
# Pre-compiled regex cache: built lazily, keyed by canonical skill name
# ---------------------------------------------------------------------------
_regex_cache: dict[str, re.Pattern[str]] = {}

# Flat list of all canonical skills — built once at module load
_ALL_SKILLS: list[str] = get_all_skills()

# CSV fields for extracted_skills.csv
_SKILL_CSV_FIELDS: list[str] = [
    "job_id",
    "skill_canonical",
    "skill_category",
    "role_category",
    "extraction_source",
    "confidence",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_regex(skill: str) -> re.Pattern[str]:
    """
    Return a compiled word-boundary regex for ``skill``, with caching.

    Special characters in the skill name (e.g. "C++", "C#", ".NET") are
    escaped so they match literally. The word boundary \\b is omitted on the
    right side when the skill ends with a non-word character (e.g. ".NET")
    to avoid regex errors.
    """
    if skill not in _regex_cache:
        escaped = re.escape(skill)
        # Left boundary: \\b works if skill starts with a word char, else use lookahead
        left = r"\b" if re.match(r"\w", skill) else r"(?<!\w)"
        # Right boundary: \\b works if skill ends with a word char
        right = r"\b" if re.search(r"\w$", skill) else r"(?!\w)"
        pattern = re.compile(left + escaped + right, re.IGNORECASE)
        _regex_cache[skill] = pattern
    return _regex_cache[skill]


def _context_check(text: str, match_start: int, match_end: int, skill: str) -> bool:
    """
    For ambiguous skills, confirm at least one context indicator appears
    within AMBIGUOUS_CONTEXT_WINDOW characters of the match span in ``text``.

    Parameters
    ----------
    text        : The full source text being scanned.
    match_start : Start index of the matched skill in ``text``.
    match_end   : End index of the matched skill in ``text``.
    skill       : Canonical skill name (looked up in AMBIGUOUS_TERMS).

    Returns
    -------
    bool
        True if the skill is NOT ambiguous (always passes), OR if it IS
        ambiguous and a context indicator was found nearby.
        False if ambiguous and no context indicator found.
    """
    indicators = AMBIGUOUS_TERMS.get(skill)
    if not indicators:
        return True  # Not an ambiguous term — always pass

    # Extract the surrounding context window (clamped to string bounds)
    lo = max(0, match_start - AMBIGUOUS_CONTEXT_WINDOW)
    hi = min(len(text), match_end + AMBIGUOUS_CONTEXT_WINDOW)
    window = text[lo:hi].lower()

    return any(ind in window for ind in indicators)


def _ensure_csv_header(path: Path) -> None:
    """Write skill CSV header if the file is new or empty."""
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_SKILL_CSV_FIELDS)
            writer.writeheader()
        logger.debug("Skill CSV header written to %s", path)


def _append_skills_to_csv(rows: list[dict], path: Path) -> None:
    """Append skill rows to extracted_skills.csv."""
    if not rows:
        return
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_SKILL_CSV_FIELDS, extrasaction="ignore")
        writer.writerows(rows)
    logger.debug("Appended %d skill row(s) to %s", len(rows), path)


def _make_skill_row(
    job_id: str | None,
    skill: str,
    source: str,
    confidence: float,
    role_category: str = "Other Tech",
) -> dict:
    """Build a single extracted-skill row dict."""
    return {
        "job_id":            job_id or "",
        "skill_canonical":   skill,
        "skill_category":    get_skill_category(skill) or "unknown",
        "role_category":     role_category,
        "extraction_source": source,
        "confidence":        round(confidence, 4),
    }


# ---------------------------------------------------------------------------
# Layer 1 — Wuzzuf Tags (confidence = 1.0)
# ---------------------------------------------------------------------------

def _layer1_tags(job: dict) -> tuple[set[str], list[dict]]:
    """
    Extract skills from the ``category_tags`` field (Wuzzuf's own chip tags).

    The tags field is a comma-separated string of chip texts scraped from the
    listing card (e.g. "IT/Software Development,Python,Django,REST API").

    Layer 1 passes each chip through normalize_skill(), which applies the
    alias map and direct taxonomy lookup.

    Returns
    -------
    (found_skills, skill_rows)
        found_skills : set of canonical skill names found in this layer
        skill_rows   : list of skill row dicts
    """
    found: set[str] = set()
    rows: list[dict] = []

    raw_tags: str | None = job.get("category_tags")
    if not raw_tags:
        return found, rows

    job_id = job.get("job_id")
    role_cat = classify_role(job.get("job_title") or "")
    chips = [t.strip() for t in raw_tags.split(",") if t.strip()]

    for chip in chips:
        canonical = normalize_skill(chip)
        if canonical and canonical not in found:
            found.add(canonical)
            rows.append(_make_skill_row(job_id, canonical, "wuzzuf_tag", 1.0, role_cat))
            logger.debug("[L1] job=%s  tag=%r  → %s", job_id, chip, canonical)

    return found, rows


# ---------------------------------------------------------------------------
# Layer 2 — Regex scan (confidence = 0.95)
# ---------------------------------------------------------------------------

def _layer2_regex(job: dict, already_found: set[str]) -> tuple[set[str], list[dict]]:
    """
    Scan combined text (job_title + category_tags) against every canonical
    skill in the taxonomy using word-boundary regex.

    Ambiguous terms are gated by a ±60-char context window check.

    Parameters
    ----------
    job           : job dict
    already_found : skills already resolved in Layer 1 (skipped here)

    Returns
    -------
    (new_skills_found, skill_rows)
    """
    found: set[str] = set()
    rows: list[dict] = []
    job_id = job.get("job_id")
    role_cat = classify_role(job.get("job_title") or "")

    # Build combined source text for scanning
    title   = clean_text(job.get("job_title") or "")
    tags    = clean_text(job.get("category_tags") or "").replace(",", " ")
    text    = f"{title} {tags}"

    if not text.strip():
        return found, rows

    for skill in _ALL_SKILLS:
        if skill in already_found or skill in found:
            continue  # already captured — skip

        pattern = _get_regex(skill)
        match = pattern.search(text)
        if not match:
            continue

        # Ambiguous-term gate
        if not _context_check(text, match.start(), match.end(), skill):
            logger.debug(
                "[L2] job=%s  skill=%r  match found but FAILED context check. Skipped.",
                job_id, skill,
            )
            continue

        found.add(skill)
        rows.append(_make_skill_row(job_id, skill, "regex_match", 0.95, role_cat))
        logger.debug("[L2] job=%s  skill=%r  matched via regex.", job_id, skill)

    return found, rows


# ---------------------------------------------------------------------------
# Layer 3 — Fuzzy matching (confidence = raw_score / 100)
# ---------------------------------------------------------------------------

def _layer3_fuzzy(job: dict, already_found: set[str]) -> tuple[set[str], list[dict]]:
    """
    Fuzzy-match tokenized source text against the full skill taxonomy using
    RapidFuzz.

    Algorithm
    ---------
    1. Tokenize combined text (title + tags) into unigrams + bigrams.
    2. For each token, call rapidfuzz.process.extractOne() to find the
       best-matching canonical skill above FUZZY_THRESHOLD.
    3. Apply ambiguous-term context check (same window logic as Layer 2,
       but we re-scan the full text to find the actual match position).
    4. Deduplicate: skip any skill already found in L1 or L2.
    5. Skip any token whose best match score equals exactly 100 AND the
       lowercase token equals the lowercase canonical — this avoids double-
       counting skills that SHOULD have been caught in L2 (regex miss due to
       selector drift is a bug, not a fuzzy match success).

    Confidence score
    ----------------
    confidence = rapidfuzz_score / 100.0
    (So a 92-point match → 0.92 confidence.)

    False-positive mitigations
    --------------------------
    - FUZZY_THRESHOLD = 85 is deliberately high. This catches typos and
      transliterations without pulling in semantically unrelated words.
    - Short tokens (< 3 chars) are skipped entirely — too risky for fuzzy.
    - Ambiguous single-word terms still require context confirmation.
    - Perfect-score matches that duplicate L2 would be missed there only
      due to selector drift; we log a warning when we see them.

    Parameters
    ----------
    job           : job dict
    already_found : skills found in L1 + L2 (skipped)

    Returns
    -------
    (new_skills_found, skill_rows)
    """
    found: set[str] = set()
    rows: list[dict] = []
    job_id = job.get("job_id")
    role_cat = classify_role(job.get("job_title") or "")

    # Build combined text (same source as L2)
    title  = clean_text(job.get("job_title") or "")
    tags   = clean_text(job.get("category_tags") or "").replace(",", " ")
    text   = f"{title} {tags}"

    if not text.strip():
        return found, rows

    tokens = tokenize(text)

    for token in tokens:
        # ── Skip very short tokens — too ambiguous for fuzzy ─────────────────
        if len(token) < 3:
            continue

        # ── Run fuzzy extraction against all canonical skills ─────────────────
        result = rf_process.extractOne(
            token,
            _ALL_SKILLS,
            scorer=fuzz.WRatio,         # Weighted ratio: handles substrings + transpositions
            score_cutoff=FUZZY_THRESHOLD,
        )

        if result is None:
            continue  # No match above threshold

        best_match, raw_score, _ = result

        # ── Skip skills already found in L1 / L2 ─────────────────────────────
        if best_match in already_found or best_match in found:
            continue

        # ── Log a warning if fuzzy found a perfect score that L2 missed ───────
        if raw_score == 100:
            logger.warning(
                "[L3] job=%s  token=%r  → PERFECT fuzzy match to %r "
                "(score=100) — L2 regex should have caught this. "
                "Check SELECTOR_SKILL_TAGS / regex pattern for drift.",
                job_id, token, best_match,
            )

        # ── Ambiguous-term context gate ───────────────────────────────────────
        # Find where ``best_match`` appears in the source text (approx).
        # We use a simple substring search on the lowercased text since the
        # fuzzy match already confirmed similarity.
        context_start = text.lower().find(token.lower())
        if context_start == -1:
            context_start = 0
        context_end = context_start + len(token)

        if not _context_check(text, context_start, context_end, best_match):
            logger.debug(
                "[L3] job=%s  token=%r  → %r  FAILED context check (score=%.0f). Skipped.",
                job_id, token, best_match, raw_score,
            )
            continue

        # ── Accept the match ──────────────────────────────────────────────────
        confidence = round(raw_score / 100.0, 4)
        found.add(best_match)
        rows.append(_make_skill_row(job_id, best_match, "fuzzy_match", confidence, role_cat))
        logger.debug(
            "[L3] job=%s  token=%r  → %r  (score=%.0f, conf=%.4f)",
            job_id, token, best_match, raw_score, confidence,
        )

    return found, rows


# ---------------------------------------------------------------------------
# Public API — single-job extractor (pure, no I/O)
# ---------------------------------------------------------------------------

def extract_skills_for_job(job: dict) -> list[dict]:
    """
    Run all three extraction layers for a single job dict.

    This function is PURE — it performs no file I/O and has no side effects.
    Suitable for unit testing and incremental/resumable pipelines.

    Parameters
    ----------
    job : dict
        A job dict from card_parser.parse() — must contain at least
        "job_id", "job_title", and "category_tags".

    Returns
    -------
    list[dict]
        Skill rows (one per unique skill found). Empty list if no skills found.
    """
    all_rows: list[dict] = []
    all_found: set[str] = set()

    # Layer 1 — Wuzzuf tags
    l1_found, l1_rows = _layer1_tags(job)
    all_found.update(l1_found)
    all_rows.extend(l1_rows)

    # Layer 2 — Regex scan (skip skills already in L1)
    l2_found, l2_rows = _layer2_regex(job, already_found=all_found)
    all_found.update(l2_found)
    all_rows.extend(l2_rows)

    # Layer 3 — Fuzzy match (skip skills already in L1 + L2)
    l3_found, l3_rows = _layer3_fuzzy(job, already_found=all_found)
    all_found.update(l3_found)
    all_rows.extend(l3_rows)

    logger.info(
        "Extracted %d skill(s) for job_id=%s  [L1=%d L2=%d L3=%d]",
        len(all_rows),
        job.get("job_id", "?"),
        len(l1_rows), len(l2_rows), len(l3_rows),
    )
    return all_rows


# ---------------------------------------------------------------------------
# Public API — batch extractor (writes to CSV)
# ---------------------------------------------------------------------------

def extract_skills(jobs: list[dict]) -> list[dict]:
    """
    Run the full three-layer extraction pipeline over a list of job dicts.

    Writes all results to settings.EXTRACTED_SKILLS_CSV (appending if the
    file already exists). This is the ONLY function in the project that
    writes to extracted_skills.csv.

    Parameters
    ----------
    jobs : list[dict]
        List of job dicts as returned by card_parser.parse() /
        listing_scraper.scrape_all_categories().

    Returns
    -------
    list[dict]
        Flat list of all skill rows across all jobs.
    """
    _ensure_csv_header(settings.EXTRACTED_SKILLS_CSV)

    all_rows: list[dict] = []

    for job in jobs:
        job_rows = extract_skills_for_job(job)
        if job_rows:
            _append_skills_to_csv(job_rows, settings.EXTRACTED_SKILLS_CSV)
            all_rows.extend(job_rows)

    logger.info(
        "Skill extraction complete. %d skill rows from %d jobs → %s",
        len(all_rows), len(jobs), settings.EXTRACTED_SKILLS_CSV,
    )
    return all_rows
