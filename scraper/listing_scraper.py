"""
scraper/listing_scraper.py
==========================
Listing-only scraper — iterates all target categories, paginates each
category using ?start=N, hands off page_source to card_parser, writes
results to CSV, and maintains a JSON checkpoint so a crashed run can
resume exactly where it left off.

Public API
----------
scrape_all_categories(driver) -> list[dict]
    Main entry point. Returns the full list of scraped job dicts.
    Respects DEV_MODE_LIMIT — stops early once DEV_MODE_LIMIT_COUNT
    total jobs have been collected across all categories.

State / checkpoint schema (output/state.json)
---------------------------------------------
{
  "run_id": "20260415_210000",
  "status": "in_progress" | "done",
  "phase": "listing_scrape",
  "total_jobs_collected": 42,
  "categories": {
    "IT-Software-Development": {
      "status":              "done" | "in_progress" | "pending",
      "total_results":       3405,
      "total_pages":         171,
      "last_completed_page": 2,       <- 0-indexed; -1 = not started
      "jobs_collected":      60
    },
    ...
  },
  "last_updated": "2026-04-15T21:23:00+00:00"
}

Pagination contract
-------------------
URL pattern : {category_url}?start={page_index}
page_index  : 0-based (page 1 → start=0, page 2 → start=1, …)
Stop when   : page returned fewer than JOBS_PER_PAGE cards  OR
              showing_end >= total_results (counter says we're at the last page)
"""

from __future__ import annotations

import csv
import json
import logging
import math
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from selenium.common.exceptions import TimeoutException, WebDriverException
import undetected_chromedriver as uc

from config import settings
from parser import card_parser
from scraper import driver_manager
from pipeline import state_manager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

# Ordered field names — matches the schema defined in the architecture plan.
_CSV_FIELDS: list[str] = [
    "job_id",
    "job_title",
    "job_url",
    "company_name",
    "location_raw",
    "city",
    "posted_date_raw",
    "job_type",
    "work_mode",
    "experience_level",
    "category_tags",
    "source_category",
    "scraped_at",
]


def _ensure_csv_header(csv_path: Path) -> None:
    """Write the CSV header row if the file does not yet exist or is empty."""
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
        logger.debug("CSV header written to %s", csv_path)


def _append_jobs_to_csv(jobs: list[dict], csv_path: Path) -> None:
    """Append a batch of job dicts to the CSV (no header re-written)."""
    if not jobs:
        return
    with csv_path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writerows(jobs)
    logger.debug("Appended %d job(s) to %s", len(jobs), csv_path)


# ---------------------------------------------------------------------------
# Internal: navigate one page with retry + backoff
# ---------------------------------------------------------------------------

def _navigate_with_retry(
    driver: uc.Chrome,
    url: str,
    attempt: int = 0,
) -> bool:
    """
    Navigate to ``url`` and confirm job cards are present.

    Parameters
    ----------
    driver  : WebDriver
    url     : Full URL to load (including ?start=N)
    attempt : Current retry attempt index (0-based)

    Returns
    -------
    bool
        True if cards were successfully detected; False after all retries
        exhausted.
    """
    max_retries = settings.MAX_PAGE_RETRIES
    backoff = settings.RETRY_BACKOFF_DELAYS  # [5, 15, 45]

    try:
        logger.debug("GET %s", url)
        driver.get(url)

        # If CF challenge fires, wait for it to auto-resolve
        if driver_manager.is_cf_challenge(driver):
            logger.info("Cloudflare challenge detected — waiting up to %ds …",
                        settings.CLOUDFLARE_RESOLVE_WAIT_SECONDS)
            resolved = driver_manager.wait_for_cf(driver)
            if not resolved:
                raise TimeoutException("Cloudflare challenge did not resolve.")

        # Wait for job cards
        cards_visible = driver_manager.wait_for_cards(driver)
        if not cards_visible:
            raise TimeoutException("Job card elements did not appear in DOM.")

        return True

    except (TimeoutException, WebDriverException) as exc:
        if attempt < max_retries - 1:
            delay = backoff[min(attempt, len(backoff) - 1)]
            logger.warning(
                "Page load failed (attempt %d/%d): %s — retrying in %.0fs …",
                attempt + 1, max_retries, exc, delay,
            )
            time.sleep(delay)
            return _navigate_with_retry(driver, url, attempt + 1)
        else:
            logger.error(
                "Page load failed after %d attempts: %s  URL: %s",
                max_retries, exc, url,
            )
            return False


# ---------------------------------------------------------------------------
# Internal: scrape one category
# ---------------------------------------------------------------------------

def _scrape_category(
    driver: uc.Chrome,
    category: dict,
    state: dict,
    total_collected: int,
) -> tuple[list[dict], int]:
    """
    Scrape all pages of a single category, respecting DEV_MODE_LIMIT.

    Parameters
    ----------
    driver          : WebDriver instance
    category        : One entry from settings.TARGET_CATEGORIES
    state           : Mutable state dict (modified in place for checkpointing)
    total_collected : Jobs already collected from prior categories

    Returns
    -------
    (jobs_from_category, updated_total_collected)
    """
    label = category["label"]
    base_url = category["url"]
    cat_state = state["categories"][label]

    # ── Resume from checkpoint ────────────────────────────────────────────────
    start_page = cat_state.get("last_completed_page", -1) + 1
    if cat_state.get("status") == "done":
        logger.info("Category '%s' already complete — skipping.", label)
        return [], total_collected

    logger.info(
        "=== Starting category: %s  (resuming from page index %d) ===",
        label, start_page,
    )
    cat_state["status"] = "in_progress"
    state_manager.save_state(state)

    all_jobs: list[dict] = []
    consecutive_failures = 0
    total_results: int | None = cat_state.get("total_results")
    total_pages: int | None = cat_state.get("total_pages")

    page_index = start_page

    while True:
        # ── DEV_MODE_LIMIT guard ──────────────────────────────────────────────
        if settings.DEV_MODE_LIMIT:
            remaining_budget = settings.DEV_MODE_LIMIT_COUNT - total_collected
            if remaining_budget <= 0:
                logger.info(
                    "[DEV] Reached %d job limit — stopping scrape.",
                    settings.DEV_MODE_LIMIT_COUNT,
                )
                return all_jobs, total_collected

        # ── Pagination end guard ──────────────────────────────────────────────
        if total_pages is not None and page_index >= total_pages:
            logger.info(
                "Category '%s' — reached last page (index %d / total %d).",
                label, page_index, total_pages,
            )
            break

        # ── Cooldown every N pages ────────────────────────────────────────────
        if (
            page_index > 0
            and page_index % settings.LISTING_COOLDOWN_EVERY_N_PAGES == 0
        ):
            logger.info(
                "Cooldown pause %.0fs after %d pages …",
                settings.LISTING_COOLDOWN_SECONDS, page_index,
            )
            time.sleep(settings.LISTING_COOLDOWN_SECONDS)

        # ── Build paginated URL ───────────────────────────────────────────────
        url = f"{base_url}?start={page_index}"

        # ── Navigate ──────────────────────────────────────────────────────────
        success = _navigate_with_retry(driver, url)

        if not success:
            consecutive_failures += 1
            logger.warning(
                "Page %d failed. Consecutive failures: %d / %d",
                page_index, consecutive_failures,
                settings.MAX_CONSECUTIVE_FAILURES,
            )
            if consecutive_failures >= settings.MAX_CONSECUTIVE_FAILURES:
                logger.error(
                    "Too many consecutive failures on category '%s'. "
                    "Triggering long pause (%ds) …", label,
                    settings.LONG_PAUSE_SECONDS,
                )
                time.sleep(settings.LONG_PAUSE_SECONDS)
                consecutive_failures = 0
            continue  # retry same page_index after pause

        consecutive_failures = 0  # reset on success

        # ── Get rendered HTML ─────────────────────────────────────────────────
        html = driver.page_source

        # ── Parse results counter (first page only, or if still unknown) ──────
        if total_results is None or page_index == start_page:
            counter = card_parser.parse_results_count(html)
            if counter:
                _, showing_end, total_results = counter
                total_pages = math.ceil(total_results / settings.JOBS_PER_PAGE)
                cat_state["total_results"] = total_results
                cat_state["total_pages"] = total_pages
                logger.info(
                    "Category '%s': %d total results → %d pages.",
                    label, total_results, total_pages,
                )
            else:
                logger.warning(
                    "Could not parse results counter on page %d (%s).",
                    page_index, url,
                )

        # ── Parse job cards ── HANDOFF to BeautifulSoup ───────────────────────
        page_jobs = card_parser.parse(html, source_category=label)
        n = len(page_jobs)
        logger.info(
            "Page %d (%s): parsed %d job(s).",
            page_index, label, n,
        )

        # ── DEV_MODE_LIMIT: trim batch to budget ──────────────────────────────
        if settings.DEV_MODE_LIMIT:
            budget = settings.DEV_MODE_LIMIT_COUNT - total_collected
            if n > budget:
                page_jobs = page_jobs[:budget]
                logger.info(
                    "[DEV] Trimmed batch to %d (budget remaining: %d).",
                    len(page_jobs), budget,
                )

        # ── Persist to CSV immediately ────────────────────────────────────────
        if page_jobs:
            _append_jobs_to_csv(page_jobs, settings.RAW_JOBS_CSV)
            all_jobs.extend(page_jobs)
            total_collected += len(page_jobs)
            cat_state["jobs_collected"] = (
                cat_state.get("jobs_collected", 0) + len(page_jobs)
            )
            state["total_jobs_collected"] = total_collected

        # ── Update checkpoint ─────────────────────────────────────────────────
        cat_state["last_completed_page"] = page_index
        state["last_updated"] = datetime.now(tz=timezone.utc).isoformat()
        state_manager.save_state(state)

        # ── Pagination end detection ──────────────────────────────────────────
        # Condition A: fewer cards than a full page → last page
        if n < settings.JOBS_PER_PAGE and n > 0:
            logger.info(
                "Category '%s' — partial page (%d cards) detected. "
                "Assuming last page.", label, n,
            )
            break

        # Condition B: counter explicitly says we're at the end
        if total_results is not None:
            counter = card_parser.parse_results_count(html)
            if counter:
                s_start, s_end, s_total = counter
                if s_end >= s_total:
                    logger.info(
                        "Category '%s' — counter shows end (%d of %d). Done.",
                        label, s_end, s_total,
                    )
                    break

        # Condition C: no cards found at all → stop iterating this category
        if n == 0:
            logger.warning(
                "Category '%s' page %d returned 0 cards — stopping.",
                label, page_index,
            )
            break

        # ── DEV_MODE_LIMIT post-page check ────────────────────────────────────
        if settings.DEV_MODE_LIMIT and total_collected >= settings.DEV_MODE_LIMIT_COUNT:
            logger.info(
                "[DEV] Collected %d/%d jobs — stopping.",
                total_collected, settings.DEV_MODE_LIMIT_COUNT,
            )
            break

        # ── Advance page ──────────────────────────────────────────────────────
        page_index += 1

        # ── Polite delay ──────────────────────────────────────────────────────
        delay = random.uniform(settings.LISTING_DELAY_MIN, settings.LISTING_DELAY_MAX)
        logger.debug("Sleeping %.2fs before next page …", delay)
        time.sleep(delay)

    # ── Mark category done ────────────────────────────────────────────────────
    cat_state["status"] = "done"
    state["last_updated"] = datetime.now(tz=timezone.utc).isoformat()
    state_manager.save_state(state)
    logger.info(
        "Category '%s' complete. Jobs collected this run: %d.",
        label, len(all_jobs),
    )

    return all_jobs, total_collected


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def scrape_all_categories(driver: uc.Chrome) -> list[dict]:
    """
    Iterate all TARGET_CATEGORIES, scrape job listings, and return the
    combined list of job dicts.

    Writes raw_jobs.csv and updates state.json incrementally — a crash at
    any point can be resumed by restarting the pipeline; already-completed
    categories and pages are skipped.

    Parameters
    ----------
    driver : uc.Chrome
        A live, configured WebDriver from driver_manager.create_driver().

    Returns
    -------
    list[dict]
        All job dicts scraped this run (may be a partial list if
        DEV_MODE_LIMIT was hit or a crash occurred on a prior run and
        this is a resume).
    """
    # ── Initialise CSV (write header if file is new) ──────────────────────────
    _ensure_csv_header(settings.RAW_JOBS_CSV)

    # ── Load or create checkpoint state ───────────────────────────────────────
    state = state_manager.load_state()
    _bootstrap_state(state)

    total_collected: int = state.get("total_jobs_collected", 0)
    all_jobs: list[dict] = []

    logger.info(
        "Starting listing scrape | DEV_MODE=%s limit=%s | categories=%d",
        settings.DEV_MODE_LIMIT,
        settings.DEV_MODE_LIMIT_COUNT if settings.DEV_MODE_LIMIT else "none",
        len(settings.TARGET_CATEGORIES),
    )

    for category in settings.TARGET_CATEGORIES:
        label = category["label"]

        # ── Skip completed categories ─────────────────────────────────────────
        cat_state = state["categories"].get(label, {})
        if cat_state.get("status") == "done":
            logger.info("Category '%s' already done — skipping.", label)
            continue

        # ── Global DEV_MODE_LIMIT guard before starting a new category ─────────
        if settings.DEV_MODE_LIMIT and total_collected >= settings.DEV_MODE_LIMIT_COUNT:
            logger.info(
                "[DEV] Limit of %d jobs reached — not starting category '%s'.",
                settings.DEV_MODE_LIMIT_COUNT, label,
            )
            break

        cat_jobs, total_collected = _scrape_category(
            driver, category, state, total_collected
        )
        all_jobs.extend(cat_jobs)

        # ── Global DEV_MODE_LIMIT guard after each category ───────────────────
        if settings.DEV_MODE_LIMIT and total_collected >= settings.DEV_MODE_LIMIT_COUNT:
            logger.info(
                "[DEV] Global limit reached after category '%s'. "
                "Stopping further categories.", label,
            )
            break

    # ── Mark overall run done ─────────────────────────────────────────────────
    state["status"] = "done"
    state["last_updated"] = datetime.now(tz=timezone.utc).isoformat()
    state_manager.save_state(state)

    logger.info(
        "Listing scrape complete. Total jobs this run: %d  |  CSV: %s",
        len(all_jobs), settings.RAW_JOBS_CSV,
    )
    return all_jobs


# ---------------------------------------------------------------------------
# State bootstrapping
# ---------------------------------------------------------------------------

def _bootstrap_state(state: dict) -> None:
    """
    Ensure every TARGET_CATEGORY has an entry in state["categories"].
    Pre-populates any missing category entries with "pending" status.
    Modifies ``state`` in place.
    """
    if "categories" not in state:
        state["categories"] = {}
    if "total_jobs_collected" not in state:
        state["total_jobs_collected"] = 0
    if "phase" not in state:
        state["phase"] = "listing_scrape"

    for cat in settings.TARGET_CATEGORIES:
        label = cat["label"]
        if label not in state["categories"]:
            state["categories"][label] = {
                "status":              "pending",
                "total_results":       None,
                "total_pages":         None,
                "last_completed_page": -1,
                "jobs_collected":      0,
            }

    state_manager.save_state(state)
