"""
analysis/gap_analyzer.py
────────────────────────
Identifies seniority-level skill gaps: skills that are predominantly
required at a specific seniority tier, revealing where market demand
skews towards (or away from) entry-level vs. senior-level talent.

Methodology
───────────
For every skill *s* and seniority level *l* compute:

    skew(s, l) = count(s, l) / total_count(s)

A high skew value for (s, "senior") means *s* is mostly demanded by
senior roles — signalling a potential supply gap for that skill.

Outputs
───────
A ``pd.DataFrame`` with columns:
    skill, seniority, count, total_count, skew, gap_flag
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

_SENIORITY_ORDER = ["entry", "mid", "senior", "lead"]
_GAP_SKEW_THRESHOLD = 0.6  # >60 % concentration signals a gap


class GapAnalyzer:
    """
    Detects seniority-skewed skills from job posting records.

    Parameters
    ----------
    records:
        List of dicts with keys ``skills`` (list[str]) and
        ``seniority`` (str: "entry" | "mid" | "senior" | "lead").
    """

    def __init__(self, records: list[dict]) -> None:
        self._records = records

    # ── Public API ────────────────────────────────────────────

    def analyze(self) -> pd.DataFrame:
        """
        Return a seniority-skill skew DataFrame with gap flags.

        Returns
        -------
        pd.DataFrame
            Columns: skill, seniority, count, total_count, skew, gap_flag.
        """
        rows = []
        for record in self._records:
            seniority = record.get("seniority", "mid")
            for skill in record.get("skills", []):
                rows.append({"skill": skill, "seniority": seniority})

        if not rows:
            logger.warning("No rows to analyse in GapAnalyzer.")
            return pd.DataFrame(
                columns=["skill", "seniority", "count", "total_count", "skew", "gap_flag"]
            )

        df = pd.DataFrame(rows)
        grouped = df.groupby(["skill", "seniority"]).size().reset_index(name="count")

        totals = grouped.groupby("skill")["count"].sum().reset_index(name="total_count")
        merged = grouped.merge(totals, on="skill")
        merged["skew"] = merged["count"] / merged["total_count"]
        merged["gap_flag"] = merged["skew"] >= _GAP_SKEW_THRESHOLD

        merged["seniority"] = pd.Categorical(
            merged["seniority"], categories=_SENIORITY_ORDER, ordered=True
        )
        merged.sort_values(["skill", "seniority"], inplace=True)
        merged.reset_index(drop=True, inplace=True)

        flagged = merged[merged["gap_flag"]].shape[0]
        logger.info("Gap analysis complete. %d seniority-skill gaps flagged.", flagged)
        return merged
