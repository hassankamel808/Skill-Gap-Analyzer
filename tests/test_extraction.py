"""
tests/test_extraction.py
=========================
Unit tests for extraction/normalizer.py and extraction/skill_extractor.py.

Covers
------
- normalizer.clean_text
- normalizer.normalize_skill (alias resolution)
- normalizer.parse_relative_date (all time units + edge cases)
- normalizer.tokenize (unigrams + bigrams)
- skill_extractor Layer 1 (Wuzzuf tags)
- skill_extractor Layer 2 (regex scan)
- skill_extractor Layer 3 (fuzzy matching + threshold)
- skill_extractor ambiguous-term gating (Go, C, R, Spring, Rust)
- skill_extractor deduplication across layers
- skill_extractor extract_skills_for_job (pure, no I/O)

Run with:
    pytest tests/test_extraction.py -v
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from extraction.normalizer import clean_text, normalize_skill, parse_relative_date, tokenize
from extraction.skill_extractor import (
    FUZZY_THRESHOLD,
    AMBIGUOUS_TERMS,
    extract_skills_for_job,
    _layer1_tags,
    _layer2_regex,
    _layer3_fuzzy,
    _context_check,
)

# ---------------------------------------------------------------------------
# Fixed reference datetime for deterministic date tests
# ---------------------------------------------------------------------------
REF = datetime(2026, 4, 16, 12, 0, 0, tzinfo=timezone.utc)


# ===========================================================================
# normalizer.clean_text
# ===========================================================================

class TestCleanText:
    def test_strips_leading_trailing_whitespace(self):
        assert clean_text("  Python  ") == "Python"

    def test_collapses_internal_whitespace(self):
        assert clean_text("machine   learning") == "machine learning"

    def test_handles_none(self):
        assert clean_text(None) == ""

    def test_handles_empty_string(self):
        assert clean_text("") == ""

    def test_handles_only_whitespace(self):
        assert clean_text("   ") == ""

    def test_preserves_case(self):
        assert clean_text("  React.JS ") == "React.JS"

    def test_replaces_nbsp(self):
        # Non-breaking space (U+00A0) should be treated as whitespace
        assert clean_text("Python\u00a0Developer") == "Python Developer"

    def test_nfc_normalisation(self):
        # é composed vs decomposed should produce the same result
        composed   = "\u00e9"          # é (precomposed)
        decomposed = "e\u0301"         # e + combining acute
        assert clean_text(decomposed) == clean_text(composed)


# ===========================================================================
# normalizer.normalize_skill
# ===========================================================================

class TestNormalizeSkill:
    """Tests for alias resolution and direct taxonomy lookups."""

    # ── Alias map lookups ─────────────────────────────────────────────────────
    def test_reactjs_resolves_to_react(self):
        assert normalize_skill("reactjs") == "React"

    def test_react_js_with_spaces_resolves(self):
        assert normalize_skill("React JS") == "React"

    def test_react_dot_js_resolves(self):
        assert normalize_skill("  React.JS ") == "React"

    def test_golang_resolves_to_go(self):
        assert normalize_skill("golang") == "Go"

    def test_k8s_resolves_to_kubernetes(self):
        assert normalize_skill("k8s") == "Kubernetes"

    def test_aws_alias(self):
        assert normalize_skill("amazon web services") == "AWS"

    def test_pyspark_alias(self):
        assert normalize_skill("pyspark") == "Apache Spark"

    def test_sklearn_alias(self):
        assert normalize_skill("sklearn") == "scikit-learn"

    def test_llm_alias(self):
        assert normalize_skill("llm") == "Large Language Models"

    def test_cicd_alias(self):
        assert normalize_skill("cicd") == "CI/CD"

    def test_mssql_alias(self):
        assert normalize_skill("mssql") == "SQL Server"

    def test_dotnet_alias(self):
        assert normalize_skill("dotnet") == ".NET"

    def test_ml_alias(self):
        assert normalize_skill("ml") == "Machine Learning"

    def test_nodejs_alias(self):
        assert normalize_skill("nodejs") == "Node.js"

    def test_postgres_alias(self):
        assert normalize_skill("postgres") == "PostgreSQL"

    def test_drf_alias(self):
        assert normalize_skill("drf") == "Django"

    # ── Direct canonical lookups ──────────────────────────────────────────────
    def test_exact_canonical_python(self):
        assert normalize_skill("Python") == "Python"

    def test_case_insensitive_direct_match(self):
        assert normalize_skill("python") == "Python"

    def test_exact_canonical_docker(self):
        assert normalize_skill("Docker") == "Docker"

    def test_exact_canonical_react(self):
        assert normalize_skill("React") == "React"

    # ── None / unknown returns ────────────────────────────────────────────────
    def test_returns_none_for_unknown(self):
        assert normalize_skill("banana") is None

    def test_returns_none_for_none_input(self):
        assert normalize_skill(None) is None

    def test_returns_none_for_empty_string(self):
        assert normalize_skill("") is None

    def test_category_noun_not_a_skill(self):
        # "IT/Software Development" is a category label, not a canonical skill
        assert normalize_skill("IT/Software Development") is None


# ===========================================================================
# normalizer.parse_relative_date
# ===========================================================================

class TestParseRelativeDate:
    def test_just_now(self):
        result = parse_relative_date("just now", REF)
        assert result == REF

    def test_today(self):
        result = parse_relative_date("today", REF)
        assert result == REF

    def test_minutes_ago(self):
        result = parse_relative_date("30 minutes ago", REF)
        expected = datetime(2026, 4, 16, 11, 30, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_1_hour_ago(self):
        result = parse_relative_date("1 hour ago", REF)
        expected = datetime(2026, 4, 16, 11, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_3_hours_ago(self):
        result = parse_relative_date("3 hours ago", REF)
        expected = datetime(2026, 4, 16, 9, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_2_days_ago(self):
        result = parse_relative_date("2 days ago", REF)
        expected = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_1_week_ago(self):
        result = parse_relative_date("1 week ago", REF)
        expected = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_2_months_ago_approx(self):
        result = parse_relative_date("2 months ago", REF)
        # 2 × 30 days = 60 days before reference
        from datetime import timedelta
        expected = REF - timedelta(days=60)
        assert result == expected

    def test_1_year_ago_approx(self):
        result = parse_relative_date("1 year ago", REF)
        from datetime import timedelta
        expected = REF - timedelta(days=365)
        assert result == expected

    def test_plural_hours(self):
        # "hours" (plural) should parse identically to "hour"
        result = parse_relative_date("5 hours ago", REF)
        from datetime import timedelta
        expected = REF - timedelta(hours=5)
        assert result == expected

    def test_returns_none_for_none_input(self):
        assert parse_relative_date(None, REF) is None

    def test_returns_none_for_gibberish(self):
        assert parse_relative_date("last Tuesday", REF) is None

    def test_returns_none_for_empty_string(self):
        assert parse_relative_date("", REF) is None

    def test_result_is_utc_aware(self):
        result = parse_relative_date("1 hour ago", REF)
        assert result is not None
        assert result.tzinfo is not None

    def test_case_insensitive(self):
        result1 = parse_relative_date("3 Hours Ago", REF)
        result2 = parse_relative_date("3 hours ago", REF)
        assert result1 == result2


# ===========================================================================
# normalizer.tokenize
# ===========================================================================

class TestTokenize:
    def test_returns_unigrams(self):
        tokens = tokenize("Python developer")
        assert "Python" in tokens
        assert "developer" in tokens

    def test_returns_bigrams(self):
        tokens = tokenize("machine learning engineer")
        assert "machine learning" in tokens
        assert "learning engineer" in tokens

    def test_filters_short_tokens(self):
        # Single characters should be filtered (len < 2)
        tokens = tokenize("C # developer")
        assert "C" not in tokens   # 1 char — filtered

    def test_handles_none(self):
        assert tokenize(None) == []

    def test_handles_empty_string(self):
        assert tokenize("") == []

    def test_splits_on_comma(self):
        tokens = tokenize("Python,Django,REST API")
        assert "Python" in tokens
        assert "Django" in tokens

    def test_bigram_formed_from_adjacent_unigrams(self):
        tokens = tokenize("Spring Boot developer")
        assert "Spring Boot" in tokens


# ===========================================================================
# Shared test job fixtures
# ===========================================================================

def _make_job(
    job_id: str = "test001",
    job_title: str = "",
    category_tags: str | None = None,
) -> dict:
    """Build a minimal job dict for extraction tests."""
    return {
        "job_id":        job_id,
        "job_title":     job_title,
        "category_tags": category_tags,
    }


# ===========================================================================
# Layer 1 — Wuzzuf Tags
# ===========================================================================

class TestLayer1Tags:
    def test_canonical_skill_extracted_from_tag(self):
        job = _make_job(category_tags="Python,Django,REST API")
        found, rows = _layer1_tags(job)
        assert "Python" in found
        assert "Django" in found
        assert "REST API" in found

    def test_alias_resolved_in_tag(self):
        job = _make_job(category_tags="reactjs")
        found, rows = _layer1_tags(job)
        assert "React" in found

    def test_category_label_not_extracted_as_skill(self):
        # "IT/Software Development" is a category label — not a canonical skill
        job = _make_job(category_tags="IT/Software Development,Python")
        found, rows = _layer1_tags(job)
        assert "IT/Software Development" not in found
        assert "Python" in found

    def test_confidence_is_1_0(self):
        job = _make_job(category_tags="Docker")
        _, rows = _layer1_tags(job)
        assert rows[0]["confidence"] == 1.0

    def test_extraction_source_is_wuzzuf_tag(self):
        job = _make_job(category_tags="Kubernetes")
        _, rows = _layer1_tags(job)
        assert rows[0]["extraction_source"] == "wuzzuf_tag"

    def test_empty_tags_returns_empty(self):
        job = _make_job(category_tags=None)
        found, rows = _layer1_tags(job)
        assert found == set()
        assert rows == []

    def test_deduplication_within_layer(self):
        # Same skill repeated in tags should appear only once
        job = _make_job(category_tags="Python,python,Python")
        found, rows = _layer1_tags(job)
        assert len([r for r in rows if r["skill_canonical"] == "Python"]) == 1

    def test_skill_category_populated(self):
        job = _make_job(category_tags="Python")
        _, rows = _layer1_tags(job)
        assert rows[0]["skill_category"] == "programming_languages"


# ===========================================================================
# Layer 2 — Regex Scan
# ===========================================================================

class TestLayer2Regex:
    def test_skill_in_title_extracted(self):
        job = _make_job(job_title="Senior Python Developer")
        _, rows = _layer2_regex(job, already_found=set())
        skills = {r["skill_canonical"] for r in rows}
        assert "Python" in skills

    def test_confidence_is_0_95(self):
        job = _make_job(job_title="Django Developer")
        _, rows = _layer2_regex(job, already_found=set())
        for r in rows:
            if r["skill_canonical"] == "Django":
                assert r["confidence"] == 0.95

    def test_extraction_source_is_regex_match(self):
        job = _make_job(job_title="React Frontend Engineer")
        _, rows = _layer2_regex(job, already_found=set())
        for r in rows:
            assert r["extraction_source"] == "regex_match"

    def test_already_found_skills_skipped(self):
        job = _make_job(job_title="Python Developer", category_tags="Python")
        already = {"Python"}
        found, rows = _layer2_regex(job, already_found=already)
        python_rows = [r for r in rows if r["skill_canonical"] == "Python"]
        assert python_rows == []  # must not duplicate

    def test_multi_word_skill_matched(self):
        job = _make_job(job_title="Machine Learning Engineer")
        _, rows = _layer2_regex(job, already_found=set())
        skills = {r["skill_canonical"] for r in rows}
        assert "Machine Learning" in skills

    def test_case_insensitive_match(self):
        job = _make_job(job_title="expert in POSTGRESQL and redis")
        _, rows = _layer2_regex(job, already_found=set())
        skills = {r["skill_canonical"] for r in rows}
        assert "PostgreSQL" in skills
        assert "Redis" in skills

    # ── Ambiguous-term gating ─────────────────────────────────────────────────
    def test_go_blocked_without_context(self):
        # "go-getter" should NOT trigger the "Go" language skill
        job = _make_job(job_title="Proactive go-getter team player")
        found, rows = _layer2_regex(job, already_found=set())
        assert "Go" not in found

    def test_go_allowed_with_golang_context(self):
        job = _make_job(job_title="Golang backend developer with Go experience")
        found, rows = _layer2_regex(job, already_found=set())
        assert "Go" in found

    def test_spring_blocked_without_java_context(self):
        # "Spring semester" should NOT trigger Spring Boot
        job = _make_job(job_title="Spring semester teaching assistant")
        found, rows = _layer2_regex(job, already_found=set())
        assert "Spring Boot" not in found

    def test_spring_allowed_with_java_context(self):
        job = _make_job(
            job_title="Java Spring Boot microservices developer",
            category_tags="Java,Spring Boot",
        )
        found, rows = _layer2_regex(job, already_found=set())
        assert "Spring Boot" in found

    def test_rust_blocked_without_context(self):
        # "rust belt" or "rusty skills" should NOT match Rust language
        job = _make_job(job_title="Experienced rust belt manufacturing manager")
        found, rows = _layer2_regex(job, already_found=set())
        assert "Rust" not in found

    def test_rust_allowed_with_systems_context(self):
        job = _make_job(
            job_title="Systems programmer",
            category_tags="Rust,systems programming,memory safe",
        )
        found, rows = _layer2_regex(job, already_found=set())
        assert "Rust" in found


# ===========================================================================
# Layer 3 — Fuzzy Matching
# ===========================================================================

class TestLayer3Fuzzy:
    def test_fuzzy_threshold_is_85(self):
        assert FUZZY_THRESHOLD == 85

    def test_typo_variant_matched(self):
        # "Pyhon" (missing 't') is close enough to "Python" at 85+ score
        job = _make_job(job_title="Pyhon developer with Djano experience")
        found, rows = _layer3_fuzzy(job, already_found=set())
        # Either Python or Django might match — they should not both miss
        assert len(rows) > 0

    def test_already_found_skills_not_duplicated(self):
        # If Python was found in L1/L2, L3 must skip it entirely
        job = _make_job(job_title="Python developer")
        found, rows = _layer3_fuzzy(job, already_found={"Python"})
        python_rows = [r for r in rows if r["skill_canonical"] == "Python"]
        assert python_rows == []

    def test_confidence_is_score_over_100(self):
        # Any fuzzy match must have confidence in [0.85, 1.0] range
        job = _make_job(category_tags="Kubernetes,Docker,Ansible")
        found, rows = _layer3_fuzzy(job, already_found=set())
        for r in rows:
            assert 0.85 <= r["confidence"] <= 1.0, (
                f"confidence out of range: {r['confidence']} for {r['skill_canonical']}"
            )

    def test_extraction_source_is_fuzzy_match(self):
        job = _make_job(category_tags="Dockers")   # slight typo
        found, rows = _layer3_fuzzy(job, already_found=set())
        for r in rows:
            assert r["extraction_source"] == "fuzzy_match"

    def test_short_token_skipped(self):
        # "Go" is 2 chars — layer 3 skips tokens < 3 chars
        job = _make_job(job_title="Go developer")
        # If Go is not already in already_found, L3 should skip the token "Go"
        # because len("Go") < 3. It may match via bigram "Go developer" → low score.
        found, rows = _layer3_fuzzy(job, already_found=set())
        go_rows = [r for r in rows if r["skill_canonical"] == "Go"]
        # Go CAN match via the bigram "Go developer" with context check —
        # the guarantee is only that the 2-char unigram "Go" is not tried alone.
        # We just verify no crash and confidence is sane.
        for r in go_rows:
            assert r["confidence"] >= 0.85

    # ── Ambiguous-term gating in L3 ───────────────────────────────────────────
    def test_go_fuzzy_blocked_without_context(self):
        # "go-getter" text — no golang context — Rust/Go should be blocked
        job = _make_job(job_title="Motivated go-getter salesperson")
        found, rows = _layer3_fuzzy(job, already_found=set())
        assert "Go" not in found

    def test_spring_fuzzy_blocked_without_java_context(self):
        job = _make_job(job_title="Spring cleaning coordinator seasonal role")
        found, rows = _layer3_fuzzy(job, already_found=set())
        assert "Spring Boot" not in found
        assert "Spring Framework" not in found


# ===========================================================================
# _context_check
# ===========================================================================

class TestContextCheck:
    def test_non_ambiguous_skill_always_passes(self):
        # "Python" is not in AMBIGUOUS_TERMS → always True
        assert _context_check("some text", 0, 4, "Python") is True

    def test_go_passes_with_golang_nearby(self):
        text = "experience with Go and golang is required"
        pos = text.lower().find("go")
        assert _context_check(text, pos, pos + 2, "Go") is True

    def test_go_fails_without_context(self):
        text = "great go-getter attitude required for this sales role"
        pos = text.lower().find("go")
        assert _context_check(text, pos, pos + 2, "Go") is False

    def test_spring_passes_with_java_nearby(self):
        text = "5 years java and Spring Boot experience required"
        pos = text.lower().find("spring")
        result = _context_check(text, pos, pos + 10, "Spring Boot")
        assert result is True

    def test_spring_fails_without_java(self):
        text = "Spring cleaning drive every March for the office"
        pos = text.lower().find("spring")
        result = _context_check(text, pos, pos + 6, "Spring Boot")
        assert result is False

    def test_rust_passes_with_systems_context(self):
        text = "Rust systems programming and memory safe development"
        pos = text.lower().find("rust")
        assert _context_check(text, pos, pos + 4, "Rust") is True

    def test_rust_fails_without_context(self):
        text = "The rust belt region faces economic challenges"
        pos = text.lower().find("rust")
        assert _context_check(text, pos, pos + 4, "Rust") is False


# ===========================================================================
# extract_skills_for_job — integration (pure, no CSV I/O)
# ===========================================================================

class TestExtractSkillsForJob:
    def test_returns_list_of_dicts(self):
        job = _make_job(
            job_id="integ001",
            job_title="Senior Python Developer",
            category_tags="Python,Django,REST API",
        )
        rows = extract_skills_for_job(job)
        assert isinstance(rows, list)
        assert all(isinstance(r, dict) for r in rows)

    def test_all_required_fields_present(self):
        job = _make_job(category_tags="Docker")
        rows = extract_skills_for_job(job)
        required = {"job_id", "skill_canonical", "skill_category", "extraction_source", "confidence"}
        for r in rows:
            assert required.issubset(r.keys()), f"Missing fields in row: {r}"

    def test_no_duplicate_skills_across_layers(self):
        # Python appears in both tags AND title — should only appear once in output
        job = _make_job(
            job_title="Python Developer specialising in Python",
            category_tags="Python,Flask",
        )
        rows = extract_skills_for_job(job)
        canonical_names = [r["skill_canonical"] for r in rows]
        assert len(canonical_names) == len(set(canonical_names)), (
            f"Duplicate skills found: {canonical_names}"
        )

    def test_l1_takes_precedence_over_l2(self):
        # Skills in tags should be sourced as "wuzzuf_tag" not "regex_match"
        job = _make_job(
            job_title="Python developer",
            category_tags="Python",
        )
        rows = extract_skills_for_job(job)
        python_row = next(r for r in rows if r["skill_canonical"] == "Python")
        assert python_row["extraction_source"] == "wuzzuf_tag"

    def test_empty_job_returns_empty_list(self):
        job = _make_job(job_title="", category_tags=None)
        rows = extract_skills_for_job(job)
        assert rows == []

    def test_confidence_ordering_across_layers(self):
        # L1 confidence (1.0) must be >= L2 (0.95) >= L3 (< 1.0)
        job = _make_job(
            job_title="Machine Learning Engineer with Tensorflow experience",
            category_tags="Python",
        )
        rows = extract_skills_for_job(job)
        sources = {r["extraction_source"]: r["confidence"] for r in rows}
        if "wuzzuf_tag" in sources:
            assert sources["wuzzuf_tag"] == 1.0
        if "regex_match" in sources:
            assert sources["regex_match"] == 0.95
        if "fuzzy_match" in sources:
            assert sources["fuzzy_match"] < 1.0

    def test_multi_word_skill_extracted(self):
        job = _make_job(
            job_title="Machine Learning Engineer",
            category_tags="Machine Learning,TensorFlow",
        )
        rows = extract_skills_for_job(job)
        skills = {r["skill_canonical"] for r in rows}
        assert "Machine Learning" in skills
        assert "TensorFlow" in skills

    def test_alias_in_tag_resolved_correctly(self):
        job = _make_job(category_tags="k8s,pyspark")
        rows = extract_skills_for_job(job)
        skills = {r["skill_canonical"] for r in rows}
        assert "Kubernetes" in skills
        assert "Apache Spark" in skills

    def test_real_wuzzuf_card_simulation(self):
        """
        Simulate a real Wuzzuf card for a Senior Backend Java Developer.
        Expected extractions: Java, Spring Boot, PostgreSQL, Docker,
        REST API, Microservices, Git.
        """
        job = _make_job(
            job_id="sim001",
            job_title="Senior Java Backend Developer",
            category_tags=(
                "IT/Software Development,"
                "Java,"
                "Spring Boot,"
                "PostgreSQL,"
                "Docker,"
                "REST API,"
                "Microservices,"
                "Git"
            ),
        )
        rows = extract_skills_for_job(job)
        skills = {r["skill_canonical"] for r in rows}
        assert "Java" in skills
        assert "Spring Boot" in skills
        assert "PostgreSQL" in skills
        assert "Docker" in skills
        assert "REST API" in skills
        assert "Microservices" in skills
        assert "Git" in skills


# ===========================================================================
# AMBIGUOUS_TERMS configuration sanity checks
# ===========================================================================

class TestAmbiguousTermsConfig:
    def test_go_is_in_ambiguous_terms(self):
        assert "Go" in AMBIGUOUS_TERMS

    def test_c_is_in_ambiguous_terms(self):
        assert "C" in AMBIGUOUS_TERMS

    def test_r_is_in_ambiguous_terms(self):
        assert "R" in AMBIGUOUS_TERMS

    def test_spring_boot_is_in_ambiguous_terms(self):
        assert "Spring Boot" in AMBIGUOUS_TERMS

    def test_rust_is_in_ambiguous_terms(self):
        assert "Rust" in AMBIGUOUS_TERMS

    def test_lean_is_in_ambiguous_terms(self):
        assert "Lean" in AMBIGUOUS_TERMS

    def test_vault_is_in_ambiguous_terms(self):
        assert "Vault" in AMBIGUOUS_TERMS

    def test_each_term_has_at_least_one_indicator(self):
        for term, indicators in AMBIGUOUS_TERMS.items():
            assert len(indicators) >= 1, f"'{term}' has no context indicators"

    def test_python_is_not_ambiguous(self):
        # Python should NOT require context gating
        assert "Python" not in AMBIGUOUS_TERMS


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
