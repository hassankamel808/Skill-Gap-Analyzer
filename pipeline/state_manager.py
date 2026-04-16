"""
pipeline/state_manager.py
=========================
JSON checkpoint persistence for the scraper pipeline.

All state is stored in a single human-readable JSON file at
settings.STATE_FILE (output/state.json).

Public API
----------
load_state()       -> dict    Load state from disk, or return a fresh state.
save_state(state)  -> None    Atomically write state to disk.
reset_state()      -> None    Delete the state file so next run starts fresh.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema for a fresh / empty state object
# ---------------------------------------------------------------------------

def _fresh_state() -> dict:
    """Return a newly initialised state dict for a brand-new run."""
    return {
        "run_id":               datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "status":               "in_progress",
        "phase":                "listing_scrape",
        "total_jobs_collected": 0,
        "categories":           {},
        "last_updated":         datetime.now(tz=timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """
    Load the checkpoint state from disk.

    If the state file does not exist, is empty, or contains invalid JSON,
    returns a fresh initialised state dict (i.e. a new run starts cleanly).

    Returns
    -------
    dict
        The checkpoint state, either loaded from disk or freshly initialised.
    """
    path: Path = settings.STATE_FILE

    if not path.exists() or path.stat().st_size == 0:
        logger.info("No state file found — starting fresh run.")
        return _fresh_state()

    try:
        with path.open("r", encoding="utf-8") as fh:
            state = json.load(fh)
        logger.info(
            "State loaded: run_id=%s  status=%s  total_jobs=%d",
            state.get("run_id", "?"),
            state.get("status", "?"),
            state.get("total_jobs_collected", 0),
        )
        return state
    except (json.JSONDecodeError, OSError) as exc:
        logger.error(
            "Failed to load state file (%s): %s — starting fresh.", path, exc
        )
        return _fresh_state()


def save_state(state: dict) -> None:
    """
    Atomically write ``state`` to settings.STATE_FILE as JSON.

    Uses a write-to-temp-then-replace strategy so the state file is never
    left in a partially-written, corrupt state if the process is killed
    mid-write.

    Parameters
    ----------
    state : dict
        The current pipeline checkpoint state to persist.
    """
    path: Path = settings.STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temp file in the same directory, then atomically replace.
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=path.parent, prefix=".state_tmp_", suffix=".json"
        )
        try:
            with open(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2, ensure_ascii=False, default=str)
            shutil.move(tmp_path, path)
        except Exception:
            # Clean up the temp file if something went wrong
            Path(tmp_path).unlink(missing_ok=True)
            raise
    except OSError as exc:
        # State save failures must NEVER crash the scraper.
        # Log the error and continue — data already written to CSV is safe.
        logger.error("Failed to save state file (%s): %s", path, exc)


def reset_state() -> None:
    """
    Delete the state file so the next run starts completely fresh.
    Safe to call even if the file does not exist.
    """
    path: Path = settings.STATE_FILE
    if path.exists():
        path.unlink()
        logger.info("State file deleted — next run will start fresh.")
    else:
        logger.debug("reset_state(): no state file to delete.")
