"""
pipeline/orchestrator.py
========================
Main pipeline entry point. Wires all phases together.

This module is the ONLY module allowed to write:
    - output/analytics_summary.csv
    - output/cooccurrence_matrix.csv

PIPELINE PHASES
---------------
Phase B/C: Scraping + Extraction  (optional — can skip if CSVs already exist)
Phase D:   Analysis               (demand scoring, gap analysis, co-occurrence)

Two entry points
----------------
run_pipeline()
    Full pipeline: scrape -> extract -> analyse.
    Requires Chrome/undetected-chromedriver to be available.

run_analysis_only()
    Analysis-only: read existing CSVs and run Phase D.
    Use this to re-run analysis after manual corrections or for testing.

ANALYTICS_SUMMARY.CSV SCHEMA
-----------------------------
segment_type, segment_value, rank, skill_canonical, skill_category,
job_count, demand_score, [gap cols: senior_mentions, entry_mentions,
seniority_skew, gap_signal_score, is_emerging_gap]

Gap-analysis rows have segment_type = "gap_analysis".
All other rows leave gap columns NULL.
"""

from __future__ import annotations

import logging
import logging.config
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from config import settings
from analysis import demand_scorer, gap_analyzer, cooccurrence
from visualization import dashboard

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Analytics CSV schema
# ---------------------------------------------------------------------------

_ANALYTICS_COLS: list[str] = [
    "segment_type",
    "segment_value",
    "rank",
    "skill_canonical",
    "skill_category",
    "job_count",
    "demand_score",
    # Gap-analysis extra columns (NULL for non-gap rows)
    "demand_rank",
    "senior_mentions",
    "mid_mentions",
    "entry_mentions",
    "seniority_skew",
    "gap_signal_score",
    "is_emerging_gap",
]


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format=settings.LOG_FORMAT,
        datefmt=settings.LOG_DATE_FORMAT,
        stream=sys.stdout,
    )


# ---------------------------------------------------------------------------
# CSV I/O helpers (orchestrator's exclusive write path)
# ---------------------------------------------------------------------------

def _write_analytics(frames: list[pd.DataFrame], path: Path) -> None:
    """Concatenate demand + gap frames and write analytics_summary.csv."""
    combined = pd.concat(frames, ignore_index=True)
    # Ensure all schema columns exist (fill missing with None)
    for col in _ANALYTICS_COLS:
        if col not in combined.columns:
            combined[col] = None
    combined = combined[_ANALYTICS_COLS]
    combined.to_csv(path, index=False, encoding="utf-8")
    logger.info("Analytics summary written -> %s  (%d rows)", path, len(combined))


def _write_cooccurrence(matrix: pd.DataFrame, path: Path) -> None:
    """Write the co-occurrence matrix as a square CSV (index included)."""
    if matrix.empty:
        logger.warning("Co-occurrence matrix is empty — skipping write.")
        return
    matrix.to_csv(path, index=True, encoding="utf-8")
    logger.info(
        "Co-occurrence matrix written -> %s  (%dx%d)", path, *matrix.shape
    )


def _read_csv_safe(path: Path, name: str) -> pd.DataFrame:
    """Read a CSV file, returning an empty DataFrame on failure."""
    if not path.exists() or path.stat().st_size == 0:
        logger.error("%s not found or empty: %s", name, path)
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, dtype=str)
        logger.info("Loaded %s: %d rows from %s", name, len(df), path)
        return df
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to read %s (%s): %s", name, path, exc)
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Phase D: Analysis
# ---------------------------------------------------------------------------

def run_analysis_only() -> dict[str, pd.DataFrame]:
    """
    Run Phase D analysis using existing raw_jobs.csv and extracted_skills.csv.

    Does NOT require Chrome or Selenium. Use for testing, re-runs, and
    dashboard refresh without re-scraping.

    Returns
    -------
    dict with keys: "global", "by_role", "by_seniority", "by_city",
                    "gap_signals", "cooccurrence"
    """
    _configure_logging()
    logger.info("=== Phase D: Analysis pipeline starting ===")
    t_start = datetime.now(tz=timezone.utc)

    # ── Load CSVs ─────────────────────────────────────────────────────────────
    jobs_df   = _read_csv_safe(settings.RAW_JOBS_CSV,        "raw_jobs.csv")
    skills_df = _read_csv_safe(settings.EXTRACTED_SKILLS_CSV, "extracted_skills.csv")

    if jobs_df.empty or skills_df.empty:
        logger.error(
            "Cannot run analysis — one or both input CSVs are missing.\n"
            "Run run_pipeline() to scrape and extract data first,\n"
            "or use scripts/generate_mock_data.py to create test data."
        )
        return {}

    # Ensure numeric types for key columns
    if "confidence" in skills_df.columns:
        skills_df["confidence"] = pd.to_numeric(skills_df["confidence"], errors="coerce")

    logger.info(
        "Input: %d jobs, %d skill rows, %d unique skills.",
        len(jobs_df),
        len(skills_df),
        skills_df["skill_canonical"].nunique(),
    )

    # ── Step 1: Demand scoring ─────────────────────────────────────────────────
    logger.info("--- Step 1: Demand scoring ---")
    demand_results = demand_scorer.compute_demand_scores(
        skills_df,
        jobs_df,
        top_n_global=20,
        top_n_segment=10,
    )

    global_df       = demand_results["global"]
    by_role_df      = demand_results["by_role"]
    by_seniority_df = demand_results["by_seniority"]
    by_city_df      = demand_results["by_city"]

    # ── Step 2: Gap analysis ───────────────────────────────────────────────────
    logger.info("--- Step 2: Gap analysis ---")
    gap_df = gap_analyzer.compute_gap_signals(
        skills_df,
        jobs_df,
        global_scores=global_df,
    )
    # Tag gap rows for the combined CSV
    if not gap_df.empty:
        gap_df["segment_type"]  = "gap_analysis"
        gap_df["segment_value"] = "all"

    # ── Step 3: Co-occurrence matrix ──────────────────────────────────────────
    logger.info("--- Step 3: Co-occurrence matrix ---")
    cooc_matrix = cooccurrence.build_cooccurrence_matrix(
        skills_df,
        max_skills=50,
    )

    # ── Step 4: Write outputs (orchestrator's exclusive write zone) ────────────
    logger.info("--- Step 4: Writing outputs ---")
    demand_frames = [
        f for f in [global_df, by_role_df, by_seniority_df, by_city_df]
        if f is not None and not f.empty
    ]
    all_frames = demand_frames + ([gap_df] if not gap_df.empty else [])
    _write_analytics(all_frames, settings.ANALYTICS_CSV)
    _write_cooccurrence(cooc_matrix, settings.OUTPUT_DIR / "cooccurrence_matrix.csv")

    # -- Step 5: Visualisation -----------------------------------------------------
    logger.info("--- Step 5: Generating dashboard charts ---")
    # Build the combined analytics DataFrame (re-use in-memory frames)
    analytics_combined = pd.concat(
        [f for f in all_frames if f is not None and not f.empty],
        ignore_index=True,
    )
    # Ensure numeric types for chart functions
    for num_col in ("demand_score", "job_count", "gap_signal_score",
                    "seniority_skew", "rank"):
        if num_col in analytics_combined.columns:
            analytics_combined[num_col] = pd.to_numeric(
                analytics_combined[num_col], errors="coerce"
            )
    try:
        dashboard.generate_all(analytics_combined, cooc_matrix)
    except Exception as exc:   # noqa: BLE001
        logger.error("Dashboard generation failed: %s", exc, exc_info=True)

    elapsed = (datetime.now(tz=timezone.utc) - t_start).total_seconds()
    logger.info("=== Phase D complete in %.1fs ===", elapsed)

    return {
        "global":       global_df,
        "by_role":      by_role_df,
        "by_seniority": by_seniority_df,
        "by_city":      by_city_df,
        "gap_signals":  gap_df,
        "cooccurrence": cooc_matrix,
    }


# ---------------------------------------------------------------------------
# Full pipeline (Phase B -> C -> D)
# ---------------------------------------------------------------------------

def run_pipeline() -> None:
    """
    Full pipeline: scrape -> extract -> analyse.

    Requires Chrome + undetected-chromedriver. Respects DEV_MODE_LIMIT
    (from settings.py) to cap the scrape at DEV_MODE_LIMIT_COUNT jobs.

    For analysis-only runs (no scraping), use run_analysis_only().
    """
    _configure_logging()
    logger.info("=== Full pipeline starting ===")
    logger.info(
        "DEV_MODE=%s  limit=%s",
        settings.DEV_MODE_LIMIT,
        settings.DEV_MODE_LIMIT_COUNT if settings.DEV_MODE_LIMIT else "none",
    )

    # ── Phase B: Scraping ─────────────────────────────────────────────────────
    from scraper import driver_manager, listing_scraper
    from extraction import skill_extractor

    driver = None
    try:
        driver = driver_manager.create_driver()
        jobs = listing_scraper.scrape_all_categories(driver)
        logger.info("Scraping complete: %d jobs collected.", len(jobs))
    finally:
        driver_manager.teardown(driver)

    # ── Phase C: Skill extraction ─────────────────────────────────────────────
    if jobs:
        logger.info("--- Phase C: Extracting skills ---")
        skill_extractor.extract_skills(jobs)
    else:
        logger.warning(
            "No jobs scraped — skipping extraction. "
            "Check Chrome/network and try again."
        )

    # ── Phase D: Analysis ─────────────────────────────────────────────────────
    run_analysis_only()
    logger.info("=== Full pipeline complete ===")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Wuzzuf Skill-Gap Analyzer pipeline"
    )
    parser.add_argument(
        "--analysis-only",
        action="store_true",
        help="Skip scraping/extraction; re-run analysis on existing CSVs.",
    )
    args = parser.parse_args()

    if args.analysis_only:
        results = run_analysis_only()
        if results and "global" in results and not results["global"].empty:
            print("\n=== TOP 20 GLOBAL SKILLS ===")
            print(results["global"].to_string(index=False))
    else:
        run_pipeline()
