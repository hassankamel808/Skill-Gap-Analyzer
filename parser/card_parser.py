"""
parser/card_parser.py
=====================
BeautifulSoup4 HTML parser for Wuzzuf listing page job cards.

Public API
----------
parse(html, source_category) -> list[dict]
    Parse a fully-rendered listing page HTML string and return a list of
    job dicts — one per card detected on the page.

parse_results_count(html) -> tuple[int, int, int] | None
    Extract the (showing_start, showing_end, total) integers from the
    "Showing X - Y of Z" counter element.

Each returned job dict contains exactly these keys (None if not found):
    job_id, job_title, job_url, company_name, location_raw, city,
    posted_date_raw, job_type, work_mode, experience_level,
    category_tags, source_category, scraped_at

Design rules
------------
- ALL field extractions are wrapped in try/except so that a single broken
  card or changed class name never crashes the entire page parse.
- Primary selectors from settings.py are tried first; stable fallbacks
  (href-based, structural) are tried second.
- HTML is parsed with the 'lxml' backend for speed; falls back to
  'html.parser' if lxml is unavailable.
- No network calls are made here — input is always a page_source string.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from config import settings

logger = logging.getLogger(__name__)

# Base URL used to absolutise relative hrefs (e.g. /jobs/p/...)
_BASE_URL = "https://wuzzuf.net"

# Regex: extract digits from "Showing 1 - 20 of 3405"
_RE_SHOWING = re.compile(
    r"Showing\s+(\d[\d,]*)\s*[-–]\s*(\d[\d,]*)\s+of\s+(\d[\d,]*)",
    re.IGNORECASE,
)

# Regex to pull job_id from job URL slug:
# e.g. /jobs/p/abc123xyz-senior-python-developer-... → abc123xyz
_RE_JOB_ID = re.compile(r"/(?:jobs/p|internship)/([^-/]+)")

# Known experience-level tokens used for fuzzy identification when the
# dedicated selector fails.
_EXPERIENCE_TOKENS = {
    "entry level", "junior", "fresh grad", "experienced",
    "manager", "senior management", "director", "c-level",
    "internship", "student",
}

# known job-type tokens (lowercase)
_JOB_TYPE_TOKENS = {"full time", "part time", "internship", "contract", "freelance"}

# Known work-mode tokens (lowercase)
_WORK_MODE_TOKENS = {"on-site", "on site", "remote", "hybrid"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_soup(html: str) -> BeautifulSoup:
    """Return a BeautifulSoup object, preferring lxml for speed."""
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:  # noqa: BLE001
        return BeautifulSoup(html, "html.parser")


def _text(tag: Tag | None) -> str | None:
    """
    Return stripped inner text of a BS4 Tag, or None if tag is None/empty.
    Collapses internal whitespace and strips the leading "·" bullet Wuzzuf
    uses on skill/category chips.
    """
    if tag is None:
        return None
    raw = tag.get_text(separator=" ", strip=True)
    raw = re.sub(r"\s+", " ", raw).strip(" ·\u00b7\u2022\u25cf")
    return raw or None


def _abs_url(href: str | None) -> str | None:
    """Convert a relative href to an absolute URL, or return None."""
    if not href:
        return None
    href = href.strip()
    if href.startswith("http"):
        return href
    return urljoin(_BASE_URL, href)


def _extract_job_id(url: str | None) -> str | None:
    """Extract the short job-id token from a Wuzzuf job URL."""
    if not url:
        return None
    m = _RE_JOB_ID.search(url)
    return m.group(1) if m else None


def _extract_city(location_raw: str | None) -> str | None:
    """
    Extract the primary city from a raw location string.

    Wuzzuf formats location as one of:
      "Cairo, Egypt"
      "Nasr City, Cairo, Egypt"
      "Mansoura, Dakahlia, Egypt"

    Strategy: split on ", ", drop "Egypt" suffix, and return the LAST
    remaining token (which is the governorate/city in Wuzzuf's hierarchy).

    Examples
    --------
    "Nasr City, Cairo, Egypt" → "Cairo"
    "Cairo, Egypt"            → "Cairo"
    "Remote"                  → "Remote"
    """
    if not location_raw:
        return None
    parts = [p.strip() for p in location_raw.split(",")]
    # Drop trailing "Egypt"
    parts = [p for p in parts if p.lower() not in ("egypt", "")]
    if not parts:
        return None
    return parts[-1]


def _find_card_title_link(card: Tag) -> Tag | None:
    """
    Locate the job-title anchor element inside a card using primary then
    fallback selectors.

    Primary : settings.SELECTOR_JOB_TITLE   (h2.css-m604qf a)
    Fallback: href-based — any <a> whose href contains /jobs/p/ or /internship/
    """
    # Primary
    el = card.select_one(settings.SELECTOR_JOB_TITLE)
    if el and el.get("href"):
        return el

    # Fallback — structural: find any <h2> child anchor with a job URL
    for a in card.find_all("a", href=True):
        href = a["href"]
        if "/jobs/p/" in href or "/internship/" in href:
            return a

    return None


def _find_skill_tags(card: Tag) -> list[str]:
    """
    Collect skill/category chip texts from a card.

    Strategy (primary → fallback):
    1. settings.SELECTOR_SKILL_TAGS   (div.css-y3uu2g a)
    2. Any <a> whose href matches the Wuzzuf /a/...-Jobs-in-Egypt pattern
       but is NOT a job detail URL and NOT a navigation link.

    Applies settings.MAX_SKILL_TAG_LENGTH guard to discard CSS bleed-through.
    """
    tags: list[str] = []
    seen: set[str] = set()

    def _add(text: str | None) -> None:
        if not text:
            return
        if len(text) > settings.MAX_SKILL_TAG_LENGTH:
            return          # CSS class string leaking — discard
        if text.lower() in seen:
            return
        seen.add(text.lower())
        tags.append(text)

    # Primary selector
    for el in card.select(settings.SELECTOR_SKILL_TAGS):
        _add(_text(el))

    if not tags:
        # Fallback: href-pattern match
        for a in card.find_all("a", href=True):
            href = a["href"]
            if "/a/" in href and "-Jobs-in-Egypt" in href:
                _add(_text(a))

    return tags


def _classify_badges(card: Tag) -> tuple[str | None, str | None, str | None]:
    """
    Extract (job_type, work_mode, experience_level) from badge chips.

    Wuzzuf renders three flavours of badges in a card, each styled differently
    but containing short keyword tokens. This function collects ALL small
    chip-like anchors, then routes each token to the right bucket.

    Returns
    -------
    tuple of (job_type | None, work_mode | None, experience_level | None)
    """
    job_type: str | None = None
    work_mode: str | None = None
    experience_level: str | None = None

    # Collect text from all <a> or <span> elements with short text inside the card.
    # A "chip" is any short-text element (< 60 chars) that is NOT the title or company.
    candidates: list[str] = []

    for el in card.find_all(["a", "span"]):
        t = _text(el)
        if t and 1 < len(t) < 60:
            candidates.append(t)

    for token in candidates:
        tl = token.lower()
        if job_type is None and any(jt in tl for jt in _JOB_TYPE_TOKENS):
            job_type = token
        elif work_mode is None and any(wm in tl for wm in _WORK_MODE_TOKENS):
            work_mode = token
        elif experience_level is None and any(et in tl for et in _EXPERIENCE_TOKENS):
            experience_level = token

    return job_type, work_mode, experience_level


# ---------------------------------------------------------------------------
# Public: parse results counter
# ---------------------------------------------------------------------------

def parse_results_count(html: str) -> tuple[int, int, int] | None:
    """
    Extract pagination metadata from the "Showing X - Y of Z" counter.

    Parameters
    ----------
    html : str
        Full page_source HTML of a listing page.

    Returns
    -------
    tuple[int, int, int] | None
        (showing_start, showing_end, total_results) or None if not found.

    Examples
    --------
    "Showing 1 - 20 of 3405" → (1, 20, 3405)
    "Showing 21 - 40 of 3405" → (21, 40, 3405)
    """
    soup = _make_soup(html)

    # ── Try the dedicated CSS selector first ─────────────────────────────────
    el = soup.select_one(settings.SELECTOR_RESULTS_COUNT)
    if el:
        m = _RE_SHOWING.search(el.get_text())
        if m:
            return (
                int(m.group(1).replace(",", "")),
                int(m.group(2).replace(",", "")),
                int(m.group(3).replace(",", "")),
            )

    # ── Full-text fallback — scan entire body for the pattern ─────────────────
    body_text = soup.get_text(separator=" ")
    m = _RE_SHOWING.search(body_text)
    if m:
        return (
            int(m.group(1).replace(",", "")),
            int(m.group(2).replace(",", "")),
            int(m.group(3).replace(",", "")),
        )

    logger.debug("Results count element not found in page HTML.")
    return None


# ---------------------------------------------------------------------------
# Public: parse job cards
# ---------------------------------------------------------------------------

def parse(html: str, source_category: str = "") -> list[dict]:
    """
    Parse all job cards from a listing page HTML string.

    Parameters
    ----------
    html            : str
        Fully-rendered page_source from Selenium.
    source_category : str
        The category label (e.g. "IT-Software-Development") that this page
        belongs to — stored as metadata on every returned job dict.

    Returns
    -------
    list[dict]
        One dict per job card found. Missing fields are None.
        Returns an empty list if no cards are found.
    """
    soup = _make_soup(html)
    scraped_at = datetime.now(tz=timezone.utc).isoformat()

    # ── Locate card container elements ────────────────────────────────────────
    cards = soup.select(settings.SELECTOR_JOB_CARD)
    if not cards:
        # Fallback: find any element that is an ancestor of a job-title link
        logger.debug(
            "Primary card selector '%s' returned 0 results — using fallback.",
            settings.SELECTOR_JOB_CARD,
        )
        title_anchors = soup.select(settings.FALLBACK_JOB_TITLE_ATTR)
        # Walk up from each title anchor to find the shared card wrapper
        card_set: list[Tag] = []
        seen_ids: set[int] = set()
        for a in title_anchors:
            card = a
            # Walk up until we find a sibling-bearing parent
            for _ in range(8):
                parent = card.parent
                if parent is None:
                    break
                siblings = [
                    c for c in parent.children
                    if isinstance(c, Tag)
                    and c is not card
                    and c.find("a", href=re.compile(r"/jobs/p/|/internship/"))
                ]
                if siblings:
                    break
                card = parent
            if id(card) not in seen_ids:
                seen_ids.add(id(card))
                card_set.append(card)
        cards = card_set

    if not cards:
        logger.warning(
            "No job cards found on listing page (source: %s). "
            "Selector drift likely — check SELECTOR_JOB_CARD in settings.",
            source_category,
        )
        return []

    logger.debug("Found %d job card(s) on listing page (%s).", len(cards), source_category)

    jobs: list[dict] = []
    for card in cards:
        job = _parse_single_card(card, source_category, scraped_at)
        if job is not None:
            jobs.append(job)

    return jobs


# ---------------------------------------------------------------------------
# Internal: parse one card element into a job dict
# ---------------------------------------------------------------------------

def _parse_single_card(
    card: Tag,
    source_category: str,
    scraped_at: str,
) -> dict | None:
    """
    Extract all card-level fields from a single card Tag.

    Returns None only if the card has no detectable job title (i.e. it is
    not a genuine job card — e.g. an ad or injected promo widget).
    All other missing fields are represented as None.
    """
    # ── Job title + URL ───────────────────────────────────────────────────────
    title_el = _find_card_title_link(card)

    if title_el is None:
        logger.debug("Card skipped — no job title anchor found.")
        return None

    job_title = _text(title_el)
    if not job_title or len(job_title) < settings.MIN_JOB_TITLE_LENGTH:
        logger.debug("Card skipped — title too short or empty: %r", job_title)
        return None

    job_url = _abs_url(title_el.get("href"))
    job_id = _extract_job_id(job_url)

    # ── Company name ──────────────────────────────────────────────────────────
    company_name: str | None = None
    try:
        el = card.select_one(settings.SELECTOR_COMPANY)
        if el:
            company_name = _text(el)
        if not company_name:
            # Fallback: first <a> with /careers/ or /jobs/careers/ in href
            for a in card.find_all("a", href=True):
                if "/careers/" in a["href"] and "/jobs/p/" not in a["href"]:
                    company_name = _text(a)
                    if company_name:
                        break
    except Exception as exc:  # noqa: BLE001
        logger.debug("company_name extraction error: %s", exc)

    # ── Location ──────────────────────────────────────────────────────────────
    location_raw: str | None = None
    try:
        el = card.select_one(settings.SELECTOR_LOCATION)
        if el:
            location_raw = _text(el)
        if not location_raw:
            # Fallback: text node directly after company anchor containing a comma
            for el in card.find_all(["span", "div"]):
                t = _text(el)
                if t and "," in t and "egypt" in t.lower() and len(t) < 80:
                    location_raw = t
                    break
    except Exception as exc:  # noqa: BLE001
        logger.debug("location_raw extraction error: %s", exc)

    city = _extract_city(location_raw)

    # ── Posted date (relative text) ────────────────────────────────────────────
    posted_date_raw: str | None = None
    try:
        el = card.select_one(settings.SELECTOR_POSTED_DATE)
        if el:
            posted_date_raw = _text(el)
        if not posted_date_raw:
            # Fallback: look for any element containing "ago" or "hour" or "day"
            date_re = re.compile(
                r"(\d+\s+(?:second|minute|hour|day|week|month|year)s?\s+ago|just now|today)",
                re.IGNORECASE,
            )
            for el in card.find_all(["span", "div", "time"]):
                t = _text(el)
                if t and date_re.search(t) and len(t) < 40:
                    posted_date_raw = t
                    break
    except Exception as exc:  # noqa: BLE001
        logger.debug("posted_date_raw extraction error: %s", exc)

    # ── Badges: job_type, work_mode, experience_level ─────────────────────────
    job_type: str | None = None
    work_mode: str | None = None
    experience_level: str | None = None
    try:
        # Primary selector approach
        jt_el = card.select_one(settings.SELECTOR_JOB_TYPE_BADGES)
        wm_el = card.select_one(settings.SELECTOR_WORK_MODE_BADGES)
        exp_el = card.select_one(settings.SELECTOR_EXPERIENCE_LEVEL)
        job_type = _text(jt_el)
        work_mode = _text(wm_el)
        experience_level = _text(exp_el)

        # Fallback: token-based classification of all badge-like elements
        if not any([job_type, work_mode, experience_level]):
            job_type, work_mode, experience_level = _classify_badges(card)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Badge extraction error: %s", exc)

    # ── Skill / category tags ─────────────────────────────────────────────────
    category_tags: list[str] = []
    try:
        category_tags = _find_skill_tags(card)
    except Exception as exc:  # noqa: BLE001
        logger.debug("category_tags extraction error: %s", exc)

    # ── Assemble final dict ───────────────────────────────────────────────────
    return {
        "job_id":           job_id,
        "job_title":        job_title,
        "job_url":          job_url,
        "company_name":     company_name,
        "location_raw":     location_raw,
        "city":             city,
        "posted_date_raw":  posted_date_raw,
        "job_type":         job_type,
        "work_mode":        work_mode,
        "experience_level": experience_level,
        "category_tags":    ",".join(category_tags) if category_tags else None,
        "source_category":  source_category,
        "scraped_at":       scraped_at,
    }
