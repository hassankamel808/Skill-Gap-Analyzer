"""
main.py
───────
CLI entry point for the Wuzzuf Skill Gap Analyzer pipeline.

Modes
─────
--scrape            Run the full scrape + extract pipeline.
--analyze           Run analysis only on already-scraped data.
--extract-and-analyze  Scrape then immediately analyse (default if no flag given).
--test-mode         Cap the scraper at 1 page (for CI / smoke tests).

Examples
────────
    python main.py --scrape --query "data engineer" --max-pages 20
    python main.py --analyze
    python main.py --scrape --test-mode
    python main.py --extract-and-analyze
"""

from __future__ import annotations

import logging
import sys

import click
from rich.logging import RichHandler

from config.settings import settings


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)],
    )


@click.command()
@click.option(
    "--scrape",
    "mode",
    flag_value="scrape",
    help="Run the web scraper and skill extractor.",
)
@click.option(
    "--analyze",
    "mode",
    flag_value="analyze",
    help="Run demand / gap / co-occurrence analysis on existing data.",
)
@click.option(
    "--extract-and-analyze",
    "mode",
    flag_value="extract-and-analyze",
    default=True,
    help="Scrape then analyse in one shot (default).",
)
@click.option(
    "--query",
    default="data engineer",
    show_default=True,
    help="Search query forwarded to Wuzzuf.",
)
@click.option(
    "--max-pages",
    default=None,
    type=int,
    show_default=True,
    help="Override maximum pages to scrape (default from settings).",
)
@click.option(
    "--test-mode",
    is_flag=True,
    default=False,
    help="Limit scraper to 1 page for quick smoke tests.",
)
@click.option(
    "--log-level",
    default=settings.log_level,
    show_default=True,
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="Logging verbosity.",
)
def main(
    mode: str,
    query: str,
    max_pages: int | None,
    test_mode: bool,
    log_level: str,
) -> None:
    """Wuzzuf Skill Gap Analyzer – pipeline entry point."""
    _configure_logging(log_level)
    log = logging.getLogger(__name__)

    from pipeline.orchestrator import Orchestrator

    if mode in ("scrape", "extract-and-analyze"):
        log.info("Starting scrape phase (query=%r, test_mode=%s).", query, test_mode)
        orch = Orchestrator(
            mode="scrape",
            query=query,
            max_pages=max_pages,
            test_mode=test_mode,
        )
        orch.run()

    if mode in ("analyze", "extract-and-analyze"):
        log.info("Starting analysis phase.")
        orch = Orchestrator(mode="analyze")
        orch.run()

    log.info("Pipeline finished.")


if __name__ == "__main__":
    main()
