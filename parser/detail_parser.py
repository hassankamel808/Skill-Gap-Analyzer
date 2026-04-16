"""
parser/detail_parser.py
=======================
BeautifulSoup HTML parser for job detail pages.
Input: raw page_source HTML string from Selenium.
Output: dict of detail-level fields (description, salary, education, etc.).
NOTE: Detail scraping is DISABLED in listing-only mode. Stub only.
"""
# Detail scraping is NOT used in listing-only production mode.
# Retained as a stub for future use.


def parse(html: str) -> dict:
    raise NotImplementedError("Detail scraping disabled in listing-only mode.")
