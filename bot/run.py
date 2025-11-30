"""Main entry point for LobbyLens bot."""

import html
import json
import logging
import sys
import traceback
from typing import Optional

import click
from rich.console import Console
from rich.logging import RichHandler

from bot.digest import DigestFormatter  # Patch-friendly import for tests
from bot.signals_database import create_signals_database

from .config import settings

# V2 System - Enhanced digest with consolidated modules (no version suffixes)
from .notifiers.base import NotificationError
from .notifiers.email import EmailNotifier
from .notifiers.slack import SlackNotifier

console = Console()


# V2 System Functions
def run_daily_digest(hours_back: int = 24, channel_id: str = "test_channel") -> str:
    """Run daily digest collection and formatting using v2 system"""
    import logging

    # Removed unused imports
    from bot.daily_signals import DailySignalsCollector
    from bot.digest import DigestFormatter
    from bot.signals_database import SignalsDatabaseV2

    logger = logging.getLogger(__name__)
    logger.info(f"Running daily digest for last {hours_back} hours")

    # Initialize components
    db_url = settings.signals_database_url or settings.database_url
    database = create_signals_database(db_url)
    watchlist = database.get_watchlist(channel_id)
    collector = DailySignalsCollector(settings.model_dump(), watchlist)
    formatter = DigestFormatter()

    # Collect signals
    signals = collector.collect_signals(hours_back)
    logger.info(f"Collected {len(signals)} signals")

    try:
        saved = database.save_signals(signals)
        logger.info(f"Saved {saved} signals to database")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"Failed to persist signals: {exc}")

    # Format digest
    digest = formatter.format_daily_digest(signals, hours_back)

    return digest


def run_mini_digest(
    hours_back: int = 4, channel_id: str = "test_channel"
) -> Optional[str]:
    """Run mini digest collection and formatting using v2 system"""
    import logging

    # Removed unused imports
    from bot.daily_signals import DailySignalsCollector
    from bot.digest import DigestFormatter
    from bot.signals_database import SignalsDatabaseV2

    logger = logging.getLogger(__name__)
    logger.info(f"Running mini digest for last {hours_back} hours")

    # Initialize components
    db_url = settings.signals_database_url or settings.database_url
    database = create_signals_database(db_url)
    watchlist = database.get_watchlist(channel_id)
    channel_settings = database.get_channel_settings(channel_id)
    collector = DailySignalsCollector(settings.model_dump(), watchlist)
    formatter = DigestFormatter()

    # Collect signals
    signals = collector.collect_signals(hours_back)
    logger.info(f"Collected {len(signals)} signals")

    try:
        saved = database.save_signals(signals)
        logger.info(f"Saved {saved} signals to database")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"Failed to persist signals: {exc}")

    # Check mini-digest thresholds
    mini_threshold = channel_settings.get("mini_digest_threshold", 10)
    high_threshold = channel_settings.get("high_priority_threshold", 5.0)

    high_priority_signals = [s for s in signals if s.priority_score >= high_threshold]
    watchlist_hits = [s for s in signals if s.watchlist_hit]

    # Mini-digest criteria
    if (
        len(signals) >= mini_threshold
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
    """Set up logging with Rich handler or JSON lines."""
    log_level = getattr(logging, level.upper())
    if settings.log_json:

        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                payload = {
                    "level": record.levelname,
                    "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
                    "message": record.getMessage(),
                    "name": record.name,
                }
                return json.dumps(payload)

        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logging.basicConfig(level=log_level, handlers=[handler])
    else:
        logging.basicConfig(
            level=log_level,
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


def create_notifier() -> object:
    """Create and return configured notifier.

    Returns:
        Configured SlackNotifier instance

    Raises:
        ValueError: If no notifier is properly configured
    """
    settings.validate_notifier_config()

    if settings.notifier_type == "slack":
        return SlackNotifier(settings.slack_webhook_url or "")

    if settings.notifier_type == "email":
        recipients = settings.get_email_recipients()
        return EmailNotifier(
            host=settings.smtp_host or "",
            port=int(settings.smtp_port),
            from_address=settings.email_from_address or "",
            to_addresses=recipients,
            username=settings.smtp_username,
            password=settings.smtp_password,
            use_tls=settings.smtp_use_tls,
            subject_prefix=settings.email_subject_prefix,
        )

    raise ValueError("No supported notifier configured")


def _plain_text_to_html(text: str) -> str:
    """Convert a plain-text digest to lightweight HTML with basic Markdown support."""
    import re

    if not text:
        text = ""

    link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    bold_pattern = re.compile(r"\*\*(.+?)\*\*")

    def render_inline(segment: str) -> str:
        parts: list[str] = []
        last = 0
        for match in link_pattern.finditer(segment):
            parts.append(html.escape(segment[last : match.start()]))
            label = html.escape(match.group(1))
            url = html.escape(match.group(2), quote=True)
            parts.append(f'<a href="{url}">{label}</a>')
            last = match.end()
        parts.append(html.escape(segment[last:]))
        combined = "".join(parts)

        # Bold support (**text**)
        combined = bold_pattern.sub(
            lambda m: f"<strong>{html.escape(m.group(1))}</strong>", combined
        )
        return combined

    lines = text.splitlines()
    html_lines: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("• ") or stripped.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            content = stripped[2:].strip()
            html_lines.append(f"<li>{render_inline(content)}</li>")
        elif stripped.endswith(":") and len(stripped) < 80:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(
                f'<h3 style="margin-bottom:4px;">{render_inline(stripped)}</h3>'
            )
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            if stripped == "":
                html_lines.append("<br/>")
            else:
                html_lines.append(f"<p>{render_inline(stripped)}</p>")

    if in_list:
        html_lines.append("</ul>")

    body = "\n".join(html_lines)
    return (
        "<div style=\"font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;"
        ' font-size: 14px; line-height: 1.5; color: #111;">'
        f"{body}"
        "</div>"
    )


def _send_digest_via_notifier(notifier: object, digest_text: str) -> None:
    """Send digest using notifier; include HTML when emailing."""
    if isinstance(notifier, EmailNotifier):
        html_body = _plain_text_to_html(digest_text)
        notifier.send(digest_text, subject="LobbyLens Daily Digest", html=html_body)
    else:
        notifier.send(digest_text)


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
    """Run LobbyLens daily digest bot using V2 system.

    Collects government signals and sends daily digest via Slack.
    """
    # Override config with CLI options
    if dry_run:
        settings.dry_run = True
    if log_level:
        settings.log_level = log_level

    setup_logging(settings.log_level)

    logger.info("🔍 Starting LobbyLens V2 daily digest bot...")

    # Use V2 system for daily digest
    try:
        logger.info("Generating V2 daily digest...")
        digest_text = run_daily_digest(hours_back=24, channel_id="default")

        if not digest_text:
            digest_text = "No government activity detected in the last 24 hours."

    except Exception as e:
        logger.error(f"Failed to generate V2 digest: {e}")
        digest_text = (
            f"🚨 *LobbyLens V2 Error*\\n\\nFailed to generate daily digest: {e}"
        )

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
        _send_digest_via_notifier(notifier, digest_text)
        logger.info("✅ V2 daily digest sent successfully")

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
