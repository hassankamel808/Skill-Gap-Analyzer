"""
tests/test_card_parser.py
=========================
Unit tests for parser/card_parser.py using mock HTML fixtures.

The test HTML is crafted to mirror the real Wuzzuf listing page structure
observed during live DOM inspection, but contains no real personal data.

Run with:
    pytest tests/test_card_parser.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make sure the project root is on the path when running directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from parser import card_parser

# ---------------------------------------------------------------------------
# Mock HTML fixtures
# ---------------------------------------------------------------------------

# ── Single card — fully populated (all fields present) ─────────────────────
MOCK_CARD_FULL = """
<div class="css-1gatmva">
  <div>
    <h2 class="css-m604qf">
      <a href="/jobs/p/abc123xyz-senior-python-developer-techcorp-cairo-egypt">
        Senior Python Developer
      </a>
    </h2>
    <a class="css-17s97q8" href="/jobs/careers/TechCorp-Egypt-12345">
      TechCorp
    </a>
    <span class="css-5wys0k">New Cairo, Cairo, Egypt</span>
    <div class="css-do6t5g">3 hours ago</div>
    <div>
      <a class="css-n2jc43" href="/a/Full-Time-Jobs-in-Egypt">Full Time</a>
      <a class="css-bcbr8g" href="/a/Remote-Jobs-in-Egypt">Remote</a>
      <a class="css-y4udm8" href="/a/Experienced-Jobs-in-Egypt">Experienced</a>
    </div>
    <div class="css-y3uu2g">
      <a href="/a/IT-Software-Development-Jobs-in-Egypt?filters[country][0]=Egypt">
        · IT/Software Development
      </a>
      <a href="/a/Python-Jobs-in-Egypt?filters[country][0]=Egypt">
        · Python
      </a>
      <a href="/a/Django-Jobs-in-Egypt?filters[country][0]=Egypt">
        · Django
      </a>
      <a href="/a/REST-API-Jobs-in-Egypt?filters[country][0]=Egypt">
        · REST API
      </a>
    </div>
  </div>
</div>
"""

# ── Single card — minimal (only title + URL, everything else absent) ─────────
MOCK_CARD_MINIMAL = """
<div class="css-1gatmva">
  <h2 class="css-m604qf">
    <a href="/jobs/p/def456uvw-junior-developer-startup-giza-egypt">
      Junior Developer
    </a>
  </h2>
</div>
"""

# ── Single card — internship URL scheme ──────────────────────────────────────
MOCK_CARD_INTERNSHIP = """
<div class="css-1gatmva">
  <h2 class="css-m604qf">
    <a href="/internship/ghi789rst-software-intern-bigco-cairo-egypt">
      Software Engineering Intern
    </a>
  </h2>
  <a class="css-17s97q8" href="/jobs/careers/BigCo-Egypt-99999">BigCo</a>
  <span class="css-5wys0k">Cairo, Egypt</span>
  <div class="css-do6t5g">1 day ago</div>
  <a class="css-n2jc43" href="/a/Internship-Jobs-in-Egypt">Internship</a>
  <a class="css-bcbr8g" href="/a/On-Site-Jobs-in-Egypt">On-site</a>
</div>
"""

# ── Card with no title — should be skipped ───────────────────────────────────
MOCK_CARD_NO_TITLE = """
<div class="css-1gatmva">
  <a class="css-17s97q8" href="/jobs/careers/Orphan-Egypt-00000">Orphan Co</a>
  <span class="css-5wys0k">Alexandria, Egypt</span>
</div>
"""

# ── Full listing page HTML containing two cards + results counter ─────────────
MOCK_PAGE_TWO_CARDS = f"""
<!DOCTYPE html>
<html>
<body>
  <div class="css-1d2q07k">Showing 1 - 2 of 3405</div>
  {MOCK_CARD_FULL}
  {MOCK_CARD_MINIMAL}
</body>
</html>
"""

# ── Full listing page with NO results counter ─────────────────────────────────
MOCK_PAGE_NO_COUNTER = f"""
<!DOCTYPE html>
<html>
<body>
  {MOCK_CARD_FULL}
</body>
</html>
"""

# ── Last page (partial) — fewer than 20 cards ─────────────────────────────────
MOCK_PAGE_LAST = """
<!DOCTYPE html>
<html>
<body>
  <div class="css-1d2q07k">Showing 3401 - 3405 of 3405</div>
  <div class="css-1gatmva">
    <h2 class="css-m604qf">
      <a href="/jobs/p/zzzlast-last-job-cairo-egypt">Last Job</a>
    </h2>
  </div>
</body>
</html>
"""

# ── Page with a CSS class bleed (long CSS string in an anchor) — must be filtered
MOCK_CARD_CSS_BLEED = """
<div class="css-1gatmva">
  <h2 class="css-m604qf">
    <a href="/jobs/p/bleed001-css-bleed-test-cairo-egypt">CSS Bleed Test Job</a>
  </h2>
  <div class="css-y3uu2g">
    <a href="/a/IT-Software-Development-Jobs-in-Egypt?filters[country][0]=Egypt">
      .css-1y7kjgo{display:-webkit-inline-box;display:-webkit-inline-flex;font-size:12px;padding:0 12px;border:1px solid transparent;border-radius:2px;min-width:80px;transition:color .2s ease}
    </a>
    <a href="/a/Python-Jobs-in-Egypt?filters[country][0]=Egypt">Python</a>
  </div>
</div>
"""

# ── Empty page (no cards at all) ─────────────────────────────────────────────
MOCK_PAGE_EMPTY = """
<!DOCTYPE html>
<html><body><p>No results found.</p></body></html>
"""


# ---------------------------------------------------------------------------
# Tests: parse_results_count
# ---------------------------------------------------------------------------

class TestParseResultsCount:
    def test_parses_standard_counter(self):
        result = card_parser.parse_results_count(MOCK_PAGE_TWO_CARDS)
        assert result == (1, 2, 3405)

    def test_parses_last_page_counter(self):
        result = card_parser.parse_results_count(MOCK_PAGE_LAST)
        assert result == (3401, 3405, 3405)

    def test_returns_none_when_no_counter(self):
        result = card_parser.parse_results_count(MOCK_PAGE_NO_COUNTER)
        assert result is None

    def test_fallback_text_scan_finds_counter_outside_selector(self):
        # Counter buried in a different element — full-text fallback must find it
        html = "<html><body><p>Showing 21 - 40 of 500</p></body></html>"
        result = card_parser.parse_results_count(html)
        assert result == (21, 40, 500)

    def test_handles_comma_separated_numbers(self):
        html = "<html><body><p>Showing 1 - 20 of 1,234</p></body></html>"
        result = card_parser.parse_results_count(html)
        assert result == (1, 20, 1234)

    def test_returns_none_on_empty_page(self):
        result = card_parser.parse_results_count(MOCK_PAGE_EMPTY)
        assert result is None


# ---------------------------------------------------------------------------
# Tests: parse — field extraction
# ---------------------------------------------------------------------------

class TestParseFullCard:
    """Tests against a fully-populated card fixture."""

    def setup_method(self):
        self.jobs = card_parser.parse(
            f"<html><body>{MOCK_CARD_FULL}</body></html>",
            source_category="IT-Software-Development",
        )

    def test_returns_one_job(self):
        assert len(self.jobs) == 1

    def test_job_title(self):
        assert self.jobs[0]["job_title"] == "Senior Python Developer"

    def test_job_url_is_absolute(self):
        url = self.jobs[0]["job_url"]
        assert url.startswith("https://wuzzuf.net")
        assert "/jobs/p/abc123xyz" in url

    def test_job_id_extracted_from_url(self):
        assert self.jobs[0]["job_id"] == "abc123xyz"

    def test_company_name(self):
        assert self.jobs[0]["company_name"] == "TechCorp"

    def test_location_raw(self):
        assert self.jobs[0]["location_raw"] == "New Cairo, Cairo, Egypt"

    def test_city_extracted(self):
        # "New Cairo, Cairo, Egypt" → "Cairo"
        assert self.jobs[0]["city"] == "Cairo"

    def test_posted_date_raw(self):
        assert self.jobs[0]["posted_date_raw"] == "3 hours ago"

    def test_job_type(self):
        assert self.jobs[0]["job_type"] == "Full Time"

    def test_work_mode(self):
        assert self.jobs[0]["work_mode"] == "Remote"

    def test_experience_level(self):
        assert self.jobs[0]["experience_level"] == "Experienced"

    def test_category_tags_present(self):
        tags_str = self.jobs[0]["category_tags"]
        assert tags_str is not None
        tags = tags_str.split(",")
        assert len(tags) >= 2

    def test_category_tags_contains_python(self):
        assert "Python" in self.jobs[0]["category_tags"]

    def test_category_tags_contains_django(self):
        assert "Django" in self.jobs[0]["category_tags"]

    def test_source_category(self):
        assert self.jobs[0]["source_category"] == "IT-Software-Development"

    def test_scraped_at_is_iso_string(self):
        scraped_at = self.jobs[0]["scraped_at"]
        assert "T" in scraped_at               # ISO 8601 format
        assert scraped_at.endswith("+00:00")   # UTC timezone


class TestParseMinimalCard:
    """Tests against a card with only title + URL (all other fields absent)."""

    def setup_method(self):
        self.jobs = card_parser.parse(
            f"<html><body>{MOCK_CARD_MINIMAL}</body></html>",
            source_category="IT-Software-Development",
        )

    def test_returns_one_job(self):
        assert len(self.jobs) == 1

    def test_job_title(self):
        assert self.jobs[0]["job_title"] == "Junior Developer"

    def test_job_id(self):
        assert self.jobs[0]["job_id"] == "def456uvw"

    def test_missing_company_is_none(self):
        assert self.jobs[0]["company_name"] is None

    def test_missing_location_is_none(self):
        assert self.jobs[0]["location_raw"] is None
        assert self.jobs[0]["city"] is None

    def test_missing_date_is_none(self):
        assert self.jobs[0]["posted_date_raw"] is None

    def test_missing_badges_are_none_or_token(self):
        # job_type and work_mode have no matching tokens in this card
        assert self.jobs[0]["job_type"] is None
        assert self.jobs[0]["work_mode"] is None
        # experience_level: the fallback classifier may legitimately pick up
        # "junior" from the title text. The guarantee is that the value is
        # either None or a short string (not a crash, not a CSS blob).
        exp = self.jobs[0]["experience_level"]
        assert exp is None or (isinstance(exp, str) and len(exp) < 60)

    def test_missing_tags_is_none(self):
        assert self.jobs[0]["category_tags"] is None


class TestParseInternshipCard:
    """Tests for internship URL scheme (/internship/ instead of /jobs/p/)."""

    def setup_method(self):
        self.jobs = card_parser.parse(
            f"<html><body>{MOCK_CARD_INTERNSHIP}</body></html>",
            source_category="IT-Software-Development",
        )

    def test_returns_one_job(self):
        assert len(self.jobs) == 1

    def test_job_title(self):
        assert self.jobs[0]["job_title"] == "Software Engineering Intern"

    def test_job_url_contains_internship(self):
        assert "/internship/" in self.jobs[0]["job_url"]

    def test_job_id_extracted(self):
        assert self.jobs[0]["job_id"] == "ghi789rst"

    def test_city_for_simple_location(self):
        # "Cairo, Egypt" → "Cairo"
        assert self.jobs[0]["city"] == "Cairo"

    def test_job_type_is_internship(self):
        assert self.jobs[0]["job_type"] == "Internship"

    def test_work_mode_is_onsite(self):
        assert self.jobs[0]["work_mode"] == "On-site"


class TestParseNoTitleCard:
    """A card with no title anchor should be silently skipped."""

    def test_card_without_title_is_skipped(self):
        jobs = card_parser.parse(
            f"<html><body>{MOCK_CARD_NO_TITLE}</body></html>",
        )
        assert jobs == []


class TestMultipleCardsOnPage:
    """Full listing page with two cards."""

    def setup_method(self):
        self.jobs = card_parser.parse(MOCK_PAGE_TWO_CARDS, source_category="IT-Software-Development")

    def test_two_jobs_returned(self):
        assert len(self.jobs) == 2

    def test_first_job_title(self):
        assert self.jobs[0]["job_title"] == "Senior Python Developer"

    def test_second_job_title(self):
        assert self.jobs[1]["job_title"] == "Junior Developer"

    def test_both_have_correct_source_category(self):
        for job in self.jobs:
            assert job["source_category"] == "IT-Software-Development"


class TestEmptyPage:
    def test_empty_page_returns_empty_list(self):
        jobs = card_parser.parse(MOCK_PAGE_EMPTY)
        assert jobs == []


# ---------------------------------------------------------------------------
# Tests: CSS bleed-through guard
# ---------------------------------------------------------------------------

class TestCssBleedGuard:
    """Long CSS class strings must not be stored as skill tags."""

    def setup_method(self):
        self.jobs = card_parser.parse(
            f"<html><body>{MOCK_CARD_CSS_BLEED}</body></html>",
        )

    def test_returns_one_job(self):
        assert len(self.jobs) == 1

    def test_css_string_not_in_tags(self):
        tags = self.jobs[0]["category_tags"] or ""
        # The long CSS class string must be filtered out
        assert "webkit-inline" not in tags
        assert "border-radius" not in tags

    def test_real_skill_python_still_captured(self):
        tags = self.jobs[0]["category_tags"] or ""
        assert "Python" in tags


# ---------------------------------------------------------------------------
# Tests: city extraction edge cases
# ---------------------------------------------------------------------------

class TestExtractCity:
    """Tests for _extract_city via the public parse interface."""

    def _parse_location(self, location: str) -> str | None:
        """Build a minimal card with the given location and parse its city."""
        html = f"""
        <div class="css-1gatmva">
          <h2 class="css-m604qf">
            <a href="/jobs/p/test001-test-job-cairo-egypt">Test Job</a>
          </h2>
          <span class="css-5wys0k">{location}</span>
        </div>
        """
        jobs = card_parser.parse(f"<html><body>{html}</body></html>")
        return jobs[0]["city"] if jobs else None

    def test_city_from_district_city_country(self):
        assert self._parse_location("Nasr City, Cairo, Egypt") == "Cairo"

    def test_city_from_city_country(self):
        assert self._parse_location("Cairo, Egypt") == "Cairo"

    def test_city_from_governorate_country(self):
        assert self._parse_location("Mansoura, Dakahlia, Egypt") == "Dakahlia"

    def test_remote_location(self):
        assert self._parse_location("Remote") == "Remote"

    def test_alexandria(self):
        assert self._parse_location("Alexandria, Egypt") == "Alexandria"


# ---------------------------------------------------------------------------
# Tests: helper function _text (indirect via parse)
# ---------------------------------------------------------------------------

class TestTextNormalization:
    """Verify that leading/trailing bullet chars and whitespace are stripped."""

    def test_skill_tag_bullet_stripped(self):
        html = f"<html><body>{MOCK_CARD_FULL}</body></html>"
        jobs = card_parser.parse(html)
        tags = jobs[0]["category_tags"].split(",")
        for tag in tags:
            assert not tag.startswith("·"), f"Bullet not stripped from tag: {tag!r}"
            assert tag == tag.strip(), f"Whitespace not stripped: {tag!r}"


# ---------------------------------------------------------------------------
# Tests: parse_results_count — end-of-pagination signals
# ---------------------------------------------------------------------------

class TestEndOfPagination:
    def test_last_page_detected_when_end_equals_total(self):
        result = card_parser.parse_results_count(MOCK_PAGE_LAST)
        assert result is not None
        _, showing_end, total = result
        assert showing_end >= total  # pagination-end signal


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
