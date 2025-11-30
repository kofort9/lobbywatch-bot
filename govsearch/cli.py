"""Command-line entrypoints for GovSearch."""

from __future__ import annotations

import logging
from typing import Optional

import click

from govsearch.config import get_settings
from govsearch.db import ensure_schema
from govsearch.indexer.backfill import backfill_recent_documents
from govsearch.indexer.incremental import run_incremental_update

logger = logging.getLogger(__name__)


@click.group()
def main() -> None:
    """GovSearch management commands."""


@main.command()
@click.option("--database-url", envvar="GOVSEARCH_DATABASE_URL", default=None)
def migrate(database_url: Optional[str]) -> None:
    """Create GovSearch tables and indexes if needed."""

    settings = get_settings()
    ensure_schema(database_url or settings.database_url)
    logger.info("GovSearch schema ensured")


@main.command(name="backfill")
@click.option("--days", default=365, show_default=True)
@click.option("--quarters", default=8, show_default=True)
@click.option("--database-url", envvar="GOVSEARCH_DATABASE_URL", default=None)
def backfill_cmd(days: int, quarters: int, database_url: Optional[str]) -> None:
    """Run a historical backfill."""

    settings = get_settings()
    backfill_recent_documents(
        database_url or settings.database_url,
        days_back=days,
        quarters_back=quarters,
    )


@main.command(name="incremental")
@click.option("--hours", default=24, show_default=True)
@click.option("--database-url", envvar="GOVSEARCH_DATABASE_URL", default=None)
def incremental_cmd(hours: int, database_url: Optional[str]) -> None:
    """Run incremental update for the last N hours."""

    settings = get_settings()
    run_incremental_update(
        database_url or settings.database_url,
        hours_back=hours,
    )


if __name__ == "__main__":
    main()
