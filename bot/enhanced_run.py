"""Enhanced main entry point for LobbyLens with interactive features."""

import logging
import os
import sys
from datetime import datetime
from datetime import time as dt_time
from datetime import timezone
from typing import Dict, List, Optional

import click
from rich.console import Console
from rich.logging import RichHandler

from .config import settings
from .database import DatabaseManager
from .database_postgres import create_database_manager
from .enhanced_digest import EnhancedDigestComputer
from .slack_app import SlackApp

console = Console()


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
    """Fetch fresh data from configured sources."""
    # Note: Legacy data fetching removed due to API changes.
    # The v2 system now uses direct government API calls instead of
    # the lobbywatch package which relied on deprecated OpenSecrets/ProPublica
    # APIs.
    logger.info("Legacy data fetching disabled - using v2 system for fresh data")
    return 0, 0


def get_configured_channels() -> List[str]:
    """Get list of channels to send digests to."""
    # For now, use environment variable. In production, this could come from
    # database
    channels = os.getenv("LOBBYLENS_CHANNELS", "").split(",")
    return [ch.strip() for ch in channels if ch.strip()]


def is_time_for_digest(digest_type: str) -> bool:
    """Check if it's time for a specific digest type."""
    now = datetime.now(timezone.utc)
    current_time = now.time()

    if digest_type == "daily":
        # 8:00 AM PT (15:00 UTC in winter, 16:00 UTC in summer)
        # For simplicity, using 8:00 AM local time
        target_time = dt_time(8, 0)
        return current_time.hour == target_time.hour and current_time.minute < 15

    elif digest_type == "mini":
        # 4:00 PM PT
        target_time = dt_time(16, 0)
        return current_time.hour == target_time.hour and current_time.minute < 15

    return False


def run_scheduled_digests(
    db_manager: DatabaseManager, slack_app: SlackApp, digest_type: str = "daily"
) -> Dict[str, bool]:
    """Run scheduled digests for configured channels."""
    channels = get_configured_channels()
    if not channels:
        logger.warning("No channels configured for digests")
        return {}

    results = {}

    for channel_id in channels:
        try:
            logger.info(f"Generating {digest_type} digest for channel {channel_id}")

            # Check if mini-digest should be sent
            if digest_type == "mini":
                digest_computer = EnhancedDigestComputer(db_manager)
                if not digest_computer.should_send_mini_digest(channel_id):
                    logger.info(
                        f"Skipping mini digest for {channel_id} - threshold not met"
                    )
                    results[channel_id] = True  # Success (but skipped)
                    continue

            # Send digest
            success = slack_app.send_digest(channel_id, digest_type)
            results[channel_id] = success

            if success:
                logger.info(f"✅ {digest_type.title()} digest sent to {channel_id}")
            else:
                logger.error(f"❌ Failed to send {digest_type} digest to {channel_id}")

        except Exception as e:
            logger.error(f"Error generating {digest_type} digest for {channel_id}: {e}")
            results[channel_id] = False

    return results


@click.command()
@click.option(
    "--mode",
    type=click.Choice(["daily", "mini", "server"]),
    default="daily",
    help="Run mode: daily digest, mini digest, or web server",
)
@click.option("--channel", help="Specific channel to send digest to (overrides config)")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Generate digest but don't send notifications",
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
@click.option(
    "--port",
    default=None,
    type=int,
    help="Port for web server mode (defaults to Railway PORT or 8000)",
)
def main(
    mode: str, channel: str, dry_run: bool, skip_fetch: bool, log_level: str, port: int
) -> None:
    """Enhanced LobbyLens with interactive features and dual cadence."""

    # Override config with CLI options
    if dry_run:
        settings.dry_run = True
    if log_level:
        settings.log_level = log_level

    setup_logging(settings.log_level)

    logger.info(f"🔍 Starting LobbyLens in {mode} mode...")

    # Initialize database and ensure enhanced schema
    try:
        db_manager = create_database_manager(settings.database_url)
        db_manager.ensure_enhanced_schema()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)

    # Initialize Slack app
    slack_app = SlackApp(db_manager)

    if mode == "server":
        # Run web server for handling Slack events
        from .web_server import create_web_server

        if not settings.slack_bot_token or not settings.slack_signing_secret:
            if settings.is_production():
                logger.error(
                    "Web server mode requires SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET in production"
                )
                sys.exit(1)
            else:
                logger.warning(
                    "SLACK_BOT_TOKEN or SLACK_SIGNING_SECRET not set - Slack features will be disabled"
                )

        app = create_web_server(slack_app)

        # Use Railway's PORT environment variable or default
        if port is None:
            port = int(os.environ.get("PORT", 8000))

        logger.info(f"🚀 Starting web server on port {port}")
        try:
            app.run(host="0.0.0.0", port=port, debug=False)
        except KeyboardInterrupt:
            logger.info("Web server stopped")
        return

    # Track errors for summary
    errors = []

    # 1. Fetch fresh data (unless skipped)
    if not skip_fetch:
        try:
            successful_fetches, failed_fetches = fetch_data()
            if failed_fetches > 0:
                errors.append(f"Data fetch errors: {failed_fetches} source(s) failed")
            logger.info(
                f"Data fetch complete: {successful_fetches} successful, {failed_fetches} failed"
            )
        except Exception as e:
            error_msg = f"Critical error during data fetch: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
    else:
        logger.info("Skipping data fetch (--skip-fetch specified)")

    # 2. Run digests
    if settings.dry_run:
        logger.info("DRY RUN MODE - Would send digests but not actually posting")

        # Generate sample digest for first configured channel or specified
        # channel
        test_channels = [channel] if channel else get_configured_channels()[:1]

        if test_channels:
            try:
                digest_computer = EnhancedDigestComputer(db_manager)
                digest_text = digest_computer.compute_enhanced_digest(
                    test_channels[0], mode
                )

                console.print(
                    f"\n[yellow]DRY RUN - Would send this {mode} digest:[/yellow]"
                )
                console.print("\n" + "=" * 60)
                console.print(digest_text)
                console.print("=" * 60 + "\n")

            except Exception as e:
                logger.error(f"Failed to generate test digest: {e}")
        else:
            logger.warning("No channels configured for testing")

        logger.info("✅ Dry run completed successfully")
        return

    # 3. Run actual digests
    try:
        if channel:
            # Single channel mode
            logger.info(f"Sending {mode} digest to specific channel: {channel}")
            success = slack_app.send_digest(channel, mode)

            if success:
                logger.info(f"✅ {mode.title()} digest sent successfully")
            else:
                logger.error(f"❌ Failed to send {mode} digest")
                sys.exit(1)
        else:
            # Multi-channel mode
            results = run_scheduled_digests(db_manager, slack_app, mode)

            successful = sum(1 for success in results.values() if success)
            total = len(results)

            logger.info(f"📊 Digest summary: {successful}/{total} channels successful")

            if successful < total:
                failed_channels = [ch for ch, success in results.items() if not success]
                logger.error(f"Failed channels: {', '.join(failed_channels)}")
                sys.exit(1)

    except Exception as e:
        logger.error(f"Unexpected error during digest generation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
