"""
tests/test_analysis.py
=======================
Unit tests for analysis/demand_scorer.py, analysis/gap_analyzer.py,
and analysis/cooccurrence.py.

All tests use in-memory pandas DataFrames — no file I/O.

Run with:
    pytest tests/test_analysis.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd
import numpy as np

from analysis.demand_scorer import (
    compute_demand_scores,
    _seniority_bucket,
)
from analysis.gap_analyzer import (
    compute_gap_signals,
    DEMAND_THRESHOLD,
    SENIORITY_SKEW_THRESHOLD,
)
from analysis.cooccurrence import build_cooccurrence_matrix


# ===========================================================================
# Shared fixtures
# ===========================================================================

def _make_jobs_df(rows: list[dict]) -> pd.DataFrame:
    """Build a jobs DataFrame from a list of dicts."""
    defaults = {
        "job_id": "j000",
        "job_title": "Software Developer",
        "company_name": "TestCo",
        "city": "Cairo",
        "experience_level": "Experienced",
        "work_mode": "On-site",
        "job_type": "Full Time",
        "source_category": "IT-Software-Development",
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


def _make_skills_df(rows: list[dict]) -> pd.DataFrame:
    """Build a skills DataFrame from a list of dicts."""
    defaults = {
        "job_id": "j000",
        "skill_canonical": "Python",
        "skill_category": "programming_languages",
        "role_category": "Backend",
        "extraction_source": "wuzzuf_tag",
        "confidence": 1.0,
    }
    return pd.DataFrame([{**defaults, **r} for r in rows])


# ---------------------------------------------------------------------------
# Controlled fixture: 5 jobs, 3 skills, known distribution
# ---------------------------------------------------------------------------
#
# Jobs:
#   j001 – Backend  – Senior    – Cairo    – [Python, Docker]
#   j002 – Backend  – Entry     – Cairo    – [Python, Django]
#   j003 – Frontend – Mid       – Cairo    – [React, Python]
#   j004 – Backend  – Senior    – Alex.    – [Docker, Python]
#   j005 – DevOps   – Senior    – Alex.    – [Docker, Kubernetes]
#
# Skill demand:
#   Python  : 4/5 = 0.80
#   Docker  : 3/5 = 0.60
#   React   : 1/5 = 0.20
#   Django  : 1/5 = 0.20
#   Kubernetes : 1/5 = 0.20
#
# Python seniority: Senior (j001, j004) = 2, Entry (j002) = 1, Mid (j003) = 1
# Docker seniority: Senior (j001, j004, j005) = 3, Entry = 0

FIXTURE_JOBS = _make_jobs_df([
    {"job_id": "j001", "experience_level": "Senior Management", "city": "Cairo",        "job_title": "Senior Backend Developer"},
    {"job_id": "j002", "experience_level": "Entry Level",       "city": "Cairo",        "job_title": "Junior Backend Developer"},
    {"job_id": "j003", "experience_level": "Experienced",       "city": "Cairo",        "job_title": "React Frontend Developer"},
    {"job_id": "j004", "experience_level": "Senior Management", "city": "Alexandria",   "job_title": "Senior Backend Developer"},
    {"job_id": "j005", "experience_level": "Senior Management", "city": "Alexandria",   "job_title": "Senior DevOps Engineer"},
])

FIXTURE_SKILLS = _make_skills_df([
    # j001: Python, Docker
    {"job_id": "j001", "skill_canonical": "Python",     "skill_category": "programming_languages", "role_category": "Backend"},
    {"job_id": "j001", "skill_canonical": "Docker",     "skill_category": "devops_cloud",          "role_category": "Backend"},
    # j002: Python, Django
    {"job_id": "j002", "skill_canonical": "Python",     "skill_category": "programming_languages", "role_category": "Backend"},
    {"job_id": "j002", "skill_canonical": "Django",     "skill_category": "frameworks_libraries",  "role_category": "Backend"},
    # j003: React, Python
    {"job_id": "j003", "skill_canonical": "React",      "skill_category": "frameworks_libraries",  "role_category": "Frontend"},
    {"job_id": "j003", "skill_canonical": "Python",     "skill_category": "programming_languages", "role_category": "Frontend"},
    # j004: Docker, Python
    {"job_id": "j004", "skill_canonical": "Docker",     "skill_category": "devops_cloud",          "role_category": "Backend"},
    {"job_id": "j004", "skill_canonical": "Python",     "skill_category": "programming_languages", "role_category": "Backend"},
    # j005: Docker, Kubernetes
    {"job_id": "j005", "skill_canonical": "Docker",     "skill_category": "devops_cloud",          "role_category": "DevOps / Cloud"},
    {"job_id": "j005", "skill_canonical": "Kubernetes", "skill_category": "devops_cloud",          "role_category": "DevOps / Cloud"},
])


# ===========================================================================
# Tests: _seniority_bucket
# ===========================================================================

class TestSeniorityBucket:
    def test_entry_level(self):
        assert _seniority_bucket("Entry Level") == "Entry"

    def test_junior(self):
        assert _seniority_bucket("Junior") == "Entry"

    def test_fresh_graduate(self):
        assert _seniority_bucket("Fresh Graduate") == "Entry"

    def test_internship(self):
        assert _seniority_bucket("Internship") == "Entry"

    def test_senior_management(self):
        assert _seniority_bucket("Senior Management") == "Senior"

    def test_manager(self):
        assert _seniority_bucket("Manager") == "Senior"

    def test_director(self):
        assert _seniority_bucket("Director") == "Senior"

    def test_experienced_is_mid(self):
        assert _seniority_bucket("Experienced") == "Mid"

    def test_none_returns_unknown(self):
        assert _seniority_bucket(None) == "Unknown"

    def test_empty_string_returns_unknown(self):
        assert _seniority_bucket("") == "Unknown"

    def test_case_insensitive(self):
        assert _seniority_bucket("SENIOR DEVELOPER") == "Senior"
        assert _seniority_bucket("entry level") == "Entry"


# ===========================================================================
# Tests: compute_demand_scores — global
# ===========================================================================

class TestDemandScorerGlobal:
    def setup_method(self):
        self.results = compute_demand_scores(
            FIXTURE_SKILLS, FIXTURE_JOBS,
            top_n_global=20, top_n_segment=10,
        )
        self.global_df = self.results["global"]

    def test_returns_dict_with_four_keys(self):
        assert set(self.results.keys()) == {"global", "by_role", "by_seniority", "by_city"}

    def test_global_has_all_required_columns(self):
        required = {"rank", "skill_canonical", "skill_category", "job_count", "demand_score"}
        assert required.issubset(self.global_df.columns)

    def test_python_demand_score(self):
        # 4 out of 5 jobs → 0.80
        python_row = self.global_df[self.global_df["skill_canonical"] == "Python"]
        assert len(python_row) == 1
        assert float(python_row.iloc[0]["demand_score"]) == pytest.approx(0.80, abs=0.01)

    def test_docker_demand_score(self):
        # 3 out of 5 jobs → 0.60
        docker_row = self.global_df[self.global_df["skill_canonical"] == "Docker"]
        assert len(docker_row) == 1
        assert float(docker_row.iloc[0]["demand_score"]) == pytest.approx(0.60, abs=0.01)

    def test_python_ranks_first(self):
        top_skill = self.global_df.loc[self.global_df["rank"] == 1, "skill_canonical"].iloc[0]
        assert top_skill == "Python"

    def test_docker_ranks_second(self):
        second_skill = self.global_df.loc[self.global_df["rank"] == 2, "skill_canonical"].iloc[0]
        assert second_skill == "Docker"

    def test_demand_scores_sum_to_at_most_n_times_n(self):
        # All demand scores in [0, 1]
        assert (self.global_df["demand_score"] >= 0).all()
        assert (self.global_df["demand_score"] <= 1.0 + 1e-6).all()

    def test_ranks_are_sequential_from_1(self):
        expected_ranks = list(range(1, len(self.global_df) + 1))
        actual_ranks = self.global_df["rank"].tolist()
        assert actual_ranks == expected_ranks

    def test_job_count_is_correct(self):
        python_row = self.global_df[self.global_df["skill_canonical"] == "Python"]
        assert int(python_row.iloc[0]["job_count"]) == 4

    def test_empty_inputs_return_empty_dfs(self):
        result = compute_demand_scores(pd.DataFrame(), pd.DataFrame())
        assert all(v.empty for v in result.values())

    def test_top_n_global_limits_rows(self):
        result = compute_demand_scores(FIXTURE_SKILLS, FIXTURE_JOBS, top_n_global=2)
        assert len(result["global"]) <= 2


# ===========================================================================
# Tests: compute_demand_scores — segmented
# ===========================================================================

class TestDemandScorerSegmented:
    def setup_method(self):
        self.results = compute_demand_scores(
            FIXTURE_SKILLS, FIXTURE_JOBS,
            top_n_global=20, top_n_segment=10,
        )

    def test_by_role_has_backend_segment(self):
        by_role = self.results["by_role"]
        assert not by_role.empty
        assert "Backend" in by_role["segment_value"].values

    def test_backend_python_score_correct(self):
        by_role = self.results["by_role"]
        backend_python = by_role[
            (by_role["segment_value"] == "Backend") &
            (by_role["skill_canonical"] == "Python")
        ]
        # 3 Backend jobs (j001, j002, j004); all 3 mention Python → 1.0
        assert len(backend_python) == 1
        assert float(backend_python.iloc[0]["demand_score"]) == pytest.approx(1.0, abs=0.01)

    def test_by_seniority_has_entry_and_senior(self):
        by_sen = self.results["by_seniority"]
        assert not by_sen.empty
        segment_vals = set(by_sen["segment_value"].unique())
        assert "Senior" in segment_vals
        assert "Entry" in segment_vals

    def test_senior_segment_docker_appears(self):
        by_sen = self.results["by_seniority"]
        senior_docker = by_sen[
            (by_sen["segment_value"] == "Senior") &
            (by_sen["skill_canonical"] == "Docker")
        ]
        # 3 senior jobs; Docker in j001, j004, j005 → demand = 3/3 = 1.0
        assert len(senior_docker) == 1
        assert float(senior_docker.iloc[0]["demand_score"]) == pytest.approx(1.0, abs=0.01)

    def test_by_city_has_cairo(self):
        by_city = self.results["by_city"]
        assert "Cairo" in by_city["segment_value"].values

    def test_segment_type_column_populated(self):
        for key, df in self.results.items():
            if df is not None and not df.empty and "segment_type" in df.columns:
                assert df["segment_type"].notna().all()


# ===========================================================================
# Tests: compute_gap_signals
# ===========================================================================

class TestGapAnalyzer:
    def setup_method(self):
        demand_results = compute_demand_scores(FIXTURE_SKILLS, FIXTURE_JOBS)
        self.global_df = demand_results["global"]
        self.gap_df = compute_gap_signals(
            FIXTURE_SKILLS, FIXTURE_JOBS, self.global_df
        )

    def test_returns_dataframe(self):
        assert isinstance(self.gap_df, pd.DataFrame)

    def test_has_required_columns(self):
        required = {
            "rank", "skill_canonical", "skill_category",
            "demand_score", "demand_rank",
            "senior_mentions", "entry_mentions",
            "seniority_skew", "gap_signal_score", "is_emerging_gap",
        }
        assert required.issubset(self.gap_df.columns)

    def test_docker_seniority_skew(self):
        # Docker: Senior=3, Entry=0 → skew = 3/max(0,1) = 3.0
        docker_row = self.gap_df[self.gap_df["skill_canonical"] == "Docker"]
        assert len(docker_row) == 1
        assert float(docker_row.iloc[0]["seniority_skew"]) == pytest.approx(3.0, abs=0.01)

    def test_zero_entry_mentions_does_not_crash(self):
        # Docker has 0 entry mentions — must not raise ZeroDivisionError
        docker_row = self.gap_df[self.gap_df["skill_canonical"] == "Docker"]
        assert len(docker_row) == 1  # if it crashed, we would not reach here

    def test_seniority_skew_is_non_negative(self):
        assert (self.gap_df["seniority_skew"] >= 0).all()

    def test_gap_signal_score_is_non_negative(self):
        assert (self.gap_df["gap_signal_score"] >= 0).all()

    def test_ranked_by_gap_signal_score_descending(self):
        scores = self.gap_df["gap_signal_score"].tolist()
        assert scores == sorted(scores, reverse=True)

    def test_is_emerging_gap_is_boolean(self):
        assert self.gap_df["is_emerging_gap"].dtype == bool

    def test_docker_flagged_as_emerging_gap(self):
        # Docker: demand_score=0.6 (>0.05), seniority_skew=3.0 (>2.0) → True
        docker_row = self.gap_df[self.gap_df["skill_canonical"] == "Docker"]
        assert bool(docker_row.iloc[0]["is_emerging_gap"]) is True

    def test_react_not_flagged(self):
        # React: only 1/5 jobs (0.20) but single entry-level job → skew=0/1=0 < 2
        react_row = self.gap_df[self.gap_df["skill_canonical"] == "React"]
        if len(react_row) > 0:
            # Only 1 job total — skew is likely 0 (mid, not senior or entry)
            assert not bool(react_row.iloc[0]["is_emerging_gap"])

    def test_empty_inputs_return_empty_df(self):
        result = compute_gap_signals(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
        assert result.empty

    def test_demand_threshold_respected(self):
        # With threshold=0.99, only skills in all jobs would be flagged (Python at 0.8 excluded)
        demand_results = compute_demand_scores(FIXTURE_SKILLS, FIXTURE_JOBS)
        gap = compute_gap_signals(
            FIXTURE_SKILLS, FIXTURE_JOBS,
            global_scores=demand_results["global"],
            demand_threshold=0.99,
        )
        # No skill in our fixture reaches 0.99 demand
        assert gap["is_emerging_gap"].sum() == 0

    def test_skew_threshold_respected(self):
        # With skew_threshold=100, nothing should be flagged
        demand_results = compute_demand_scores(FIXTURE_SKILLS, FIXTURE_JOBS)
        gap = compute_gap_signals(
            FIXTURE_SKILLS, FIXTURE_JOBS,
            global_scores=demand_results["global"],
            seniority_skew_threshold=100.0,
        )
        assert gap["is_emerging_gap"].sum() == 0

    def test_ranks_are_sequential_from_1(self):
        expected = list(range(1, len(self.gap_df) + 1))
        assert self.gap_df["rank"].tolist() == expected


# ===========================================================================
# Tests: build_cooccurrence_matrix
# ===========================================================================

class TestCooccurrence:
    def setup_method(self):
        self.matrix = build_cooccurrence_matrix(FIXTURE_SKILLS, max_skills=50)

    def test_returns_dataframe(self):
        assert isinstance(self.matrix, pd.DataFrame)

    def test_matrix_is_square(self):
        assert self.matrix.shape[0] == self.matrix.shape[1]

    def test_index_equals_columns(self):
        assert list(self.matrix.index) == list(self.matrix.columns)

    def test_diagonal_is_zero(self):
        diag = self.matrix.values.diagonal()
        assert (diag == 0).all(), f"Non-zero diagonal elements: {diag}"

    def test_matrix_is_symmetric(self):
        vals = self.matrix.values
        assert (vals == vals.T).all(), "Matrix is not symmetric"

    def test_matrix_is_non_negative(self):
        assert (self.matrix.values >= 0).all()

    def test_python_docker_cooccurrence(self):
        # Python+Docker both in j001 and j004 → co-occur = 2
        assert self.matrix.loc["Python", "Docker"] == 2
        assert self.matrix.loc["Docker", "Python"] == 2  # symmetric

    def test_python_django_cooccurrence(self):
        # Python+Django both in j002 only → co-occur = 1
        assert self.matrix.loc["Python", "Django"] == 1
        assert self.matrix.loc["Django", "Python"] == 1  # symmetric

    def test_react_kubernetes_no_cooccurrence(self):
        # React and Kubernetes never appear in the same job → 0
        assert self.matrix.loc["React", "Kubernetes"] == 0
        assert self.matrix.loc["Kubernetes", "React"] == 0

    def test_docker_kubernetes_cooccurrence(self):
        # Docker+Kubernetes both in j005 → co-occur = 1
        assert self.matrix.loc["Docker", "Kubernetes"] == 1

    def test_max_skills_limits_matrix_size(self):
        # With max_skills=2, matrix should be 2×2
        matrix_small = build_cooccurrence_matrix(FIXTURE_SKILLS, max_skills=2)
        assert matrix_small.shape == (2, 2)

    def test_empty_skills_df_returns_empty_df(self):
        result = build_cooccurrence_matrix(pd.DataFrame(columns=["job_id", "skill_canonical"]))
        assert result.empty

    def test_single_skill_jobs_have_no_pairs(self):
        # If every job has only 1 skill, all off-diagonals should be 0
        single_skills = _make_skills_df([
            {"job_id": "s001", "skill_canonical": "Python"},
            {"job_id": "s002", "skill_canonical": "Docker"},
            {"job_id": "s003", "skill_canonical": "React"},
        ])
        matrix = build_cooccurrence_matrix(single_skills, max_skills=10)
        # All jobs have exactly 1 skill → no pairs → all cells = 0
        assert matrix.values.sum() == 0

    def test_dtype_is_integer(self):
        assert self.matrix.dtypes.unique()[0] == np.int64

    def test_skills_in_index_are_sorted(self):
        idx = list(self.matrix.index)
        assert idx == sorted(idx)


# ===========================================================================
# Integration: demand → gap → cooccurrence pipeline
# ===========================================================================

class TestAnalysisPipelineIntegration:
    """End-to-end test of the three analysis modules chained together."""

    def test_pipeline_chain_no_errors(self):
        demand_results = compute_demand_scores(FIXTURE_SKILLS, FIXTURE_JOBS)
        global_df = demand_results["global"]
        gap_df = compute_gap_signals(FIXTURE_SKILLS, FIXTURE_JOBS, global_df)
        cooc = build_cooccurrence_matrix(FIXTURE_SKILLS)

        assert not global_df.empty
        assert not gap_df.empty
        assert not cooc.empty

    def test_pipeline_outputs_consistent_skill_universe(self):
        demand_results = compute_demand_scores(FIXTURE_SKILLS, FIXTURE_JOBS)
        global_skills  = set(demand_results["global"]["skill_canonical"])
        gap_skills     = set(
            compute_gap_signals(
                FIXTURE_SKILLS, FIXTURE_JOBS, demand_results["global"]
            )["skill_canonical"]
        )
        cooc_skills = set(
            build_cooccurrence_matrix(FIXTURE_SKILLS).index
        )

        # All skills in gap analysis must be in the skills universe
        assert gap_skills.issubset(FIXTURE_SKILLS["skill_canonical"].unique())
        # All skills in co-occurrence must be in the skills universe
        assert cooc_skills.issubset(FIXTURE_SKILLS["skill_canonical"].unique())

    def test_python_is_top_skill_globally(self):
        demand_results = compute_demand_scores(FIXTURE_SKILLS, FIXTURE_JOBS)
        top = demand_results["global"].iloc[0]["skill_canonical"]
        assert top == "Python"


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
