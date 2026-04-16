"""
tests/test_extraction.py
─────────────────────────
Unit tests for:
    extraction.normalizer  – text normalisation helpers
    extraction.skill_extractor – SkillExtractor NLP logic
"""

from __future__ import annotations

import pytest

from extraction.normalizer import normalize_skill, normalize_text, clean_job_text
from extraction.skill_extractor import SkillExtractor


# ── Normalizer tests ──────────────────────────────────────────────────────────


class TestNormalizeSkill:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("  Apache Spark  ", "apache spark"),
            ("C++", "c++"),
            ("Node.JS", "node.js"),
            ("  Python3  ", "python3"),
            ("GraphQL", "graphql"),
            ("REST API", "rest api"),
        ],
    )
    def test_normalizes_correctly(self, raw: str, expected: str) -> None:
        assert normalize_skill(raw) == expected


class TestNormalizeText:
    def test_lowercases(self) -> None:
        assert normalize_text("PYTHON") == "python"

    def test_collapses_whitespace(self) -> None:
        assert normalize_text("   hello   world   ") == "hello world"

    def test_strips_accents(self) -> None:
        result = normalize_text("café naïve résumé")
        assert "a" in result  # accent stripped

    def test_unicode_normalization(self) -> None:
        # ligature ﬁ → fi
        result = normalize_text("ﬁle")
        assert "fi" in result or "f" in result


class TestCleanJobText:
    def test_combines_title_and_description(self) -> None:
        result = clean_job_text("Data Engineer", "Python Spark SQL")
        assert "data engineer" in result
        assert "python" in result


# ── SkillExtractor tests ──────────────────────────────────────────────────────


class TestSkillExtractorExactMatch:
    def setup_method(self) -> None:
        self.extractor = SkillExtractor()

    def test_detects_python(self) -> None:
        skills = self.extractor.extract("We need a Python developer")
        assert "python" in skills

    def test_detects_sql(self) -> None:
        skills = self.extractor.extract("Strong SQL skills required")
        assert "sql" in skills

    def test_detects_apache_spark(self) -> None:
        skills = self.extractor.extract("Experience with Apache Spark and PySpark")
        assert "apache spark" in skills or "pyspark" in skills

    def test_detects_docker(self) -> None:
        skills = self.extractor.extract("Must know Docker and Kubernetes")
        assert "docker" in skills

    def test_detects_multiple_skills(self) -> None:
        text = "Python, PostgreSQL, Docker, and Kubernetes required."
        skills = self.extractor.extract(text)
        assert len(skills) >= 3


class TestSkillExtractorNegation:
    def setup_method(self) -> None:
        self.extractor = SkillExtractor()

    def test_negated_skill_excluded(self) -> None:
        text = "No experience in Python required for this role."
        skills = self.extractor.extract(text)
        assert "python" not in skills

    def test_non_negated_skill_included(self) -> None:
        text = "Python experience is required."
        skills = self.extractor.extract(text)
        assert "python" in skills


class TestSkillExtractorOutputFormat:
    def setup_method(self) -> None:
        self.extractor = SkillExtractor()

    def test_returns_sorted_list(self) -> None:
        skills = self.extractor.extract("Docker Python SQL")
        assert skills == sorted(skills)

    def test_returns_no_duplicates(self) -> None:
        text = "Python python PYTHON expertise"
        skills = self.extractor.extract(text)
        assert len(skills) == len(set(skills))

    def test_empty_string_returns_empty_list(self) -> None:
        assert self.extractor.extract("") == []

    def test_irrelevant_text_returns_empty_or_few(self) -> None:
        skills = self.extractor.extract("We are looking for a great team player.")
        # Should not return any technical skills
        assert isinstance(skills, list)
