"""
analysis/demand_scorer.py
=========================
Pure function module — zero file I/O, zero side effects.

Computes skill demand scores globally and segmented by role, seniority,
and city using only pre-loaded pandas DataFrames.

PUBLIC API
----------
compute_demand_scores(skills_df, jobs_df, top_n_global, top_n_segment)
    -> dict[str, pd.DataFrame]
    Keys: "global", "by_role", "by_seniority", "by_city"

_seniority_bucket(experience_level) -> str
    Maps raw experience_level text to "Entry" | "Mid" | "Senior" | "Unknown"

DEMAND SCORE FORMULA
---------------------
demand_score(skill) = count(distinct job_ids that mention skill) / total_jobs

where total_jobs = len(jobs_df) — the actual scraped job count.

This fraction is intentionally not capped at 1.0: a score of 0.75 means
75% of all scraped jobs mention that skill.

SEGMENTED SCORES
----------------
For role segments  : demand_score = count_in_role / total_jobs_in_role
For seniority segs : demand_score = count_in_seniority / total_in_seniority
For city segments  : demand_score = count_in_city / total_in_city

The seniority label is derived by bucketing experience_level (joined from
jobs_df on job_id) into "Entry", "Mid", "Senior", or "Unknown".

OUTPUT SCHEMA (per returned DataFrame)
--------------------------------------
Column          Type    Description
-----------     -----   -----------
rank            int     1 = most demanded in that segment
skill_canonical str
skill_category  str     Taxonomy category label
job_count       int     Distinct jobs mentioning this skill
demand_score    float   [0, 1] fraction of jobs in segment
segment_type    str     "global" | "role" | "seniority" | "city"
segment_value   str     "all" | role name | seniority bucket | city name
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seniority bucketing
# ---------------------------------------------------------------------------

# Keywords that map an experience_level string to a seniority bucket.
# Checked in order; first match wins.
_SENIORITY_RULES: list[tuple[list[str], str]] = [
    (["entry", "junior", "fresh", "intern", "student", "trainee", "graduate"], "Entry"),
    (["senior", "manager", "director", "c-level", "management", "lead", "head", "vp", "principal"], "Senior"),
    (["experienced", "mid", "associate"], "Mid"),
]


def _seniority_bucket(experience_level: str | None) -> str:
    """
    Map a raw experience_level string to a canonical seniority bucket.

    Parameters
    ----------
    experience_level : str | None
        e.g. "Entry Level", "Experienced", "Senior Management"

    Returns
    -------
    str
        One of "Entry", "Mid", "Senior", "Unknown".
    """
    if not experience_level or not isinstance(experience_level, str):
        return "Unknown"
    el = experience_level.strip().lower()
    for keywords, bucket in _SENIORITY_RULES:
        if any(kw in el for kw in keywords):
            return bucket
    return "Unknown"


# ---------------------------------------------------------------------------
# Internal: per-segment scorer
# ---------------------------------------------------------------------------

def _score_segment(
    segment_skills: pd.DataFrame,
    total_jobs_in_segment: int,
    segment_type: str,
    segment_value: str,
    top_n: int,
) -> pd.DataFrame:
    """
    Compute demand scores for one segment slice of the skills DataFrame.

    Parameters
    ----------
    segment_skills      : Subset of skills_df for this segment.
    total_jobs_in_segment : Total distinct jobs in this segment (denominator).
    segment_type        : "global" | "role" | "seniority" | "city"
    segment_value       : "all" | role label | bucket | city name
    top_n               : How many top skills to return.

    Returns
    -------
    pd.DataFrame with standardised columns + rank.
    """
    if segment_skills.empty or total_jobs_in_segment == 0:
        return pd.DataFrame(columns=[
            "segment_type", "segment_value", "rank",
            "skill_canonical", "skill_category", "job_count", "demand_score",
        ])

    # Count distinct jobs per skill (avoid counting same job twice)
    counts = (
        segment_skills
        .groupby(["skill_canonical", "skill_category"], as_index=False)["job_id"]
        .nunique()
        .rename(columns={"job_id": "job_count"})
    )

    counts["demand_score"] = (counts["job_count"] / total_jobs_in_segment).round(4)
    counts = counts.sort_values("demand_score", ascending=False).head(top_n)
    counts["rank"] = range(1, len(counts) + 1)
    counts["segment_type"]  = segment_type
    counts["segment_value"] = segment_value

    return counts[[
        "segment_type", "segment_value", "rank",
        "skill_canonical", "skill_category",
        "job_count", "demand_score",
    ]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_demand_scores(
    skills_df: pd.DataFrame,
    jobs_df: pd.DataFrame,
    top_n_global: int = 20,
    top_n_segment: int = 10,
) -> dict[str, pd.DataFrame]:
    """
    Compute skill demand scores globally and by segment.

    Parameters
    ----------
    skills_df      : DataFrame from extracted_skills.csv.
                     Required columns: job_id, skill_canonical, skill_category,
                     role_category, extraction_source, confidence.
    jobs_df        : DataFrame from raw_jobs.csv.
                     Required columns: job_id, experience_level, city.
    top_n_global   : Number of top skills to return for the global ranking.
    top_n_segment  : Number of top skills per segment (role / seniority / city).

    Returns
    -------
    dict with four DataFrames:
        "global"       : Top N skills globally
        "by_role"      : Top N per role_category
        "by_seniority" : Top N per seniority bucket
        "by_city"      : Top N per city
    """
    if skills_df.empty or jobs_df.empty:
        logger.warning("compute_demand_scores: empty input — returning empty results.")
        return {k: pd.DataFrame() for k in ("global", "by_role", "by_seniority", "by_city")}

    total_jobs = jobs_df["job_id"].nunique()
    logger.info("Demand scoring: %d jobs, %d skill rows.", total_jobs, len(skills_df))

    # ── Add seniority bucket to a working copy of jobs_df ──────────────────
    jobs_work = jobs_df.copy()
    jobs_work["seniority"] = jobs_work["experience_level"].apply(_seniority_bucket)

    # ── Merge seniority and city onto skills for segmented analysis ─────────
    merge_cols = ["job_id", "seniority", "city"]
    enriched = skills_df.merge(
        jobs_work[merge_cols],
        on="job_id",
        how="left",
    )

    # ── Global ──────────────────────────────────────────────────────────────
    global_df = _score_segment(enriched, total_jobs, "global", "all", top_n_global)
    logger.info("Global top-%d computed.", len(global_df))

    # ── By role_category ────────────────────────────────────────────────────
    role_frames: list[pd.DataFrame] = []
    if "role_category" in enriched.columns:
        # Total jobs per role = distinct job_ids in that role (from jobs_work)
        jobs_work["role_category"] = (
            skills_df.drop_duplicates("job_id")
            .set_index("job_id")["role_category"]
            .reindex(jobs_work["job_id"])
            .values
        )
        role_totals = (
            jobs_work.dropna(subset=["role_category"])
            .groupby("role_category")["job_id"]
            .nunique()
        )
        for role, role_total in role_totals.items():
            role_slice = enriched[enriched["role_category"] == role]
            frame = _score_segment(
                role_slice, int(role_total), "role", str(role), top_n_segment
            )
            role_frames.append(frame)
    by_role_df = pd.concat(role_frames, ignore_index=True) if role_frames else pd.DataFrame()

    # ── By seniority ────────────────────────────────────────────────────────
    seniority_frames: list[pd.DataFrame] = []
    seniority_totals = (
        jobs_work[jobs_work["seniority"] != "Unknown"]
        .groupby("seniority")["job_id"]
        .nunique()
    )
    for seniority, sen_total in seniority_totals.items():
        sen_slice = enriched[enriched["seniority"] == seniority]
        frame = _score_segment(
            sen_slice, int(sen_total), "seniority", str(seniority), top_n_segment
        )
        seniority_frames.append(frame)
    by_seniority_df = (
        pd.concat(seniority_frames, ignore_index=True)
        if seniority_frames else pd.DataFrame()
    )

    # ── By city ─────────────────────────────────────────────────────────────
    city_frames: list[pd.DataFrame] = []
    # Only cities with at least 2 jobs (avoid noise from tiny samples)
    city_totals = (
        jobs_work[jobs_work["city"].notna()]
        .groupby("city")["job_id"]
        .nunique()
    )
    for city, city_total in city_totals.items():
        if city_total < 2:
            continue
        city_slice = enriched[enriched["city"] == city]
        frame = _score_segment(
            city_slice, int(city_total), "city", str(city), top_n_segment
        )
        city_frames.append(frame)
    by_city_df = (
        pd.concat(city_frames, ignore_index=True)
        if city_frames else pd.DataFrame()
    )

    return {
        "global":       global_df,
        "by_role":      by_role_df,
        "by_seniority": by_seniority_df,
        "by_city":      by_city_df,
    }
