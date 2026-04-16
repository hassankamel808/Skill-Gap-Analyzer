"""
parser/card_parser.py
─────────────────────
Parses raw Wuzzuf job listing HTML (a full page source) into a list of
structured job-card dictionaries using BeautifulSoup 4.

Each returned dict contains:
    title       – job title string
    company     – company name string
    location    – city / location string
    seniority   – inferred seniority label (entry / mid / senior / lead)
    posted_date – raw "posted X days ago" text
    job_url     – absolute URL to the job detail page
    description – concatenated requirements text (if available on listing page)
"""

from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

_BASE_URL = "https://wuzzuf.net"

# Seniority keyword mappings (checked against title, lowercased)
_SENIORITY_PATTERNS: dict[str, list[str]] = {
    "lead": ["lead", "head of", "principal", "director", "vp"],
    "senior": ["senior", "sr.", "sr ", "staff"],
    "mid": ["mid", "medior", "experienced", "ii", "iii"],
    "entry": ["junior", "jr.", "jr ", "intern", "trainee", "associate", "entry"],
}


class CardParser:
    """
    Transforms a page of raw Wuzzuf HTML into job-card dicts.

    Parameters
    ----------
    html:
        Full ``driver.page_source`` string for one results page.
    """

    def __init__(self, html: str) -> None:
        self._soup = BeautifulSoup(html, "lxml")

    # ── Public API ────────────────────────────────────────────

    def parse(self) -> list[dict[str, Any]]:
        """Return a list of structured job-card dicts from the page HTML."""
        cards = self._soup.select("article.css-prepvj")
        logger.debug("Found %d job cards on page.", len(cards))
        results = []
        for card in cards:
            try:
                results.append(self._parse_card(card))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipping card due to parse error: %s", exc)
        return results

    # ── Private helpers ───────────────────────────────────────

    def _parse_card(self, card: Tag) -> dict[str, Any]:
        title_tag = card.select_one("h2.css-m604qf a")
        title = title_tag.get_text(strip=True) if title_tag else ""
        job_url = _BASE_URL + title_tag["href"] if title_tag and title_tag.get("href") else ""

        company_tag = card.select_one("a.css-17s97q8")
        company = company_tag.get_text(strip=True) if company_tag else ""

        location_tags = card.select("span.css-5wys0k")
        location = ", ".join(t.get_text(strip=True) for t in location_tags)

        date_tag = card.select_one("div.css-4c4ojb")
        posted_date = date_tag.get_text(strip=True) if date_tag else ""

        description_tags = card.select("div.css-y4udm8 a")
        description = " ".join(t.get_text(strip=True) for t in description_tags)

        seniority = self._infer_seniority(title)

        return {
            "title": title,
            "company": company,
            "location": location,
            "seniority": seniority,
            "posted_date": posted_date,
            "job_url": job_url,
            "description": description,
        }

    @staticmethod
    def _infer_seniority(title: str) -> str:
        """Heuristically map a job title to a seniority bucket."""
        lower = title.lower()
        for level, keywords in _SENIORITY_PATTERNS.items():
            if any(kw in lower for kw in keywords):
                return level
        return "mid"  # default assumption
