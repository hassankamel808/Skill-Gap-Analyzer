"""
scraper/driver_manager.py
─────────────────────────
Manages the full lifecycle of an undetected-chromedriver / Selenium
WebDriver instance: creation, warm-up, cookie acceptance, and teardown.

Usage
─────
    with DriverManager() as driver:
        driver.get("https://wuzzuf.net/...")
"""

from __future__ import annotations

import logging
import random
import time
from contextlib import contextmanager
from typing import Generator

import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

from config.settings import settings
from config.user_agents import USER_AGENTS

logger = logging.getLogger(__name__)


class DriverManager:
    """Context-manager wrapper around an undetected Chrome instance."""

    def __init__(
        self,
        headless: bool | None = None,
        user_agent: str | None = None,
    ) -> None:
        self._headless = headless if headless is not None else settings.scrape_headless
        self._user_agent = user_agent or random.choice(USER_AGENTS)
        self._driver: uc.Chrome | None = None

    # ── Public interface ──────────────────────────────────────

    def start(self) -> uc.Chrome:
        """Initialise and return the WebDriver instance."""
        options = self._build_options()
        logger.info("Starting Chrome driver (headless=%s).", self._headless)
        self._driver = uc.Chrome(options=options)
        self._driver.implicitly_wait(10)
        logger.debug("Chrome driver started successfully.")
        return self._driver

    def quit(self) -> None:
        """Gracefully terminate the WebDriver session."""
        if self._driver:
            logger.info("Quitting Chrome driver.")
            try:
                self._driver.quit()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error while quitting driver: %s", exc)
            finally:
                self._driver = None

    # ── Context-manager support ───────────────────────────────

    def __enter__(self) -> uc.Chrome:
        return self.start()

    def __exit__(self, *_: object) -> None:
        self.quit()

    # ── Helpers ───────────────────────────────────────────────

    def _build_options(self) -> Options:
        options = uc.ChromeOptions()
        options.add_argument(f"--user-agent={self._user_agent}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        if self._headless:
            options.add_argument("--headless=new")
        return options

    @staticmethod
    def random_delay(
        min_seconds: float = 1.0,
        max_seconds: float | None = None,
    ) -> None:
        """Sleep for a random duration to mimic human browsing cadence."""
        if max_seconds is None:
            max_seconds = settings.scrape_request_delay_seconds * 1.5
        delay = random.uniform(min_seconds, max_seconds)
        logger.debug("Sleeping %.2f seconds.", delay)
        time.sleep(delay)
