"""CLI for testing daily signals collection."""

import logging
import sys
from datetime import datetime, timedelta

import click
from rich.console import Console
from rich.logging import RichHandler

from .config import settings
from .daily_signals import DailySignalsCollector
from .database_postgres import create_database_manager
from .signals_database import SignalsDatabase
from .signals_digest import SignalsDigestFormatter

console = Console()


def setup_logging(level: str) -> None:
    """Set up logging with Rich handler."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@click.command()
@click.option(
    "--hours-back", default=24, type=int, help="Hours back to collect signals from"
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Collect signals but don't store in database",
)
@click.option(
    "--format-digest",
    is_flag=True,
    default=False,
    help="Format and display digest instead of raw signals",
)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    help="Set logging level",
)
def main(hours_back: int, dry_run: bool, format_digest: bool, log_level: str) -> None:
    """Collect and process daily government signals."""

    setup_logging(log_level)
    logger = logging.getLogger(__name__)

    logger.info(f"🔍 Starting daily signals collection (last {hours_back}h)...")

    # Initialize database
    try:
        db_manager = create_database_manager(settings.database_url)
        db_manager.ensure_enhanced_schema()
        signals_db = SignalsDatabase(db_manager)
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)

    # Prepare configuration
    config = {
        "congress_api_key": settings.congress_api_key,
        "federal_register_api_key": settings.federal_register_api_key,
        "regulations_gov_api_key": settings.regulations_gov_api_key,
    }

    # Collect signals
    # Filter out None values for the collector
    clean_config = {k: v for k, v in config.items() if v is not None}
    collector = DailySignalsCollector(clean_config)

    try:
        signals = collector.collect_all_signals(hours_back)
        logger.info(f"Collected {len(signals)} signals")

        if not dry_run:
            stored_count = signals_db.store_signals(signals)
            logger.info(f"Stored {stored_count} signals in database")

        if format_digest:
            # Format and display digest
            formatter = SignalsDigestFormatter(signals_db)
            digest = formatter.format_daily_digest("test_channel", hours_back)

            console.print("\n" + "=" * 60)
            console.print("[yellow]Daily Signals Digest:[/yellow]")
            console.print("=" * 60)
            console.print(digest)
            console.print("=" * 60 + "\n")
        else:
            # Display raw signals
            console.print(f"\n[yellow]Collected {len(signals)} signals:[/yellow]")
            for i, signal in enumerate(signals[:10], 1):  # Show top 10
                console.print(f"{i}. [{signal.priority_score:.1f}] {signal.title}")
                console.print(
                    f"   Source: {signal.source} | Issues: {signal.issue_codes}"
                )
                if signal.link:
                    console.print(f"   Link: {signal.link}")
                console.print()

            if len(signals) > 10:
                console.print(f"... and {len(signals) - 10} more signals")

        logger.info("✅ Daily signals collection completed successfully")

    except Exception as e:
        logger.error(f"Failed to collect signals: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
