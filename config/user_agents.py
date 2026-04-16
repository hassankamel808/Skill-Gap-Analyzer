"""
config/user_agents.py
─────────────────────
Pool of desktop User-Agent strings rotated by the driver manager to
reduce the chance of bot-detection fingerprinting.
"""

from __future__ import annotations

USER_AGENTS: list[str] = [
    # Chrome 123 – Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    # Chrome 122 – macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    # Firefox 124 – Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
        "Gecko/20100101 Firefox/124.0"
    ),
    # Firefox 123 – Linux
    (
        "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) "
        "Gecko/20100101 Firefox/123.0"
    ),
    # Edge 123 – Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0"
    ),
    # Safari 17 – macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.3 Safari/605.1.15"
    ),
    # Chrome 121 – Android
    (
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.6167.101 Mobile Safari/537.36"
    ),
    # Chrome 120 – Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
]
