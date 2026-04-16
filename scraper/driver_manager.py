"""
scraper/driver_manager.py
=========================
Selenium WebDriver lifecycle management using undetected-chromedriver.

Responsibilities
----------------
- create_driver()  : Launch an undetected Chrome instance configured for
                     Cloudflare bypass, returning a ready WebDriver.
- is_cf_challenge(): Detect whether a Cloudflare interstitial is active.
- wait_for_cf()    : Block until the challenge resolves or timeout expires.
- wait_for_cards() : Block until job-card elements appear in the DOM.
- teardown()       : Quit the driver cleanly, swallowing any shutdown errors.

Design notes
------------
- HEADLESS_MODE = False (from settings) is required for Cloudflare bypass.
  undetected-chromedriver patches navigator.webdriver but a headless session
  still exposes extra fingerprint signals that CF's JS challenge detects.
- The driver is intentionally reused across all pages in a category run to
  maintain a consistent cookie/session state (switching IPs invalidates the
  CF clearance cookie).
- All blocking waits use explicit WebDriverWait — implicit waits are set once
  as a global fallback only.
"""

from __future__ import annotations

import logging
import time

import undetected_chromedriver as uc
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_chrome_options() -> uc.ChromeOptions:
    """
    Construct ChromeOptions for an undetected, human-like browser session.

    Rationale for each flag
    -----------------------
    --start-maximized        : Viewport matches BROWSER_WINDOW_WIDTH/HEIGHT;
                               avoids "non-standard window size" fingerprint.
    --disable-blink-features : Additional protection against
    =AutomationControlled     JS-level automation detection checks.
    --lang=en-US             : Set language header to a consistent locale;
                               avoids entropy from accept-language mismatches.
    --no-first-run           : Skip Chrome's first-run UI so the page loads
                               immediately without dialogs.
    --disable-notifications  : Suppress permission prompts that block page
                               interaction.
    --disable-popup-blocking : Prevent popups from interrupting the scrape.
    """
    options = uc.ChromeOptions()

    if settings.HEADLESS_MODE:
        # Only for CI / post-validation runs. Not recommended for CF bypass.
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        logger.warning(
            "HEADLESS_MODE is True — Cloudflare detection risk is higher."
        )

    options.add_argument(
        f"--window-size={settings.BROWSER_WINDOW_WIDTH},{settings.BROWSER_WINDOW_HEIGHT}"
    )
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=en-US")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-infobars")

    return options


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_driver() -> uc.Chrome:
    """
    Launch and configure an undetected Chrome WebDriver instance.

    Returns
    -------
    uc.Chrome
        A fully initialised, ready-to-use WebDriver.

    Raises
    ------
    WebDriverException
        If Chrome or chromedriver cannot be launched (e.g. Chrome not
        installed, port conflict).
    """
    logger.info("Launching undetected Chrome driver …")
    options = _build_chrome_options()

    # undetected_chromedriver auto-downloads the matching chromedriver binary
    # and patches it to remove automation fingerprints.
    driver = uc.Chrome(options=options, use_subprocess=True)

    # Explicit window sizing (belt-and-suspenders with the --window-size flag)
    driver.set_window_size(
        settings.BROWSER_WINDOW_WIDTH,
        settings.BROWSER_WINDOW_HEIGHT,
    )

    # Global implicit wait — used as a last-resort fallback only.
    # All critical waits use explicit WebDriverWait instead.
    driver.implicitly_wait(settings.IMPLICIT_WAIT_SECONDS)

    # Hard limit on page load time; raises TimeoutException if exceeded.
    driver.set_page_load_timeout(settings.PAGE_LOAD_TIMEOUT_SECONDS)

    logger.info(
        "Chrome driver ready  |  window=%dx%d  headless=%s",
        settings.BROWSER_WINDOW_WIDTH,
        settings.BROWSER_WINDOW_HEIGHT,
        settings.HEADLESS_MODE,
    )
    return driver


def is_cf_challenge(driver: uc.Chrome) -> bool:
    """
    Inspect the current page to determine whether a Cloudflare challenge
    interstitial is active.

    Strategy
    --------
    1. Check page title — CF interstitials have a generic title like
       "Just a moment…" or "Attention Required!".
    2. Check page body text for known CF challenge phrases.

    Parameters
    ----------
    driver : uc.Chrome

    Returns
    -------
    bool
        True if a CF challenge page is detected, False otherwise.
    """
    try:
        title = driver.title.lower()
        body_snippet = driver.find_element(By.TAG_NAME, "body").text[:500].lower()
    except WebDriverException:
        # If we can't read the page, assume CF challenge and be safe.
        return True

    combined = title + " " + body_snippet
    return any(phrase in combined for phrase in settings.CLOUDFLARE_CHALLENGE_PHRASES)


def wait_for_cf(driver: uc.Chrome, timeout: int | None = None) -> bool:
    """
    Block until the Cloudflare challenge resolves (page loads real content)
    or the timeout expires.

    undetected-chromedriver usually resolves CF challenges automatically
    within a few seconds. This function polls until the challenge page
    disappears or the deadline is reached.

    Parameters
    ----------
    driver  : uc.Chrome
    timeout : int | None
        Max seconds to wait. Defaults to settings.CLOUDFLARE_RESOLVE_WAIT_SECONDS.

    Returns
    -------
    bool
        True if CF resolved (real content visible), False if timed out.
    """
    if timeout is None:
        timeout = settings.CLOUDFLARE_RESOLVE_WAIT_SECONDS

    deadline = time.monotonic() + timeout
    poll_interval = 1.0  # check every second

    logger.debug("Waiting up to %ds for Cloudflare challenge to resolve …", timeout)

    while time.monotonic() < deadline:
        if not is_cf_challenge(driver):
            logger.debug("Cloudflare challenge resolved.")
            return True
        time.sleep(poll_interval)

    logger.warning(
        "Cloudflare challenge did NOT resolve within %ds.", timeout
    )
    return False


def wait_for_cards(driver: uc.Chrome, timeout: int | None = None) -> bool:
    """
    Wait until at least one job-card element is present in the DOM.

    Uses the primary CSS selector from settings, falling back to the stable
    ARIA/href-based selector if the primary fails within half the timeout.

    Parameters
    ----------
    driver  : uc.Chrome
    timeout : int | None
        Max seconds to wait. Defaults to settings.CARD_WAIT_TIMEOUT_SECONDS.

    Returns
    -------
    bool
        True if cards appeared, False if timed out.
    """
    if timeout is None:
        timeout = settings.CARD_WAIT_TIMEOUT_SECONDS

    half = max(timeout // 2, 3)

    # ── Try primary selector first ───────────────────────────────────────────
    primary = settings.SELECTOR_JOB_CARD
    try:
        WebDriverWait(driver, half).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, primary))
        )
        logger.debug("Job cards found via primary selector: %s", primary)
        return True
    except TimeoutException:
        logger.debug(
            "Primary card selector '%s' timed out after %ds — trying fallback.",
            primary, half,
        )

    # ── Try stable fallback selector (href-based) ────────────────────────────
    fallback = settings.FALLBACK_JOB_TITLE_ATTR
    remaining = timeout - half
    try:
        WebDriverWait(driver, remaining).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, fallback))
        )
        logger.debug("Job cards found via fallback selector: %s", fallback)
        return True
    except TimeoutException:
        logger.warning(
            "No job cards detected within %ds (primary: %s, fallback: %s).",
            timeout, primary, fallback,
        )
        return False


def teardown(driver: uc.Chrome | None) -> None:
    """
    Gracefully quit the Chrome WebDriver, suppressing any shutdown errors.

    It is safe to call this function with driver=None (no-op).

    Parameters
    ----------
    driver : uc.Chrome | None
    """
    if driver is None:
        return
    try:
        driver.quit()
        logger.info("Chrome driver shut down cleanly.")
    except Exception as exc:  # noqa: BLE001
        # Teardown errors (e.g. browser already crashed) must never propagate
        # and interrupt checkpoint saving or CSV flushing.
        logger.debug("Driver teardown raised (suppressed): %s", exc)
