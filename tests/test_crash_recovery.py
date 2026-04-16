"""
tests/test_crash_recovery.py
==============================
Integration tests for mid-run crash recovery (Step 14).

These tests verify the pipeline can resume from exactly the last saved
checkpoint WITHOUT:
  - Re-scraping already-completed pages
  - Writing duplicate job_ids to raw_jobs.csv
  - Skipping any pages that were not yet completed

No real browser is launched. The scraper's navigation and card parsing
are mocked at module level to return deterministic fake data, while the
real state_manager, CSV-writing, and pagination-index logic are exercised
against a temporary directory.

Run with:
    pytest tests/test_crash_recovery.py -v
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from config import settings
from pipeline import state_manager


# ===========================================================================
# Helpers
# ===========================================================================

def _build_state(
    category_label: str,
    last_completed_page: int,
    jobs_collected: int,
    total_results: int = 100,
    total_pages: int = 5,
    cat_status: str = "in_progress",
    all_categories: list | None = None,
) -> dict:
    """Build a realistic state dict simulating a crash mid-run."""
    all_categories = all_categories or settings.TARGET_CATEGORIES
    cats = {}
    for i, cat in enumerate(all_categories):
        if cat["label"] == category_label:
            cats[cat["label"]] = {
                "status": cat_status,
                "total_results": total_results,
                "total_pages": total_pages,
                "last_completed_page": last_completed_page,
                "jobs_collected": jobs_collected,
            }
        else:
            cats[cat["label"]] = {
                "status": "pending",
                "total_results": None,
                "total_pages": None,
                "last_completed_page": -1,
                "jobs_collected": 0,
            }
    return {
        "run_id": "20260416_crash_test",
        "status": "in_progress",
        "phase": "listing_scrape",
        "total_jobs_collected": jobs_collected,
        "categories": cats,
        "last_updated": datetime.now(tz=timezone.utc).isoformat(),
    }


def _write_csv(path: Path, n_jobs: int, category: str = "IT-Software-Development") -> list[dict]:
    """Write N fake jobs to CSV and return them."""
    fields = [
        "job_id", "job_title", "job_url", "company_name", "location_raw",
        "city", "posted_date_raw", "job_type", "work_mode", "experience_level",
        "category_tags", "source_category", "scraped_at",
    ]
    jobs = []
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for i in range(n_jobs):
            job = {f: "" for f in fields}
            job["job_id"] = f"crash_test_{i:04d}"
            job["job_title"] = f"Test Job {i}"
            job["source_category"] = category
            writer.writerow(job)
            jobs.append(job)
    return jobs


def _fake_page_jobs(page_index: int, n: int = 20, prefix: str = "page") -> list[dict]:
    """Return N fake job dicts representing one scraped page."""
    return [
        {
            "job_id":       f"{prefix}_p{page_index}_j{j:02d}",
            "job_title":    f"Job {page_index}-{j}",
            "job_url":      f"https://wuzzuf.net/jobs/p/{prefix}-p{page_index}-j{j}",
            "company_name": "TestCo",
            "location_raw": "Cairo, Egypt",
            "city":         "Cairo",
            "posted_date_raw": "1 day ago",
            "job_type":     "Full Time",
            "work_mode":    "Hybrid",
            "experience_level": "Experienced",
            "category_tags":"Python,Docker",
            "source_category": "IT-Software-Development",
            "scraped_at":   datetime.now(tz=timezone.utc).isoformat(),
        }
        for j in range(n)
    ]


# ===========================================================================
# Tests: state_manager
# ===========================================================================

class TestStateManager:
    """Core state_manager functions: load, save, reset, fresh state."""

    def test_load_returns_fresh_state_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "STATE_FILE", tmp_path / "state.json")
        state = state_manager.load_state()
        assert state["status"] == "in_progress"
        assert state["total_jobs_collected"] == 0
        assert "run_id" in state

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "STATE_FILE", tmp_path / "state.json")
        original = _build_state("IT-Software-Development", last_completed_page=2, jobs_collected=60)
        state_manager.save_state(original)
        loaded = state_manager.load_state()
        assert loaded["run_id"] == original["run_id"]
        assert loaded["total_jobs_collected"] == 60
        assert loaded["categories"]["IT-Software-Development"]["last_completed_page"] == 2
        assert loaded["categories"]["IT-Software-Development"]["status"] == "in_progress"

    def test_reset_deletes_file(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(settings, "STATE_FILE", state_file)
        state = _build_state("IT-Software-Development", 1, 20)
        state_manager.save_state(state)
        assert state_file.exists()
        state_manager.reset_state()
        assert not state_file.exists()

    def test_reset_safe_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "STATE_FILE", tmp_path / "state.json")
        # Must not raise even when file doesn't exist
        state_manager.reset_state()

    def test_load_fresh_after_reset(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "STATE_FILE", tmp_path / "state.json")
        state_manager.save_state(_build_state("IT-Software-Development", 5, 100))
        state_manager.reset_state()
        fresh = state_manager.load_state()
        assert fresh["total_jobs_collected"] == 0
        assert fresh["categories"] == {}

    def test_corrupt_json_returns_fresh_state(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(settings, "STATE_FILE", state_file)
        state_file.write_text("{ not valid json !!!", encoding="utf-8")
        state = state_manager.load_state()
        assert state["total_jobs_collected"] == 0

    def test_empty_file_returns_fresh_state(self, tmp_path, monkeypatch):
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(settings, "STATE_FILE", state_file)
        state_file.touch()
        state = state_manager.load_state()
        assert state["total_jobs_collected"] == 0

    def test_save_is_atomic_write(self, tmp_path, monkeypatch):
        """Verify no .state_tmp_ files are left behind after a successful save."""
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(settings, "STATE_FILE", state_file)
        state = _build_state("IT-Software-Development", 1, 20)
        state_manager.save_state(state)
        tmp_leftovers = list(tmp_path.glob(".state_tmp_*"))
        assert len(tmp_leftovers) == 0, f"Temp files not cleaned up: {tmp_leftovers}"


# ===========================================================================
# Tests: scraper resume logic (page-index arithmetic)
# ===========================================================================

class TestScraperResumePageIndex:
    """
    Tests for the page-index calculation in _scrape_category.

    Key invariant:
        start_page = last_completed_page + 1

    These tests mock _navigate_with_retry and card_parser.parse to avoid
    any browser dependency, while exercising real listing_scraper logic.
    """

    # Helper: monkeypatch all I/O-heavy bits of listing_scraper
    @staticmethod
    def _patch_scraper(monkeypatch, tmp_path, navigated_urls: list, page_jobs_fn):
        """
        Patch listing_scraper so it:
        - Writes state.json to tmp_path (real state_manager)
        - Writes raw_jobs.csv to tmp_path (real CSV writer)
        - Skips all Selenium navigation (records URLs instead)
        - Returns deterministic page_jobs from page_jobs_fn(page_index)
        """
        from scraper import listing_scraper
        import time

        monkeypatch.setattr(settings, "STATE_FILE",   tmp_path / "state.json")
        monkeypatch.setattr(settings, "RAW_JOBS_CSV", tmp_path / "raw_jobs.csv")
        monkeypatch.setattr(settings, "DEV_MODE_LIMIT", False)  # Disable cap for these tests

        # Mock navigation: always "succeeds", records URL
        def fake_navigate(driver, url, attempt=0):
            navigated_urls.append(url)
            return True

        monkeypatch.setattr(listing_scraper, "_navigate_with_retry", fake_navigate)

        # Mock card_parser: return deterministic jobs per page_index
        from parser import card_parser

        def fake_parse_results_count(html):
            return (1, 20, 100)  # showing 1-20 of 100

        def fake_parse(html, source_category=""):
            # Infer page from navigated_urls (last one added)
            if navigated_urls:
                last_url = navigated_urls[-1]
                page_idx = int(last_url.split("start=")[1])
            else:
                page_idx = 0
            return page_jobs_fn(page_idx)

        monkeypatch.setattr(card_parser, "parse_results_count", fake_parse_results_count)
        monkeypatch.setattr(card_parser, "parse", fake_parse)

        # Mock driver
        mock_driver = MagicMock()
        mock_driver.page_source = "<html></html>"

        # Mock time.sleep to keep tests fast
        monkeypatch.setattr(listing_scraper.time, "sleep", lambda _: None)

        return mock_driver, listing_scraper

    def test_resume_starts_at_next_page_after_crash(self, tmp_path, monkeypatch):
        """
        CRASH after page 2 (last_completed_page=2).
        Resume must start at page_index=3, NOT 0 or 1 or 2.
        """
        navigated_urls: list[str] = []
        mock_driver, listing_scraper = self._patch_scraper(
            monkeypatch, tmp_path, navigated_urls,
            page_jobs_fn=lambda pi: _fake_page_jobs(pi),
        )

        # Pre-load crash state: pages 0, 1, 2 completed
        crash_state = _build_state(
            "IT-Software-Development",
            last_completed_page=2,
            jobs_collected=60,
            total_results=100,
            total_pages=5,
        )
        state_manager.save_state(crash_state)

        # Write existing CSV (60 jobs from pages 0-2)
        existing_csv = tmp_path / "raw_jobs.csv"
        _write_csv(existing_csv, 60)

        # Run one category only
        cat = next(c for c in settings.TARGET_CATEGORIES if c["label"] == "IT-Software-Development")
        state = state_manager.load_state()
        listing_scraper._scrape_category(mock_driver, cat, state, 60)

        # Verify the first navigated URL is page_index=3, not 0/1/2
        assert navigated_urls, "No pages were navigated"
        first_url = navigated_urls[0]
        assert "start=3" in first_url, (
            f"Expected first navigation start=3, got: {first_url}"
        )

    def test_completed_pages_not_re_navigated(self, tmp_path, monkeypatch):
        """
        Pages 0, 1, 2 must NEVER be navigated when last_completed_page=2.
        """
        navigated_urls: list[str] = []
        mock_driver, listing_scraper = self._patch_scraper(
            monkeypatch, tmp_path, navigated_urls,
            page_jobs_fn=lambda pi: _fake_page_jobs(pi),
        )
        crash_state = _build_state(
            "IT-Software-Development", last_completed_page=2, jobs_collected=60
        )
        state_manager.save_state(crash_state)

        cat = next(c for c in settings.TARGET_CATEGORIES if c["label"] == "IT-Software-Development")
        state = state_manager.load_state()
        listing_scraper._scrape_category(mock_driver, cat, state, 60)

        for url in navigated_urls:
            page = int(url.split("start=")[1])
            assert page >= 3, f"Page {page} was re-navigated after crash at page 2!"

    def test_completed_category_is_skipped_entirely(self, tmp_path, monkeypatch):
        """
        A category with status='done' must return immediately without
        any navigation calls.
        """
        navigated_urls: list[str] = []
        mock_driver, listing_scraper = self._patch_scraper(
            monkeypatch, tmp_path, navigated_urls,
            page_jobs_fn=lambda pi: _fake_page_jobs(pi),
        )
        done_state = _build_state(
            "IT-Software-Development", last_completed_page=4, jobs_collected=100,
            cat_status="done",
        )
        state_manager.save_state(done_state)

        cat = next(c for c in settings.TARGET_CATEGORIES if c["label"] == "IT-Software-Development")
        state = state_manager.load_state()
        jobs, total = listing_scraper._scrape_category(mock_driver, cat, state, 100)

        assert len(navigated_urls) == 0, "Completed category should not be re-navigated"
        assert jobs == []

    def test_fresh_run_starts_at_page_zero(self, tmp_path, monkeypatch):
        """A fresh run (last_completed_page=-1) must start at page_index=0."""
        navigated_urls: list[str] = []
        mock_driver, listing_scraper = self._patch_scraper(
            monkeypatch, tmp_path, navigated_urls,
            page_jobs_fn=lambda pi: (
                _fake_page_jobs(pi) if pi < 2 else []  # stop after 2 pages
            ),
        )
        fresh_state = _build_state(
            "IT-Software-Development", last_completed_page=-1, jobs_collected=0, total_pages=5,
        )
        # Override to "pending" status so it's treated like a fresh category
        fresh_state["categories"]["IT-Software-Development"]["status"] = "pending"
        state_manager.save_state(fresh_state)

        cat = next(c for c in settings.TARGET_CATEGORIES if c["label"] == "IT-Software-Development")
        state = state_manager.load_state()
        listing_scraper._scrape_category(mock_driver, cat, state, 0)

        assert navigated_urls, "No navigation on fresh run"
        first_url = navigated_urls[0]
        assert "start=0" in first_url, f"Fresh run must start at start=0, got: {first_url}"


# ===========================================================================
# Tests: no duplicate jobs after resume
# ===========================================================================

class TestNoDuplicatesAfterResume:
    """Verify that resuming a crashed run does not produce duplicate job_ids."""

    def test_resume_produces_no_duplicate_job_ids(self, tmp_path, monkeypatch):
        """
        Scenario:
        - Pages 0 and 1 scraped before crash  (40 jobs, job_ids: crash_test_0000..0039)
        - Resume: pages 2 and 3 scraped       (40 new jobs, unique IDs)
        - Final CSV: 80 jobs, all unique IDs
        """
        from scraper import listing_scraper
        navigated_urls: list[str] = []

        monkeypatch.setattr(settings, "STATE_FILE",   tmp_path / "state.json")
        monkeypatch.setattr(settings, "RAW_JOBS_CSV", tmp_path / "raw_jobs.csv")
        monkeypatch.setattr(settings, "DEV_MODE_LIMIT", False)
        monkeypatch.setattr(listing_scraper.time, "sleep", lambda _: None)

        def fake_navigate(driver, url, attempt=0):
            navigated_urls.append(url)
            return True

        from parser import card_parser
        monkeypatch.setattr(listing_scraper, "_navigate_with_retry", fake_navigate)
        monkeypatch.setattr(card_parser, "parse_results_count", lambda html: (1, 20, 80))
        monkeypatch.setattr(card_parser, "parse", lambda html, source_category="": (
            _fake_page_jobs(
                int(navigated_urls[-1].split("start=")[1]) if navigated_urls else 0,
                n=20,
                prefix="resume",
            ) if navigated_urls and int(navigated_urls[-1].split("start=")[1]) < 4 else []
        ))

        # Write CSV with 40 "already scraped" jobs (pages 0+1)
        csv_path = tmp_path / "raw_jobs.csv"
        pre_crash_jobs = _write_csv(csv_path, 40)  # IDs: crash_test_0000..0039
        pre_crash_ids = {j["job_id"] for j in pre_crash_jobs}

        # State: pages 0+1 completed
        crash_state = _build_state(
            "IT-Software-Development", last_completed_page=1, jobs_collected=40,
            total_results=80, total_pages=4,
        )
        state_manager.save_state(crash_state)

        cat = next(c for c in settings.TARGET_CATEGORIES if c["label"] == "IT-Software-Development")
        state = state_manager.load_state()
        listing_scraper._scrape_category(MagicMock(), cat, state, 40)

        # Read the final CSV and collect all job_ids
        all_ids = []
        with csv_path.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                all_ids.append(row["job_id"])

        # Check no duplicates
        assert len(all_ids) == len(set(all_ids)), (
            f"Duplicate job_ids found after resume! Total={len(all_ids)}, "
            f"Unique={len(set(all_ids))}"
        )

        # Check pre-crash jobs are still there
        assert pre_crash_ids.issubset(set(all_ids)), (
            "Pre-crash jobs were lost after resume!"
        )

    def test_csv_header_written_exactly_once(self, tmp_path, monkeypatch):
        """
        If raw_jobs.csv already exists (from a prior partial run), the header
        must NOT be written again when _ensure_csv_header is called.
        """
        from scraper import listing_scraper
        csv_path = tmp_path / "raw_jobs.csv"
        monkeypatch.setattr(settings, "RAW_JOBS_CSV", csv_path)

        # First call: creates the file with header
        listing_scraper._ensure_csv_header(csv_path)
        # Second call: should be a no-op
        listing_scraper._ensure_csv_header(csv_path)

        # Count header lines in the file
        content = csv_path.read_text(encoding="utf-8")
        header_line = "job_id,job_title,"
        occurrences = content.count(header_line)
        assert occurrences == 1, f"Header written {occurrences} times (expected 1)"

    def test_state_checkpoint_updated_after_each_page(self, tmp_path, monkeypatch):
        """
        After scraping page N, state.json must reflect last_completed_page=N
        before moving to page N+1.
        """
        from scraper import listing_scraper
        navigated_urls: list[str] = []
        saved_states: list[dict] = []

        monkeypatch.setattr(settings, "STATE_FILE",   tmp_path / "state.json")
        monkeypatch.setattr(settings, "RAW_JOBS_CSV", tmp_path / "raw_jobs.csv")
        monkeypatch.setattr(settings, "DEV_MODE_LIMIT", False)
        monkeypatch.setattr(listing_scraper.time, "sleep", lambda _: None)

        # Track every save_state call
        original_save = state_manager.save_state
        def recording_save(state):
            import copy
            saved_states.append(copy.deepcopy(state))
            original_save(state)

        monkeypatch.setattr(state_manager, "save_state", recording_save)

        def fake_navigate(driver, url, attempt=0):
            navigated_urls.append(url)
            return True

        from parser import card_parser
        monkeypatch.setattr(listing_scraper, "_navigate_with_retry", fake_navigate)
        monkeypatch.setattr(card_parser, "parse_results_count", lambda html: (1, 20, 60))
        monkeypatch.setattr(card_parser, "parse", lambda html, source_category="": (
            _fake_page_jobs(
                int(navigated_urls[-1].split("start=")[1]) if navigated_urls else 0, n=20
            ) if navigated_urls and int(navigated_urls[-1].split("start=")[1]) < 3 else []
        ))

        fresh_state = _build_state(
            "IT-Software-Development", last_completed_page=-1, jobs_collected=0
        )
        fresh_state["categories"]["IT-Software-Development"]["status"] = "pending"
        state_manager.save_state(fresh_state)
        saved_states.clear()  # clear the initial save

        cat = next(c for c in settings.TARGET_CATEGORIES if c["label"] == "IT-Software-Development")
        state = state_manager.load_state()
        listing_scraper._scrape_category(MagicMock(), cat, state, 0)

        # Verify that last_completed_page increments sequentially in saved states
        cat_label = "IT-Software-Development"
        page_checkpoints = [
            s["categories"][cat_label]["last_completed_page"]
            for s in saved_states
            if cat_label in s.get("categories", {})
               and s["categories"][cat_label].get("last_completed_page") >= 0
        ]
        assert len(page_checkpoints) >= 1, "No page checkpoints were saved"
        # Each checkpoint should be >= the previous (monotonically increasing)
        for i in range(1, len(page_checkpoints)):
            assert page_checkpoints[i] >= page_checkpoints[i - 1], (
                f"Page checkpoints not monotone: {page_checkpoints}"
            )


# ===========================================================================
# Tests: main.py argument handling
# ===========================================================================

class TestMainEntryPoint:
    """Tests for main.py CLI argument handling."""

    def test_verify_only_returns_0_when_all_files_present(self, tmp_path, monkeypatch):
        """--verify-only should return 0 when all output files exist."""
        import main as main_mod

        # Monkeypatch all required paths to existing temp files
        charts_dir = tmp_path / "charts"
        charts_dir.mkdir()
        monkeypatch.setattr(settings, "RAW_JOBS_CSV",         tmp_path / "raw_jobs.csv")
        monkeypatch.setattr(settings, "EXTRACTED_SKILLS_CSV", tmp_path / "extracted_skills.csv")
        monkeypatch.setattr(settings, "ANALYTICS_CSV",        tmp_path / "analytics_summary.csv")
        monkeypatch.setattr(settings, "CHARTS_DIR",           charts_dir)

        # Create all expected files
        (tmp_path / "raw_jobs.csv").write_text("data", encoding="utf-8")
        (tmp_path / "extracted_skills.csv").write_text("data", encoding="utf-8")
        (tmp_path / "analytics_summary.csv").write_text("data", encoding="utf-8")
        chart_names = [
            "chart1_top20_bar.html",   "chart1_top20_bar.png",
            "chart2_role_heatmap.html","chart2_role_heatmap.png",
            "chart3_seniority_lines.html","chart3_seniority_lines.png",
            "chart4_cooccurrence.html","chart4_cooccurrence.png",
            "chart5_gap_treemap.html", "chart5_gap_treemap.png",
        ]
        for name in chart_names:
            (charts_dir / name).write_text("chart_data", encoding="utf-8")

        exit_code = main_mod.main(["--verify-only"])
        assert exit_code == 0

    def test_verify_only_returns_1_when_files_missing(self, tmp_path, monkeypatch):
        """--verify-only should return 1 when expected output files are missing."""
        import main as main_mod
        monkeypatch.setattr(settings, "RAW_JOBS_CSV",         tmp_path / "raw_jobs.csv")
        monkeypatch.setattr(settings, "EXTRACTED_SKILLS_CSV", tmp_path / "extracted_skills.csv")
        monkeypatch.setattr(settings, "ANALYTICS_CSV",        tmp_path / "analytics_summary.csv")
        monkeypatch.setattr(settings, "CHARTS_DIR",           tmp_path / "charts")
        # Files do NOT exist
        exit_code = main_mod.main(["--verify-only"])
        assert exit_code == 1

    def test_reset_clears_state_file(self, tmp_path, monkeypatch):
        """--reset must delete the state file."""
        import main as main_mod
        state_file = tmp_path / "state.json"
        monkeypatch.setattr(settings, "STATE_FILE",   state_file)
        monkeypatch.setattr(settings, "RAW_JOBS_CSV", tmp_path / "raw_jobs.csv")
        monkeypatch.setattr(settings, "EXTRACTED_SKILLS_CSV", tmp_path / "extracted_skills.csv")
        monkeypatch.setattr(settings, "ANALYTICS_CSV",        tmp_path / "analytics_summary.csv")
        monkeypatch.setattr(settings, "CHARTS_DIR",           tmp_path / "charts")

        state_file.write_text(json.dumps({"run_id": "old_run"}), encoding="utf-8")
        assert state_file.exists()

        # --reset without --run just resets and exits 0
        exit_code = main_mod.main(["--reset"])
        assert exit_code == 0
        assert not state_file.exists()


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
