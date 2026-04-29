"""
tests/conftest.py
=================
Session-level pytest configuration for the Wuzzuf Skill-Gap Analyzer.

Environment isolation guarantee
---------------------------------
Tests must NEVER write to the production output paths:
  - output/raw_jobs.csv
  - output/extracted_skills.csv
  - output/analytics_summary.csv
  - output/state.json

This module provides:
  1. A session-scoped autouse fixture (``_enforce_test_isolation``) that
     patches all production output paths to point at the system temporary
     directory before the test session begins.  Any test that fails to apply
     its own monkeypatch will therefore still write to /tmp (or equivalent)
     rather than the real output/ directory.

  2. A convenience fixture (``tmp_output``) that gives individual tests a
     fresh per-test output directory and pre-patches all settings paths to
     point there.  Use this in integration tests that need real file I/O.

These safeguards are additive — the existing ``monkeypatch`` calls in each
test class remain valid and continue to provide per-test isolation.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is importable when pytest is run from any CWD.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pytest
from config import settings


# ---------------------------------------------------------------------------
# Session-level isolation: redirect ALL production output paths to tmp
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="session")
def _enforce_test_isolation(tmp_path_factory):
    """
    Session-scoped autouse fixture.

    Patches every production output path constant in ``config.settings`` to
    a temporary directory for the entire test session.  This prevents any
    test that forgets its own monkeypatch from accidentally writing into
    ``output/raw_jobs.csv`` or any other production file.

    Individual tests that need a specific path (e.g. to pre-populate a CSV)
    should continue to use ``monkeypatch.setattr(settings, ...)`` as they
    already do — those per-test patches override this session-level default.
    """
    session_tmp = tmp_path_factory.mktemp("session_output")
    charts_tmp  = session_tmp / "charts"
    charts_tmp.mkdir(parents=True, exist_ok=True)

    # Patch module-level constants
    settings.OUTPUT_DIR           = session_tmp
    settings.CHARTS_DIR           = charts_tmp
    settings.STATE_FILE           = session_tmp / "state.json"
    settings.RAW_JOBS_CSV         = session_tmp / "raw_jobs.csv"
    settings.EXTRACTED_SKILLS_CSV = session_tmp / "extracted_skills.csv"
    settings.ANALYTICS_CSV        = session_tmp / "analytics_summary.csv"

    yield  # run all tests

    # No teardown needed — tmp_path_factory cleans up automatically


# ---------------------------------------------------------------------------
# Convenience fixture: fresh per-test output directory
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_output(tmp_path, monkeypatch):
    """
    Per-test fixture that provides a clean temporary output directory and
    monkeypatches all ``settings`` output paths to point there.

    Usage in a test::

        def test_something(tmp_output):
            from config import settings
            # settings.RAW_JOBS_CSV now points to tmp_output / "raw_jobs.csv"
            # settings.STATE_FILE   now points to tmp_output / "state.json"
            ...

    Returns the ``Path`` to the temporary output directory.
    """
    charts = tmp_path / "charts"
    charts.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "OUTPUT_DIR",           tmp_path)
    monkeypatch.setattr(settings, "CHARTS_DIR",           charts)
    monkeypatch.setattr(settings, "STATE_FILE",           tmp_path / "state.json")
    monkeypatch.setattr(settings, "RAW_JOBS_CSV",         tmp_path / "raw_jobs.csv")
    monkeypatch.setattr(settings, "EXTRACTED_SKILLS_CSV", tmp_path / "extracted_skills.csv")
    monkeypatch.setattr(settings, "ANALYTICS_CSV",        tmp_path / "analytics_summary.csv")

    return tmp_path
