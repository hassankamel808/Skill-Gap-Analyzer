"""
tests/test_parser.py
─────────────────────
Unit tests for parser.card_parser.CardParser.

These tests use a minimal HTML fixture that mirrors the Wuzzuf DOM
structure so that no real network requests are required.
"""

from __future__ import annotations

import pytest

from parser.card_parser import CardParser

# ── Fixtures ──────────────────────────────────────────────────────────────────

MINIMAL_CARD_HTML = """
<html>
<body>
  <article class="css-prepvj">
    <h2 class="css-m604qf">
      <a href="/jobs/p/1-Senior-Data-Engineer">Senior Data Engineer</a>
    </h2>
    <a class="css-17s97q8">Acme Corp</a>
    <span class="css-5wys0k">Cairo</span>
    <span class="css-5wys0k">Giza</span>
    <div class="css-4c4ojb">3 days ago</div>
    <div class="css-y4udm8">
      <a>Python</a>
      <a>Apache Spark</a>
    </div>
  </article>
</body>
</html>
"""

MULTI_CARD_HTML = MINIMAL_CARD_HTML + """
<html><body>
  <article class="css-prepvj">
    <h2 class="css-m604qf">
      <a href="/jobs/p/2-Junior-Backend-Developer">Junior Backend Developer</a>
    </h2>
    <a class="css-17s97q8">Beta Ltd</a>
    <span class="css-5wys0k">Alexandria</span>
    <div class="css-4c4ojb">1 day ago</div>
  </article>
</body></html>
"""

EMPTY_HTML = "<html><body></body></html>"


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestCardParserSingleCard:
    def setup_method(self) -> None:
        self.cards = CardParser(MINIMAL_CARD_HTML).parse()

    def test_returns_one_card(self) -> None:
        assert len(self.cards) == 1

    def test_title_extracted(self) -> None:
        assert self.cards[0]["title"] == "Senior Data Engineer"

    def test_company_extracted(self) -> None:
        assert self.cards[0]["company"] == "Acme Corp"

    def test_location_concatenated(self) -> None:
        assert self.cards[0]["location"] == "Cairo, Giza"

    def test_posted_date_extracted(self) -> None:
        assert "days ago" in self.cards[0]["posted_date"]

    def test_job_url_is_absolute(self) -> None:
        assert self.cards[0]["job_url"].startswith("https://wuzzuf.net")

    def test_description_extracted(self) -> None:
        assert "Python" in self.cards[0]["description"]
        assert "Apache Spark" in self.cards[0]["description"]

    def test_senior_seniority_inferred(self) -> None:
        assert self.cards[0]["seniority"] == "senior"


class TestCardParserSeniority:
    @pytest.mark.parametrize(
        "title, expected",
        [
            ("Junior Data Analyst", "entry"),
            ("Senior Machine Learning Engineer", "senior"),
            ("Lead Data Scientist", "lead"),
            ("Data Engineer", "mid"),  # default
            ("Intern – Data", "entry"),
            ("Staff Software Engineer", "senior"),
        ],
    )
    def test_seniority_inference(self, title: str, expected: str) -> None:
        assert CardParser._infer_seniority(title) == expected


class TestCardParserEdgeCases:
    def test_empty_page_returns_empty_list(self) -> None:
        cards = CardParser(EMPTY_HTML).parse()
        assert cards == []

    def test_multi_card_page(self) -> None:
        cards = CardParser(MULTI_CARD_HTML).parse()
        assert len(cards) >= 1
