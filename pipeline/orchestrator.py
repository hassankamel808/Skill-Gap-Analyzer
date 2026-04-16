"""
pipeline/orchestrator.py
─────────────────────────
Master workflow controller.  Supports two execution modes:

Scrape Mode  (--scrape)
    1. Launch Selenium driver via DriverManager.
    2. Paginate through Wuzzuf using ListingScraper.
    3. Parse each page with CardParser.
    4. Extract skills with SkillExtractor.
    5. Persist raw records to output/ as CSV + JSON.
    6. Save progress checkpoint via StateManager after every page.

Analysis-Only Mode  (--analyze)
    1. Load previously scraped records from output CSV/JSON.
    2. Run DemandScorer, GapAnalyzer, CooccurrenceAnalyzer.
    3. Write analysis artefacts to output/.

Usage
─────
    orch = Orchestrator(mode="scrape", query="data engineer")
    orch.run()

    orch = Orchestrator(mode="analyze")
    orch.run()
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

import pandas as pd

from analysis.cooccurrence import CooccurrenceAnalyzer
from analysis.demand_scorer import DemandScorer
from analysis.gap_analyzer import GapAnalyzer
from config.settings import settings
from extraction.skill_extractor import SkillExtractor
from parser.card_parser import CardParser
from pipeline.state_manager import StateManager

logger = logging.getLogger(__name__)

RunMode = Literal["scrape", "analyze"]

_RAW_CSV = "raw_jobs.csv"
_RAW_JSON = "raw_jobs.json"
_DEMAND_CSV = "demand_scores.csv"
_GAP_CSV = "gap_analysis.csv"
_COOCCURRENCE_CSV = "cooccurrence_top_pairs.csv"


class Orchestrator:
    """
    Master pipeline controller.

    Parameters
    ----------
    mode:
        ``"scrape"`` to run the full scrape + extract pipeline, or
        ``"analyze"`` to run analysis only on existing data.
    query:
        Search term passed to the scraper (only relevant in scrape mode).
    max_pages:
        Override for maximum pages to scrape.
    test_mode:
        When ``True``, scraper will only fetch 1 page; useful for CI.
    """

    def __init__(
        self,
        mode: RunMode = "scrape",
        query: str = "data engineer",
        max_pages: int | None = None,
        test_mode: bool = False,
    ) -> None:
        self._mode = mode
        self._query = query
        self._max_pages = 1 if test_mode else (max_pages or settings.scrape_max_pages)
        self._output_dir = settings.output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._state = StateManager()
        self._extractor = SkillExtractor()

    # ── Public API ────────────────────────────────────────────

    def run(self) -> None:
        """Execute the selected pipeline mode."""
        if self._mode == "scrape":
            self._run_scrape()
        elif self._mode == "analyze":
            self._run_analyze()
        else:
            raise ValueError(f"Unknown mode: {self._mode!r}")

    # ── Scrape mode ───────────────────────────────────────────

    def _run_scrape(self) -> None:
        # Import here to avoid heavy Selenium import at analysis-only startup
        from scraper.driver_manager import DriverManager
        from scraper.listing_scraper import ListingScraper

        checkpoint = self._state.load()
        start_page = checkpoint.get("last_page", 0)
        all_records: list[dict] = checkpoint.get("records", [])

        logger.info(
            "Scrape mode: query=%r, max_pages=%d, resuming from page %d.",
            self._query,
            self._max_pages,
            start_page,
        )

        with DriverManager() as driver:
            scraper = ListingScraper(driver)
            for page_idx, html in scraper.scrape(
                query=self._query,
                max_pages=self._max_pages,
                start_page=start_page,
            ):
                cards = CardParser(html).parse()
                for card in cards:
                    text = f"{card['title']} {card['description']}"
                    card["skills"] = self._extractor.extract(text)
                    all_records.append(card)

                self._state.save({"last_page": page_idx + 1, "records": all_records})
                logger.info("Page %d: %d cards accumulated so far.", page_idx, len(all_records))

        self._persist_records(all_records)
        logger.info("Scrape complete. %d total records saved.", len(all_records))

    # ── Analysis mode ─────────────────────────────────────────

    def _run_analyze(self) -> None:
        records = self._load_records()
        if not records:
            logger.error("No records found in %s – run scrape mode first.", self._output_dir)
            return

        logger.info("Analysis mode: %d records loaded.", len(records))

        demand_df = DemandScorer(records).score()
        gap_df = GapAnalyzer(records).analyze()
        cooc_df = CooccurrenceAnalyzer(records).top_pairs()

        demand_df.to_csv(self._output_dir / _DEMAND_CSV, index=False)
        gap_df.to_csv(self._output_dir / _GAP_CSV, index=False)
        cooc_df.to_csv(self._output_dir / _COOCCURRENCE_CSV, index=False)

        logger.info("Analysis artefacts written to %s.", self._output_dir)

    # ── IO helpers ────────────────────────────────────────────

    def _persist_records(self, records: list[dict]) -> None:
        df = pd.DataFrame(records)
        df.to_csv(self._output_dir / _RAW_CSV, index=False)
        with (self._output_dir / _RAW_JSON).open("w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2, default=str)

    def _load_records(self) -> list[dict]:
        json_path = self._output_dir / _RAW_JSON
        csv_path = self._output_dir / _RAW_CSV
        if json_path.exists():
            with json_path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        if csv_path.exists():
            return pd.read_csv(csv_path).to_dict(orient="records")
        return []
