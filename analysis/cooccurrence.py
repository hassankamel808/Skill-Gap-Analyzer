"""
analysis/cooccurrence.py
────────────────────────
Builds a skill co-occurrence matrix from job postings: how often any two
skills appear together in the same job description.

The co-occurrence count between skills A and B is the number of job
postings that list both A and B in their extracted skills.

Outputs
───────
A symmetric ``pd.DataFrame`` (pivot table) where index and columns are
canonical skill names and values are co-occurrence counts.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from itertools import combinations

import pandas as pd

logger = logging.getLogger(__name__)


class CooccurrenceAnalyzer:
    """
    Computes pairwise skill co-occurrence counts.

    Parameters
    ----------
    records:
        List of dicts, each with a ``skills`` key (list of canonical
        skill strings) for one job posting.
    min_count:
        Minimum co-occurrence count to include a pair in the output.
        Pairs below this threshold are excluded.  Defaults to 2.
    """

    def __init__(self, records: list[dict], min_count: int = 2) -> None:
        self._records = records
        self._min_count = min_count

    # ── Public API ────────────────────────────────────────────

    def matrix(self) -> pd.DataFrame:
        """
        Return the symmetric co-occurrence matrix as a DataFrame.

        Returns
        -------
        pd.DataFrame
            Symmetric matrix; index and columns are skill names; values
            are integer co-occurrence counts.
        """
        pair_counts: dict[tuple[str, str], int] = defaultdict(int)

        for record in self._records:
            skills = sorted(set(record.get("skills", [])))
            for a, b in combinations(skills, 2):
                pair_counts[(a, b)] += 1

        if not pair_counts:
            logger.warning("No skill pairs found for co-occurrence analysis.")
            return pd.DataFrame()

        filtered = {k: v for k, v in pair_counts.items() if v >= self._min_count}

        all_skills = sorted({s for pair in filtered for s in pair})
        matrix = pd.DataFrame(0, index=all_skills, columns=all_skills)

        for (a, b), count in filtered.items():
            matrix.at[a, b] = count
            matrix.at[b, a] = count

        logger.info(
            "Co-occurrence matrix built: %d skills, %d pairs (min_count=%d).",
            len(all_skills),
            len(filtered),
            self._min_count,
        )
        return matrix

    def top_pairs(self, n: int = 20) -> pd.DataFrame:
        """
        Return the top-*n* most frequently co-occurring skill pairs.

        Returns
        -------
        pd.DataFrame
            Columns: skill_a, skill_b, count.
        """
        pair_counts: dict[tuple[str, str], int] = defaultdict(int)
        for record in self._records:
            skills = sorted(set(record.get("skills", [])))
            for a, b in combinations(skills, 2):
                pair_counts[(a, b)] += 1

        df = pd.DataFrame(
            [(a, b, c) for (a, b), c in pair_counts.items()],
            columns=["skill_a", "skill_b", "count"],
        )
        return df.sort_values("count", ascending=False).head(n).reset_index(drop=True)
