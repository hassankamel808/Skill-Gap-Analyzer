"""
scripts/reextract_all.py
========================
One-shot script: re-runs skill extraction on every job in raw_jobs.csv,
rebuilding extracted_skills.csv from scratch.

Use when extracted_skills.csv is stale or only covers a subset of raw_jobs.csv
(e.g. after a production scrape without running the extraction phase).

Usage:
    python scripts/reextract_all.py
"""

from __future__ import annotations

import sys
import csv
from pathlib import Path

# ensure project root is on path
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from config import settings
from extraction.skill_extractor import (
    extract_skills_for_job,
    _ensure_csv_header,
    _append_skills_to_csv,
)


def reextract_all() -> None:
    raw_csv      = settings.RAW_JOBS_CSV
    skills_csv   = settings.EXTRACTED_SKILLS_CSV

    if not raw_csv.exists() or raw_csv.stat().st_size == 0:
        print(f"[ERROR] raw_jobs.csv not found: {raw_csv}")
        sys.exit(1)

    # Read all raw jobs
    with raw_csv.open("r", newline="", encoding="utf-8") as fh:
        reader  = csv.DictReader(fh)
        all_jobs = list(reader)

    total = len(all_jobs)
    print(f"Re-extracting skills from {total} jobs in raw_jobs.csv ...")
    print(f"Output -> {skills_csv}")
    print()

    # Wipe and recreate extracted_skills.csv
    skills_csv.unlink(missing_ok=True)
    _ensure_csv_header(skills_csv)

    total_skill_rows  = 0
    jobs_with_skills  = 0
    jobs_without      = 0
    batch             = []
    BATCH_SIZE        = 200  # flush to disk every N jobs

    for i, job in enumerate(all_jobs, start=1):
        rows = extract_skills_for_job(job)
        if rows:
            batch.extend(rows)
            jobs_with_skills += 1
        else:
            jobs_without += 1

        if len(batch) >= BATCH_SIZE or i == total:
            _append_skills_to_csv(batch, skills_csv)
            total_skill_rows += len(batch)
            batch = []

        if i % 500 == 0 or i == total:
            print(f"  [{i:>5}/{total}] skill rows so far: {total_skill_rows}")

    print()
    print(f"Done.")
    print(f"  Jobs processed      : {total}")
    print(f"  Jobs with skills    : {jobs_with_skills}")
    print(f"  Jobs without skills : {jobs_without}")
    print(f"  Total skill rows    : {total_skill_rows}")
    print(f"  Output              : {skills_csv}")


if __name__ == "__main__":
    reextract_all()
