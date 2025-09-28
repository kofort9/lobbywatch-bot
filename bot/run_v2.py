"""
LobbyLens Run v2 - Enhanced entry point with v2 features
Integrates the complete v2 system with rules engine, database, and digest formatting.
"""

import argparse
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

from bot.config import settings
from bot.daily_signals_v2 import DailySignalsCollectorV2
from bot.digest_v2 import DigestV2Formatter
from bot.signals_database_v2 import SignalsDatabaseV2
from bot.test_fixtures_v2 import TestFixturesV2, TestValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_daily_digest(hours_back: int = 24, channel_id: str = "test_channel") -> str:
    """Run daily digest collection and formatting"""
    logger.info(f"Running daily digest for last {hours_back} hours")

    # Initialize components
    collector = DailySignalsCollectorV2(settings.model_dump())
    formatter = DigestV2Formatter()
    database = SignalsDatabaseV2()

    # Get watchlist for channel
    watchlist = [item["name"] for item in database.get_watchlist(channel_id)]

    # Collect signals
    signals = collector.collect_all_signals(hours_back)
    logger.info(f"Collected {len(signals)} signals")

    # Format digest
    digest = formatter.format_daily_digest(signals, hours_back)

    return digest


def run_mini_digest(
    hours_back: int = 4, channel_id: str = "test_channel"
) -> Optional[str]:
    """Run mini digest collection and formatting"""
    logger.info(f"Running mini digest for last {hours_back} hours")

    # Initialize components
    collector = DailySignalsCollectorV2(settings.model_dump())
    formatter = DigestV2Formatter()
    database = SignalsDatabaseV2()

    # Get watchlist for channel
    watchlist = [item["name"] for item in database.get_watchlist(channel_id)]

    # Collect signals
    signals = collector.collect_all_signals(hours_back)
    logger.info(f"Collected {len(signals)} signals")

    # Format mini digest
    mini_digest = formatter.format_mini_digest(signals)

    return mini_digest


def run_test_scenarios() -> None:
    """Run comprehensive test scenarios"""
    logger.info("Running test scenarios")

    # Initialize test fixtures
    fixtures = TestFixturesV2()
    validator = TestValidator()

    # Test scenarios
    test_scenarios = [
        ("Mixed Day", fixtures.get_fixture_a_mixed_day()),
        ("Watchlist Hit", fixtures.get_fixture_b_watchlist_hit()),
        ("Mini Digest Threshold", fixtures.get_fixture_c_mini_digest_threshold()),
        ("Character Budget Stress", fixtures.get_fixture_d_character_budget_stress()),
        ("Timezone Test", fixtures.get_fixture_e_timezone_test()),
    ]

    for scenario_name, test_signals in test_scenarios:
        logger.info(f"Testing scenario: {scenario_name}")

        # Process signals through rules engine
        from bot.signals_v2 import SignalsRulesEngine

        # Set up watchlist for watchlist hit scenario
        watchlist = ["google", "microsoft"] if "Watchlist" in scenario_name else []
        rules_engine = SignalsRulesEngine(watchlist)

        processed_signals = []
        for signal in test_signals:
            processed_signal = rules_engine.process_signal(signal)
            processed_signals.append(processed_signal)

        # Format digest with watchlist
        formatter = DigestV2Formatter(watchlist)
        digest = formatter.format_daily_digest(processed_signals)

        # Validate digest
        validator.validate_digest_format(digest)
        validator.validate_section_limits(digest)
        validator.validate_mobile_formatting(digest)
        validator.validate_timezone_handling(digest)

        # Print results
        print(f"\n=== {scenario_name} ===")
        print(digest)
        print(f"\nValidation Report:")
        print(validator.get_validation_report())
        print("\n" + "=" * 50 + "\n")


def run_quarterly_lda_ingest() -> None:
    """Run quarterly LDA data ingest (placeholder)"""
    logger.info("Running quarterly LDA ingest")
    # This would integrate with the quarterly LDA data processing
    # For now, just log that it would run
    logger.info("Quarterly LDA ingest would run here")


def run_web_server(port: Optional[int] = None) -> None:
    """Run web server for Slack integration"""
    # Use Railway's dynamic port if available
    if port is None:
        port = int(os.environ.get("PORT", 8000))

    logger.info(f"Starting web server on port {port}")

    from bot.web_server_v2 import create_web_server_v2

    app = create_web_server_v2()
    app.run(host="0.0.0.0", port=port, debug=False)


def main() -> None:
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="LobbyLens v2 - Enhanced Government Signals Bot"
    )
    parser.add_argument(
        "--mode",
        choices=["daily", "mini", "test", "quarterly", "server"],
        default="daily",
        help="Run mode",
    )
    parser.add_argument(
        "--hours", type=int, default=24, help="Hours back to collect signals"
    )
    parser.add_argument(
        "--channel", type=str, default="test_channel", help="Slack channel ID"
    )
    parser.add_argument("--port", type=int, default=8000, help="Web server port")
    parser.add_argument(
        "--dry-run", action="store_true", help="Dry run (no Slack posting)"
    )

    args = parser.parse_args()

    try:
        if args.mode == "daily":
            digest = run_daily_digest(args.hours, args.channel)
            print("=== DAILY DIGEST ===")
            print(digest)

            if not args.dry_run:
                # Here you would post to Slack
                logger.info("Would post to Slack (dry-run disabled)")
            else:
                logger.info("Dry run - not posting to Slack")

        elif args.mode == "mini":
            mini_digest = run_mini_digest(args.hours, args.channel)
            if mini_digest:
                print("=== MINI DIGEST ===")
                print(mini_digest)

                if not args.dry_run:
                    # Here you would post to Slack
                    logger.info("Would post to Slack (dry-run disabled)")
                else:
                    logger.info("Dry run - not posting to Slack")
            else:
                print("No mini digest - thresholds not met")

        elif args.mode == "test":
            run_test_scenarios()

        elif args.mode == "quarterly":
            run_quarterly_lda_ingest()

        elif args.mode == "server":
            run_web_server(args.port)

    except Exception as e:
        logger.error(f"Error in {args.mode} mode: {e}")
        raise


if __name__ == "__main__":
    main()
