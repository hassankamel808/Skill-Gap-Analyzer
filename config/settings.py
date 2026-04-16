"""
config/settings.py
==================
Central configuration for the Wuzzuf Tech Job Market Skill-Gap Analyzer.
All constants live here — no magic numbers elsewhere in the codebase.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Project Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"
CHARTS_DIR = OUTPUT_DIR / "charts"
STATE_FILE = OUTPUT_DIR / "state.json"
RAW_JOBS_CSV = OUTPUT_DIR / "raw_jobs.csv"
EXTRACTED_SKILLS_CSV = OUTPUT_DIR / "extracted_skills.csv"
ANALYTICS_CSV = OUTPUT_DIR / "analytics_summary.csv"

# Ensure output dirs exist at import time
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Dev / Test Mode
# ---------------------------------------------------------------------------
# Set DEV_MODE_LIMIT = True to cap scraping at DEV_MODE_LIMIT_COUNT total
# jobs across all categories. Useful for testing the full pipeline cheaply.
DEV_MODE_LIMIT: bool = False
DEV_MODE_LIMIT_COUNT: int = 50  # Max jobs to scrape in dev mode

# ---------------------------------------------------------------------------
# Target URLs — /a/ category pages (allowed by robots.txt)
# ---------------------------------------------------------------------------
BASE_URL = "https://wuzzuf.net"

# Each entry: (category_slug, category_url, internal_label)
# Pagination appended as: url?start=0, url?start=1, ...
TARGET_CATEGORIES: list[dict] = [
    {
        "label": "IT-Software-Development",
        "url": f"{BASE_URL}/a/IT-Software-Development-Jobs-in-Egypt",
        "estimated_listings": 3400,
    },
    {
        "label": "Engineering-Telecom-Technology",
        "url": f"{BASE_URL}/a/Engineering-Telecom-Technology-Jobs-in-Egypt",
        "estimated_listings": 800,
    },
    {
        "label": "Analyst-Research",
        "url": f"{BASE_URL}/a/Analyst-Research-Jobs-in-Egypt",
        "estimated_listings": 400,
    },
    {
        "label": "Creative-Design-Art",
        "url": f"{BASE_URL}/a/Creative-Design-Art-Jobs-in-Egypt",
        "estimated_listings": 300,
    },
]

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
JOBS_PER_PAGE: int = 20           # Wuzzuf shows 20 results per listing page
# URL parameter: ?start=0 (page 1), ?start=1 (page 2), etc. (0-indexed)

# ---------------------------------------------------------------------------
# BeautifulSoup / HTML Selectors
# (Verified against live DOM — update here if Wuzzuf changes their markup)
# ---------------------------------------------------------------------------

# ---- Listing / Search Result Page ----
# The "Showing X - Y of Z" counter text, used to determine total_pages
SELECTOR_RESULTS_COUNT: str = "div.css-1d2q07k"   # fallback: parse any text matching r"Showing \d+ - \d+ of \d+"

# Each job card on the listing page (container wrapping one posting)
# Cards are <div> siblings; the parent's children each represent one job
SELECTOR_JOB_CARD: str = "div.css-1gatmva"        # primary — outer card wrapper

# Job title link inside a card
SELECTOR_JOB_TITLE: str = "h2.css-m604qf a"       # <h2><a href="/jobs/p/...">Title</a></h2>

# Company name inside a card
SELECTOR_COMPANY: str = "a.css-17s97q8"           # Company name anchor

# Location text (city) inside a card — appears after company separator " - "
SELECTOR_LOCATION: str = "span.css-5wys0k"        # Location span

# Posted date inside a card (relative: "2 hours ago")
SELECTOR_POSTED_DATE: str = "div.css-do6t5g"      # Time/date element

# Job type badge chips (Full Time, Part Time, Internship, Contract)
SELECTOR_JOB_TYPE_BADGES: str = "a.css-n2jc43"    # Clickable type badges

# Work mode badge (On-site, Remote, Hybrid)
SELECTOR_WORK_MODE_BADGES: str = "a.css-bcbr8g"   # Clickable mode badges

# Experience level text (Entry Level, Experienced, Manager, Senior Management)
SELECTOR_EXPERIENCE_LEVEL: str = "a.css-y4udm8"   # Experience level anchor

# Skill / category tag chips on a card (the "· Python · React" items)
SELECTOR_SKILL_TAGS: str = "div.css-y3uu2g a"     # Chip container → anchor

# ---- Fallback Attribute Selectors ----
# Wuzzuf uses emotion CSS-in-JS — class names can change on redeploy.
# These ARIA / data-attribute selectors are more stable backups.
FALLBACK_JOB_CARD_ATTR: str = "[data-wuzzuf-component='job-card']"
FALLBACK_JOB_TITLE_ATTR: str = "h2 a[href*='/jobs/p/'], h2 a[href*='/internship/']"
FALLBACK_SKILL_TAGS_ATTR: str = "a[href*='/a/'][href*='-Jobs-in-Egypt']"

# ---------------------------------------------------------------------------
# Selenium / WebDriver Settings
# ---------------------------------------------------------------------------
BROWSER_WINDOW_WIDTH: int = 1920
BROWSER_WINDOW_HEIGHT: int = 1080
HEADLESS_MODE: bool = False          # Keep False for Cloudflare bypass; set True only after validation
IMPLICIT_WAIT_SECONDS: int = 10
PAGE_LOAD_TIMEOUT_SECONDS: int = 30

# Maximum time to wait for job cards to appear on a listing page
CARD_WAIT_TIMEOUT_SECONDS: int = 15

# Maximum retries per page before skipping
MAX_PAGE_RETRIES: int = 3

# Maximum consecutive failures before triggering a long pause
MAX_CONSECUTIVE_FAILURES: int = 5
LONG_PAUSE_SECONDS: int = 600        # 10 min cooldown after 5 consecutive failures

# ---------------------------------------------------------------------------
# Rate Limiting & Politeness Delays (seconds)
# ---------------------------------------------------------------------------
# Random delay between listing page navigations
LISTING_DELAY_MIN: float = 2.0
LISTING_DELAY_MAX: float = 5.0

# Cooldown batch: pause every N listing pages to avoid sustained traffic
LISTING_COOLDOWN_EVERY_N_PAGES: int = 50
LISTING_COOLDOWN_SECONDS: float = 30.0

# Exponential backoff base delays for retries
RETRY_BACKOFF_DELAYS: list[float] = [5.0, 15.0, 45.0]

# ---------------------------------------------------------------------------
# Cloudflare / Bot Detection Bypass
# ---------------------------------------------------------------------------
# Time to wait after initial page load for Cloudflare challenge to auto-resolve
CLOUDFLARE_RESOLVE_WAIT_SECONDS: int = 15

# Phrases that indicate a Cloudflare challenge or block page
CLOUDFLARE_CHALLENGE_PHRASES: list[str] = [
    "checking your browser",
    "please wait",
    "just a moment",
    "enable javascript",
    "access denied",
    "ray id",
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = "INFO"             # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s — %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"

# ---------------------------------------------------------------------------
# Data Quality
# ---------------------------------------------------------------------------
# Maximum raw text length to store for skill tags (chars) — guards against
# storing entire CSS class strings as "skills" if selectors drift.
MAX_SKILL_TAG_LENGTH: int = 80

# Minimum character length for a valid job title
MIN_JOB_TITLE_LENGTH: int = 3

# Checkpoint: save state every N jobs collected on a listing page run
CHECKPOINT_EVERY_N_JOBS: int = 20
