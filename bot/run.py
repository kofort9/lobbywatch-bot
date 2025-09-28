"""Main entry point for LobbyLens bot."""

import logging
import sys
import traceback
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler

from .config import settings
from .digest import DigestError, compute_digest
from .notifiers.base import NotificationError
from .notifiers.slack import SlackNotifier

console = Console()


# V2 System Functions
def run_daily_digest(
        hours_back: int = 24,
        channel_id: str = "test_channel") -> str:
    """Run daily digest collection and formatting using v2 system"""
    import logging
    from datetime import datetime, timezone
    from typing import List, Optional

    from bot.daily_signals_v2 import DailySignalsCollectorV2
    from bot.digest_v2 import DigestV2Formatter
    from bot.signals_database_v2 import SignalsDatabaseV2

    logger = logging.getLogger(__name__)
    logger.info(f"Running daily digest for last {hours_back} hours")

    # Initialize components
    collector = DailySignalsCollectorV2(settings.model_dump())
    formatter = DigestV2Formatter()
    database = SignalsDatabaseV2()

    # Get watchlist for channel
    # watchlist = [item["name"] for item in database.get_watchlist(channel_id)]  # Unused variable

    # Collect signals
    signals = collector.collect_all_signals(hours_back)
    logger.info(f"Collected {len(signals)} signals")

    # Format digest
    digest = formatter.format_daily_digest(signals, hours_back)

    return digest


def run_mini_digest(
    hours_back: int = 4, channel_id: str = "test_channel"
) -> Optional[str]:
    """Run mini digest collection and formatting using v2 system"""
    import logging
    from datetime import datetime, timezone
    from typing import List, Optional

    from bot.daily_signals_v2 import DailySignalsCollectorV2
    from bot.digest_v2 import DigestV2Formatter
    from bot.signals_database_v2 import SignalsDatabaseV2

    logger = logging.getLogger(__name__)
    logger.info(f"Running mini digest for last {hours_back} hours")

    # Initialize components
    collector = DailySignalsCollectorV2(settings.model_dump())
    formatter = DigestV2Formatter()
    database = SignalsDatabaseV2()

    # Get watchlist for channel
    # watchlist = [item["name"] for item in database.get_watchlist(channel_id)]  # Unused variable

    # Collect signals
    signals = collector.collect_all_signals(hours_back)
    logger.info(f"Collected {len(signals)} signals")

    # Check mini-digest thresholds
    high_priority_signals = [s for s in signals if s.priority_score >= 5.0]
    watchlist_hits = [s for s in signals if s.watchlist_hit]

    # Mini-digest criteria
    if (
        len(signals) >= 10
        or len(high_priority_signals) >= 1
        or len(watchlist_hits) >= 1
    ):
        # Format mini digest
        digest = formatter.format_mini_digest(signals)
        return digest
    else:
        logger.info("Mini-digest thresholds not met")
        return None


# Configure logging
def setup_logging(level: str) -> None:
    """Set up logging with Rich handler."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


logger = logging.getLogger(__name__)


def fetch_data() -> tuple[int, int]:
    """Fetch fresh data from configured sources.

    Returns:
        Tuple of (successful_fetches, failed_fetches)
    """
    # Note: Legacy data fetching removed due to API changes.
    # The v2 system now uses direct government API calls instead of
    # the lobbywatch package which relied on deprecated OpenSecrets/ProPublica
    # APIs.
    logger.info("Legacy data fetching disabled - using v2 system for fresh data")
    return 0, 0


def create_notifier() -> SlackNotifier:
    """Create and return configured notifier.

    Returns:
        Configured SlackNotifier instance

    Raises:
        ValueError: If no notifier is properly configured
    """
    settings.validate_notifier_config()

    if settings.notifier_type == "slack":
        return SlackNotifier(settings.slack_webhook_url or "")

    raise ValueError("No supported notifier configured")


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Generate digest but don't send notification",
)
@click.option(
    "--skip-fetch",
    is_flag=True,
    default=False,
    help="Skip data fetching, only generate digest from existing data",
)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    help="Set logging level",
)
def main(dry_run: bool, skip_fetch: bool, log_level: str) -> None:
    """Run LobbyLens daily digest bot.

    Fetches fresh lobbying data and sends daily digest via Slack.
    """
    # Override config with CLI options
    if dry_run:
        settings.dry_run = True
    if log_level:
        settings.log_level = log_level

    setup_logging(settings.log_level)

    logger.info("🔍 Starting LobbyLens daily digest bot...")

    # Track errors for summary
    errors = []

    # 1. Fetch fresh data (unless skipped)
    if not skip_fetch:
        try:
            successful_fetches, failed_fetches = fetch_data()
            if failed_fetches > 0:
                errors.append(
                    f"Data fetch errors: {failed_fetches} source(s) failed")
            logger.info(
                f"Data fetch complete: {successful_fetches} successful, {failed_fetches} failed"
            )
        except Exception as e:
            error_msg = f"Critical error during data fetch: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
    else:
        logger.info("Skipping data fetch (--skip-fetch specified)")

    # 2. Compute digest
    try:
        logger.info("Computing daily digest...")
        digest_text = compute_digest(settings.database_file)

        if errors:
            # Append error summary to digest
            error_summary = "\\n⚠️ *Errors during processing:*\\n" + \
                "\\n".join(f"• {err}" for err in errors)
            digest_text += error_summary

    except DigestError as e:
        logger.error(f"Failed to compute digest: {e}")
        # Send error notification instead
        digest_text = (
            f"🚨 *LobbyLens Digest Error*\\n\\nFailed to generate daily digest: {e}"
        )
        if errors:
            digest_text += "\\n\\nAdditional errors:\\n" + "\\n".join(
                f"• {err}" for err in errors
            )
    except Exception as e:
        logger.error(f"Unexpected error computing digest: {e}")
        traceback.print_exc()
        digest_text = f"🚨 *LobbyLens Critical Error*\\n\\nUnexpected error: {e}"

    # 3. Send notification
    if settings.dry_run:
        console.print("\\n[yellow]DRY RUN - Would send this digest:[/yellow]")
        console.print("\\n" + "=" * 50)
        console.print(digest_text)
        console.print("=" * 50 + "\\n")
        logger.info("✅ Dry run completed successfully")
        return

    try:
        logger.info("Sending digest notification...")
        notifier = create_notifier()
        notifier.send(digest_text)
        logger.info("✅ Daily digest sent successfully")

    except NotificationError as e:
        logger.error(f"Failed to send notification: {e}")
        console.print(f"[red]❌ Notification failed:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error sending notification: {e}")
        traceback.print_exc()
        console.print(f"[red]❌ Critical error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
