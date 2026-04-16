"""
analysis/demand_scorer.py
─────────────────────────
Computes normalised demand scores for each skill extracted across the
entire job-posting corpus.

Outputs
───────
A ``pd.DataFrame`` with columns:
    skill           – canonical skill name
    raw_count       – absolute frequency across all postings
    demand_score    – min-max normalised score in [0, 1]
    pct_of_postings – fraction of postings that mention the skill
"""

from __future__ import annotations

import logging
from collections import Counter

import pandas as pd

logger = logging.getLogger(__name__)


class DemandScorer:
    """
    Calculates market-demand scores from extracted skill lists.

    Parameters
    ----------
    records:
        Iterable of dicts, each with a ``skills`` key containing a list
        of canonical skill strings for one job posting.
    """

    def __init__(self, records: list[dict]) -> None:
        self._records = records

    # ── Public API ────────────────────────────────────────────

    def score(self) -> pd.DataFrame:
        """
        Return a DataFrame of skills ranked by demand score.

        Returns
        -------
        pd.DataFrame
            Columns: skill, raw_count, demand_score, pct_of_postings.
            Sorted descending by demand_score.
        """
        total_postings = len(self._records)
        if total_postings == 0:
            logger.warning("No records provided to DemandScorer.")
            return pd.DataFrame(
                columns=["skill", "raw_count", "demand_score", "pct_of_postings"]
            )

        counter: Counter[str] = Counter()
        for record in self._records:
            skills = record.get("skills", [])
            counter.update(skills)

        df = pd.DataFrame(counter.items(), columns=["skill", "raw_count"])
        df["pct_of_postings"] = df["raw_count"] / total_postings

        min_count = df["raw_count"].min()
        max_count = df["raw_count"].max()
        if max_count > min_count:
            df["demand_score"] = (df["raw_count"] - min_count) / (max_count - min_count)
        else:
            df["demand_score"] = 1.0

        df.sort_values("demand_score", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)
        logger.info("Scored %d unique skills across %d postings.", len(df), total_postings)
        return df
