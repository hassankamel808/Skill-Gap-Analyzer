#!/usr/bin/env python3
"""
main.py
=======
Master entry point for the Wuzzuf Tech Job Market Skill-Gap Analyzer.

Wires the complete pipeline end-to-end:
    Scrape Listings  -> Extract Skills -> Analyze Data -> Generate Dashboard

Usage
-----
Full pipeline (requires Chrome + undetected-chromedriver):
    python main.py

Analysis-only (re-run on existing CSVs, no browser needed):
    python main.py --analysis-only

Reset checkpoint and start fresh:
    python main.py --reset

Reset checkpoint then run full pipeline:
    python main.py --reset --run

Production mode switch:
    Edit config/settings.py  ->  DEV_MODE_LIMIT = False
    Then run:                    python main.py --reset

Crash / interruption recovery:
    Simply run again — the scraper reads state.json and resumes seamlessly
    from exactly where it stopped. No data is duplicated.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Ensure project root is on sys.path ────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config import settings
from pipeline import state_manager, orchestrator

# ---------------------------------------------------------------------------
# Logging bootstrap (before any module-level imports that log)
# ---------------------------------------------------------------------------

def _setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format=settings.LOG_FORMAT,
        datefmt=settings.LOG_DATE_FORMAT,
        stream=sys.stdout,
        force=True,
    )

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Console banner
# ---------------------------------------------------------------------------

_BANNER = """
==============================================================
  WUZZUF SKILL-GAP ANALYZER  |  Egyptian Tech Job Market
==============================================================
"""

_DEV_WARN = """
[WARNING] ====================================================
[WARNING]  DEV MODE ACTIVE
[WARNING]  Scrape is capped at {limit} jobs (DEV_MODE_LIMIT_COUNT)
[WARNING]  To run production, set DEV_MODE_LIMIT = False in
[WARNING]  config/settings.py, then call:  python main.py --reset
[WARNING] ====================================================
"""

_RESUME_NOTICE = """
[INFO] Resuming interrupted run:
[INFO]   run_id  : {run_id}
[INFO]   jobs so far : {total_jobs}
[INFO]   status  : {status}
[INFO] The scraper will continue from the last checkpoint.
"""


def _print_banner(dev_mode: bool, state: dict | None) -> None:
    print(_BANNER)
    if dev_mode:
        print(_DEV_WARN.format(limit=settings.DEV_MODE_LIMIT_COUNT))
    if state and state.get("status") == "in_progress" and state.get("total_jobs_collected", 0) > 0:
        print(_RESUME_NOTICE.format(
            run_id=state.get("run_id", "?"),
            total_jobs=state.get("total_jobs_collected", 0),
            status=state.get("status", "?"),
        ))


# ---------------------------------------------------------------------------
# Output file verification (Step 15 helper)
# ---------------------------------------------------------------------------

def _verify_outputs() -> bool:
    """
    Confirm all expected output files exist after a pipeline run.

    Returns True if every expected file is present and non-empty.
    """
    expected = [
        settings.RAW_JOBS_CSV,
        settings.EXTRACTED_SKILLS_CSV,
        settings.ANALYTICS_CSV,
    ]
    chart_names = [
        "chart1_top20_bar.html",   "chart1_top20_bar.png",
        "chart2_role_heatmap.html","chart2_role_heatmap.png",
        "chart3_seniority_lines.html","chart3_seniority_lines.png",
        "chart4_cooccurrence.html","chart4_cooccurrence.png",
        "chart5_gap_treemap.html", "chart5_gap_treemap.png",
    ]
    for name in chart_names:
        expected.append(settings.CHARTS_DIR / name)

    all_ok = True
    print("\n=== Output File Verification ===")
    for path in expected:
        exists = Path(path).exists() and Path(path).stat().st_size > 0
        status = "[OK]    " if exists else "[MISSING]"
        print(f"  {status} {path.name}")
        if not exists:
            all_ok = False

    if all_ok:
        print("\n  All outputs verified successfully.\n")
    else:
        print("\n  [WARNING] Some output files are missing — check logs above.\n")
    return all_ok


# ---------------------------------------------------------------------------
# CLI argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="Wuzzuf Tech Job Market Skill-Gap Analyzer — master pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--analysis-only",
        action="store_true",
        help="Skip scraping and extraction; re-run analysis on existing CSVs.",
    )
    parser.add_argument(
        "--extract-and-analyze",
        action="store_true",
        help="Skip scraping; re-extract skills from all raw jobs, then run analysis.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the state checkpoint so the next scrape starts fresh.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Force a pipeline run even after --reset (otherwise --reset alone just clears state).",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Just check that all expected output files exist without running anything.",
    )
    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """
    Main entry point. Returns an exit code (0 = success, 1 = error).
    """
    _setup_logging()
    args = _build_parser().parse_args(argv)

    # ── Verify-only shortcut ──────────────────────────────────────────────────
    if args.verify_only:
        ok = _verify_outputs()
        return 0 if ok else 1

    # ── Reset checkpoint if requested ─────────────────────────────────────────
    if args.reset:
        state_manager.reset_state()
        logger.info("State reset. CSVs preserved (delete manually if re-scraping).")
        if not (args.run or args.analysis_only):
            print("State cleared. Run 'python main.py' to start a fresh scrape.")
            return 0

    # ── Load state to display resume notice ──────────────────────────────────
    current_state = state_manager.load_state()
    _print_banner(dev_mode=settings.DEV_MODE_LIMIT, state=current_state)

    t_start = datetime.now(tz=timezone.utc)
    exit_code = 0

    try:
        if args.extract_and_analyze:
            # ── Extract and analyze mode: skip scraping ───────────────────────
            logger.info("Running in --extract-and-analyze mode.")
            from scripts.reextract_all import reextract_all
            reextract_all()
            
            logger.info("Running analysis phase...")
            results = orchestrator.run_analysis_only()
            if not results:
                logger.error("Analysis pipeline returned no results.")
                exit_code = 1
        elif args.analysis_only:
            # ── Analysis-only mode: skip scraping/extraction ──────────────────
            logger.info("Running in --analysis-only mode.")
            results = orchestrator.run_analysis_only()
            if not results:
                logger.error("Analysis pipeline returned no results.")
                exit_code = 1
        else:
            # ── Full pipeline mode: scrape -> extract -> analyse ──────────────
            logger.info("Running full pipeline (scrape → extract → analyse → visualise).")
            orchestrator.run_pipeline()

    except KeyboardInterrupt:
        logger.warning(
            "\nPipeline interrupted by user (Ctrl+C). "
            "Progress saved to %s — run again to resume.", settings.STATE_FILE
        )
        exit_code = 130  # Standard SIGINT exit code

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Pipeline failed with unhandled error: %s", exc, exc_info=True
        )
        exit_code = 1

    finally:
        elapsed = (datetime.now(tz=timezone.utc) - t_start).total_seconds()
        logger.info("Total wall-clock time: %.1f seconds.", elapsed)
        _verify_outputs()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
