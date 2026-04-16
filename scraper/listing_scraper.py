"""
scraper/listing_scraper.py
──────────────────────────
Paginates through Wuzzuf.net job search results and returns raw HTML
page sources, one element per listing page.

The scraper is intentionally stateless: it delegates checkpoint
persistence to the pipeline's StateManager.

Usage
─────
    with DriverManager() as driver:
        scraper = ListingScraper(driver)
        pages = scraper.scrape(query="data engineer", max_pages=10)
"""

from __future__ import annotations

import logging
import re
from typing import Iterator

from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config.settings import settings
from scraper.driver_manager import DriverManager

logger = logging.getLogger(__name__)

_JOB_CARD_SELECTOR = "article.css-prepvj"
_NEXT_PAGE_SELECTOR = 'a[data-component="PaginationNextPageButton"]'


class ListingScraper:
    """Paginated Wuzzuf job listing scraper."""

    def __init__(self, driver: object) -> None:
        self._driver = driver
        self._wait = WebDriverWait(driver, timeout=20)

    # ── Public API ────────────────────────────────────────────

    def scrape(
        self,
        query: str = "data engineer",
        max_pages: int | None = None,
        start_page: int = 0,
    ) -> Iterator[tuple[int, str]]:
        """
        Yield ``(page_index, html_source)`` tuples for each result page.

        Parameters
        ----------
        query:
            Search term forwarded to Wuzzuf's query string.
        max_pages:
            Upper bound on pages to retrieve; defaults to ``settings.scrape_max_pages``.
        start_page:
            Zero-based page to start from (for checkpoint resumption).
        """
        if max_pages is None:
            max_pages = settings.scrape_max_pages

        page = start_page
        while page < max_pages:
            url = self._build_url(query, page)
            logger.info("Scraping page %d → %s", page, url)
            try:
                self._driver.get(url)
                self._wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, _JOB_CARD_SELECTOR))
                )
            except TimeoutException:
                logger.warning("Page %d timed out – stopping pagination.", page)
                break

            html = self._driver.page_source
            yield page, html

            if not self._has_next_page():
                logger.info("No next-page button found – pagination complete.")
                break

            DriverManager.random_delay()
            page += 1

    # ── Private helpers ───────────────────────────────────────

    def _build_url(self, query: str, page: int) -> str:
        sanitised = re.sub(r"[^a-zA-Z0-9 ]", "", query).strip().replace(" ", "%20")
        return f"{settings.wuzzuf_base_url}?q={sanitised}&start={page}"

    def _has_next_page(self) -> bool:
        try:
            self._driver.find_element(By.CSS_SELECTOR, _NEXT_PAGE_SELECTOR)
            return True
        except NoSuchElementException:
            return False
