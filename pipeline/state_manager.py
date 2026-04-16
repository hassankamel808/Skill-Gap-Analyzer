"""
pipeline/state_manager.py
──────────────────────────
Provides atomic JSON checkpoint read/write for pipeline resumption.

The checkpoint file stores the last successfully processed state so that
a crashed or interrupted run can resume from where it left off, rather
than restarting from scratch.

Atomicity is achieved by writing to a ``<file>.tmp`` sibling, fsyncing,
then atomically renaming into place (POSIX ``os.replace``).

Usage
─────
    sm = StateManager()
    state = sm.load()           # → {} if no checkpoint exists yet
    state["last_page"] = 7
    sm.save(state)
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)


class StateManager:
    """
    Atomic JSON checkpoint manager.

    Parameters
    ----------
    path:
        Path to the checkpoint file.  Defaults to
        ``settings.state_file``.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = Path(path) if path else settings.state_file
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ── Public API ────────────────────────────────────────────

    def load(self) -> dict[str, Any]:
        """
        Load and return the checkpoint dict.

        Returns an empty dict if the checkpoint does not yet exist or is
        corrupted.
        """
        if not self._path.exists():
            logger.debug("No checkpoint found at %s – starting fresh.", self._path)
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                state = json.load(fh)
            logger.info("Loaded checkpoint from %s.", self._path)
            return state
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load checkpoint (%s) – starting fresh.", exc)
            return {}

    def save(self, state: dict[str, Any]) -> None:
        """
        Atomically persist *state* to the checkpoint file.

        Uses a temporary file + ``os.replace`` for crash safety.
        """
        tmp_path = self._path.with_suffix(".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2, default=str)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, self._path)
            logger.debug("Checkpoint saved to %s.", self._path)
        except OSError as exc:
            logger.error("Failed to save checkpoint: %s", exc)
            raise

    def clear(self) -> None:
        """Delete the checkpoint file if it exists."""
        if self._path.exists():
            self._path.unlink()
            logger.info("Checkpoint cleared: %s", self._path)
