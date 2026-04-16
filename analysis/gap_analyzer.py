"""
analysis/gap_analyzer.py
========================
Pure function module — zero file I/O, zero side effects.

Computes skill-gap signals by combining demand rank with seniority skew.

THEORY
------
A "skill gap" in the labour market means:
  - The skill is highly demanded (appears in many job postings)  AND
  - It skews strongly toward senior roles (few entry-level jobs mention it)

This combination suggests the market cannot find enough experienced
practitioners — the classic emerging skill gap.

seniority_skew = senior_mentions / max(entry_mentions, 1)
    (max(..., 1) prevents division by zero for skills with no entry roles)

gap_signal_score = demand_score * log1p(seniority_skew)
    This combines high demand with disproportionate seniority skew.
    log1p dampens extreme skews from skills with near-zero entry mentions.

is_emerging_gap = True when:
    demand_score >= DEMAND_THRESHOLD  (>= 1% of jobs mention this skill)
    seniority_skew >= SKEW_THRESHOLD  (Sr mentions >= 1.5x entry mentions)

Thresholds are recalibrated for production datasets (4,000+ jobs).
See the DEMAND_THRESHOLD/SENIORITY_SKEW_THRESHOLD constants below.

PUBLIC API
----------
compute_gap_signals(skills_df, jobs_df, global_scores,
                    demand_threshold, seniority_skew_threshold)
    -> pd.DataFrame

OUTPUT COLUMNS
--------------
rank, skill_canonical, skill_category, demand_score, demand_rank,
senior_mentions, entry_mentions, seniority_skew, gap_signal_score,
is_emerging_gap
"""

from __future__ import annotations

import logging
import math

import pandas as pd

from analysis.demand_scorer import _seniority_bucket

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds (single source of truth)
# ---------------------------------------------------------------------------
#
# These thresholds were recalibrated for production-scale datasets (~4,000+ jobs).
# At that scale the Law of Large Numbers smooths extreme skews and demand_score
# values are naturally smaller (e.g. a skill in 100 of 4,000 jobs = 2.5%, while
# the same skill in 5 of 52 jobs = 9.6%).
#
# Calibration targets:
#   - Flag the top ~10-15% of skills by gap urgency (not a fixed count).
#   - demand_score >= 0.01 means the skill appears in ≥ 1% of all jobs.
#     At 4,000 jobs that equals ≥ 40 distinct job postings — a meaningful signal.
#   - seniority_skew >= 1.5 means senior mentions are at least 1.5× entry.
#     This is strict enough to exclude balanced skills while capturing
#     skills that are clearly experience-gated in the Egyptian market.

# Minimum fraction of total jobs to be considered "high demand".
# Changed: 0.05 -> 0.01  (5% -> 1% of all jobs)
DEMAND_THRESHOLD: float = 0.01

# Minimum senior_mentions / entry_mentions ratio to be flagged as a gap skill.
# Changed: 2.0x -> 1.5x  (2× requirement -> 1.5× requirement)
SENIORITY_SKEW_THRESHOLD: float = 1.5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_gap_signals(
    skills_df: pd.DataFrame,
    jobs_df: pd.DataFrame,
    global_scores: pd.DataFrame,
    demand_threshold: float = DEMAND_THRESHOLD,
    seniority_skew_threshold: float = SENIORITY_SKEW_THRESHOLD,
) -> pd.DataFrame:
    """
    Compute seniority skew and gap signal scores for all skills.

    Parameters
    ----------
    skills_df         : extracted_skills DataFrame (job_id, skill_canonical,
                        skill_category, role_category, confidence, ...).
    jobs_df           : raw_jobs DataFrame (job_id, experience_level, ...).
    global_scores     : "global" DataFrame from compute_demand_scores()
                        — used to look up demand_score and demand_rank.
    demand_threshold  : Min demand_score to be flagged as an emerging gap.
    seniority_skew_threshold : Min skew ratio for emerging gap flag.

    Returns
    -------
    pd.DataFrame
        Ranked by gap_signal_score descending.
        Columns: rank, skill_canonical, skill_category, demand_score,
                 demand_rank, senior_mentions, mid_mentions, entry_mentions,
                 seniority_skew, gap_signal_score, is_emerging_gap.
    """
    if skills_df.empty or jobs_df.empty or global_scores.empty:
        logger.warning("compute_gap_signals: empty input — returning empty DataFrame.")
        return pd.DataFrame()

    # ── Add seniority bucket to jobs ──────────────────────────────────────────
    jobs_work = jobs_df[["job_id", "experience_level"]].copy()
    jobs_work["seniority"] = jobs_work["experience_level"].apply(_seniority_bucket)

    # ── Join seniority onto every skill row ───────────────────────────────────
    merged = skills_df.merge(jobs_work[["job_id", "seniority"]], on="job_id", how="left")
    merged["seniority"] = merged["seniority"].fillna("Unknown")

    # ── Count distinct jobs per (skill, seniority) ────────────────────────────
    counts = (
        merged
        .groupby(["skill_canonical", "seniority"])["job_id"]
        .nunique()
        .unstack(fill_value=0)
        .reset_index()
    )

    # Ensure all seniority bucket columns are present (some may be absent in small samples)
    for col in ("Entry", "Mid", "Senior", "Unknown"):
        if col not in counts.columns:
            counts[col] = 0

    counts = counts.rename(columns={
        "Entry":   "entry_mentions",
        "Mid":     "mid_mentions",
        "Senior":  "senior_mentions",
        "Unknown": "unknown_mentions",
    })

    # ── Compute seniority_skew ────────────────────────────────────────────────
    # senior_mentions / max(entry_mentions, 1) — prevents ZeroDivisionError
    counts["seniority_skew"] = (
        counts["senior_mentions"] / counts["entry_mentions"].clip(lower=1)
    ).round(4)

    # ── Compute gap_signal_score ──────────────────────────────────────────────
    # Merge in demand_score from the global scores table
    score_map = global_scores.set_index("skill_canonical")["demand_score"].to_dict()
    rank_map  = global_scores.set_index("skill_canonical")["rank"].to_dict()

    counts["demand_score"] = counts["skill_canonical"].map(score_map).fillna(0.0)
    counts["demand_rank"]  = counts["skill_canonical"].map(rank_map).fillna(9999).astype(int)

    # gap_signal_score combines demand x log1p(skew) — high on both dimensions wins
    counts["gap_signal_score"] = (
        counts["demand_score"] * counts["seniority_skew"].apply(lambda s: math.log1p(s))
    ).round(4)

    # ── Flag emerging gap skills ──────────────────────────────────────────────
    counts["is_emerging_gap"] = (
        (counts["demand_score"] >= demand_threshold) &
        (counts["seniority_skew"] >= seniority_skew_threshold)
    )

    # ── Sort and rank ─────────────────────────────────────────────────────────
    counts = counts.sort_values("gap_signal_score", ascending=False).reset_index(drop=True)
    counts["rank"] = range(1, len(counts) + 1)

    # ── Get skill_category for each skill (may not have been in global_scores) ─
    cat_map = skills_df.drop_duplicates("skill_canonical").set_index("skill_canonical")
    if "skill_category" in cat_map.columns:
        cat_map = cat_map["skill_category"].to_dict()
    else:
        cat_map = {}
    counts["skill_category"] = counts["skill_canonical"].map(cat_map).fillna("unknown")

    logger.info(
        "Gap analysis: %d skills scored, %d flagged as emerging gaps.",
        len(counts),
        counts["is_emerging_gap"].sum(),
    )

    return counts[[
        "rank",
        "skill_canonical",
        "skill_category",
        "demand_score",
        "demand_rank",
        "senior_mentions",
        "mid_mentions",
        "entry_mentions",
        "seniority_skew",
        "gap_signal_score",
        "is_emerging_gap",
    ]].reset_index(drop=True)
