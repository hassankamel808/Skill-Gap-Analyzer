"""
analysis/cooccurrence.py
========================
Pure function module — zero file I/O, zero side effects.

Builds an NxN symmetric skill co-occurrence matrix from job-skill pairs.

DEFINITION
----------
co_occur(A, B) = count of distinct jobs where BOTH skill A and skill B
                 appear in extracted_skills.

Properties guaranteed by construction
--------------------------------------
1. Symmetric   : M[A][B] == M[B][A]  ∀ A, B
2. Non-negative: M[A][B] ≥ 0         ∀ A, B
3. Zero diagonal: M[A][A] = 0        ∀ A  (a skill doesn't "co-occur" with itself)

ALGORITHM
---------
1. Group skills_df by job_id -> each group is the set of skills in that job.
2. For each job, iterate all unique pairs (A, B) where A < B alphabetically.
3. Increment matrix[A][B] and matrix[B][A] by 1.

This is O(J x K²) where J = jobs, K = avg skills per job.
For DEV_MODE (50 jobs, ~8 skills each) this is fast (< 1ms).
For production (~3400 jobs, ~10 skills each) this is ~340K operations — still fine.

Optionally restrict to top-N skills by global job_count to keep the matrix
manageable for the dashboard heatmap.

PUBLIC API
----------
build_cooccurrence_matrix(skills_df, max_skills) -> pd.DataFrame
    NxN DataFrame with skill names as both index and columns.
"""

from __future__ import annotations

import logging
from itertools import combinations

import pandas as pd

logger = logging.getLogger(__name__)


def build_cooccurrence_matrix(
    skills_df: pd.DataFrame,
    max_skills: int = 50,
) -> pd.DataFrame:
    """
    Build a symmetric skill co-occurrence matrix.

    Parameters
    ----------
    skills_df  : extracted_skills DataFrame.
                 Required columns: job_id, skill_canonical.
    max_skills : Restrict the matrix to the top N most-frequent skills
                 (by distinct job_count). Keeps the heatmap readable.
                 Set to 0 or None to include all skills.

    Returns
    -------
    pd.DataFrame
        Square NxN matrix, skill names as index and columns.
        dtype: int64.  Symmetric.  Diagonal = 0.

    Examples
    --------
    >>> matrix = build_cooccurrence_matrix(skills_df, max_skills=5)
    >>> assert matrix.loc["Python", "Docker"] == matrix.loc["Docker", "Python"]
    >>> assert (matrix.values.diagonal() == 0).all()
    """
    if skills_df.empty:
        logger.warning("build_cooccurrence_matrix: empty skills DataFrame.")
        return pd.DataFrame()

    required = {"job_id", "skill_canonical"}
    if not required.issubset(skills_df.columns):
        missing = required - set(skills_df.columns)
        raise ValueError(f"skills_df missing columns: {missing}")

    # ── Determine the skill universe ──────────────────────────────────────────
    if max_skills and max_skills > 0:
        # Top N skills by distinct job count
        top_skills = (
            skills_df
            .groupby("skill_canonical")["job_id"]
            .nunique()
            .nlargest(max_skills)
            .index
            .tolist()
        )
        skills_filtered = skills_df[skills_df["skill_canonical"].isin(top_skills)]
        logger.info(
            "Co-occurrence matrix: restricting to top %d skills (from %d total).",
            len(top_skills), skills_df["skill_canonical"].nunique(),
        )
    else:
        skills_filtered = skills_df
        top_skills = sorted(skills_filtered["skill_canonical"].unique().tolist())

    skill_universe = sorted(set(top_skills))
    n = len(skill_universe)

    if n == 0:
        return pd.DataFrame()

    # ── Initialise matrix ─────────────────────────────────────────────────────
    matrix = pd.DataFrame(0, index=skill_universe, columns=skill_universe, dtype="int64")

    # ── Build per-job skill sets ───────────────────────────────────────────────
    # Drop duplicates: one row per (job_id, skill) to avoid double-counting
    # the same skill mentioned multiple times for the same job.
    job_skill_sets = (
        skills_filtered
        .drop_duplicates(subset=["job_id", "skill_canonical"])
        .groupby("job_id")["skill_canonical"]
        .apply(set)
    )

    logger.info(
        "Building co-occurrence matrix from %d jobs x %d skills …",
        len(job_skill_sets), n,
    )

    # ── Increment for every pair within each job ───────────────────────────────
    pair_counts: dict[tuple[str, str], int] = {}

    for _, skill_set in job_skill_sets.items():
        # Restrict to skills in the universe (size limit applied above)
        relevant = sorted(skill_set & set(skill_universe))
        for skill_a, skill_b in combinations(relevant, 2):
            pair = (skill_a, skill_b)
            pair_counts[pair] = pair_counts.get(pair, 0) + 1

    # ── Populate the symmetric matrix ─────────────────────────────────────────
    for (skill_a, skill_b), count in pair_counts.items():
        matrix.loc[skill_a, skill_b] = count
        matrix.loc[skill_b, skill_a] = count  # enforce symmetry

    # ── Verify invariants (debug assertions) ──────────────────────────────────
    assert (matrix.values.diagonal() == 0).all(), "Diagonal must be zero"
    assert (matrix.values >= 0).all(), "Matrix must be non-negative"
    # Spot-check symmetry
    sample_idx = min(5, n)
    sub = matrix.iloc[:sample_idx, :sample_idx]
    assert (sub.values == sub.values.T).all(), "Matrix must be symmetric"

    logger.info(
        "Co-occurrence matrix complete: %dx%d, %d unique pairs.",
        n, n, len(pair_counts),
    )
    return matrix
