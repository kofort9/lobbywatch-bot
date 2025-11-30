"""
End-to-end tests for V2 path: collect signals → format digest → send via notifier.

These tests exercise the full V2 pipeline with mocked external dependencies.
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import Mock, patch

import pytest

from bot.daily_signals import DailySignalsCollector
from bot.digest import DigestFormatter
from bot.notifiers.email import EmailNotifier
from bot.run import run_daily_digest, run_mini_digest
from bot.signals import SignalV2


class TestV2EndToEnd:
    """End-to-end tests for V2 digest pipeline."""

    @pytest.fixture
    def mock_signals(self) -> list[SignalV2]:
        """Create mock signals for testing."""
        return [
            SignalV2(
                source="federal_register",
                source_id="FR-2024-00123",
                timestamp=datetime.now(timezone.utc),
                title="Privacy Regulation Update",
                link="https://federalregister.gov/d/2024-00123",
                agency="Federal Trade Commission",
                issue_codes=["TEC", "HCR"],
                priority_score=6.5,
                watchlist_hit=True,
            ),
            SignalV2(
                source="congress",
                source_id="HR-1234",
                timestamp=datetime.now(timezone.utc),
                title="Data Privacy Act of 2024",
                link="https://congress.gov/bill/118/hr1234",
                bill_id="HR-1234",
                issue_codes=["TEC"],
                priority_score=5.2,
            ),
        ]

    @patch("bot.daily_signals.DailySignalsCollector")
    @patch("bot.digest.DigestFormatter")
    def test_e2e_daily_digest_with_email(
        self,
        mock_formatter_class: Any,
        mock_collector_class: Any,
        mock_signals: list[SignalV2],
    ) -> None:
        """Test full V2 pipeline: collect → format → send via email."""
        # Setup mocks
        mock_collector = Mock()
        mock_formatter = Mock()

        mock_collector_class.return_value = mock_collector
        mock_formatter_class.return_value = mock_formatter

        # Configure mock returns
        mock_collector.collect_signals.return_value = mock_signals
        mock_digest_text = "📋 **Daily Digest**\n\n• Privacy Regulation Update"
        mock_formatter.format_daily_digest.return_value = mock_digest_text

        # Run the pipeline
        result = run_daily_digest(hours_back=24, channel_id="test_channel")

        # Verify pipeline steps
        mock_collector_class.assert_called_once()
        mock_collector.collect_signals.assert_called_once_with(24)
        mock_formatter_class.assert_called_once()
        mock_formatter.format_daily_digest.assert_called_once_with(mock_signals, 24)

        # Result should be the formatted digest
        assert result == mock_digest_text

    @patch("bot.daily_signals.DailySignalsCollector")
    @patch("bot.digest.DigestFormatter")
    @patch("smtplib.SMTP")
    def test_e2e_daily_digest_email_send(
        self,
        mock_smtp_class: Any,
        mock_formatter_class: Any,
        mock_collector_class: Any,
        mock_signals: list[SignalV2],
    ) -> None:
        """Test that email notifier is called with correct payload."""
        # Setup mocks
        mock_collector = Mock()
        mock_formatter = Mock()
        mock_smtp_ctx = Mock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp_ctx

        mock_collector_class.return_value = mock_collector
        mock_formatter_class.return_value = mock_formatter

        mock_collector.collect_signals.return_value = mock_signals
        mock_digest_text = "📋 **Daily Digest**\n\n• Privacy Regulation Update"
        mock_formatter.format_daily_digest.return_value = mock_digest_text

        # Generate digest
        digest = run_daily_digest(hours_back=24, channel_id="test_channel")

        # Send via email (simulating what main() would do)
        notifier = EmailNotifier(
            host="smtp.example.com",
            port=587,
            from_address="bot@example.com",
            to_addresses=["user@example.com"],
            use_tls=True,
        )
        notifier.send(digest, subject="Daily Digest")

        # Verify email was sent
        mock_smtp_ctx.starttls.assert_called_once()
        mock_smtp_ctx.send_message.assert_called_once()

        # Verify email content
        sent_msg = mock_smtp_ctx.send_message.call_args[0][0]
        assert "Daily Digest" in sent_msg["Subject"]
        assert digest in sent_msg.get_payload()

    @patch("bot.daily_signals.DailySignalsCollector")
    @patch("bot.digest.DigestFormatter")
    def test_e2e_mini_digest_threshold_met(
        self,
        mock_formatter_class: Any,
        mock_collector_class: Any,
        mock_signals: list[SignalV2],
    ) -> None:
        """Test mini digest when thresholds are met."""
        mock_collector = Mock()
        mock_formatter = Mock()

        mock_collector_class.return_value = mock_collector
        mock_formatter_class.return_value = mock_formatter

        # Create signals that meet mini-digest thresholds
        high_priority_signal = SignalV2(
            source="federal_register",
            source_id="FR-2024-00123",
            timestamp=datetime.now(timezone.utc),
            title="High Priority Rule",
            link="https://example.com",
            priority_score=6.0,  # Above threshold
        )
        watchlist_signal = SignalV2(
            source="congress",
            source_id="HR-1234",
            timestamp=datetime.now(timezone.utc),
            title="Watchlist Match",
            link="https://example.com",
            watchlist_hit=True,
        )

        mock_collector.collect_signals.return_value = [
            high_priority_signal,
            watchlist_signal,
        ]
        mock_formatter.format_mini_digest.return_value = "⚡ Mini Digest"

        result = run_mini_digest(hours_back=4, channel_id="test_channel")

        assert result == "⚡ Mini Digest"
        mock_formatter.format_mini_digest.assert_called_once()

    @patch("bot.daily_signals.DailySignalsCollector")
    @patch("bot.digest.DigestFormatter")
    def test_e2e_mini_digest_threshold_not_met(
        self,
        mock_formatter_class: Any,
        mock_collector_class: Any,
    ) -> None:
        """Test mini digest when thresholds are not met."""
        mock_collector = Mock()
        mock_formatter = Mock()

        mock_collector_class.return_value = mock_collector
        mock_formatter_class.return_value = mock_formatter

        # Create signals that don't meet thresholds
        low_priority_signals = [
            SignalV2(
                source="federal_register",
                source_id="FR-2024-00123",
                timestamp=datetime.now(timezone.utc),
                title="Low Priority Notice",
                link="https://example.com",
                priority_score=2.0,  # Below threshold
            )
        ]

        mock_collector.collect_signals.return_value = low_priority_signals

        result = run_mini_digest(hours_back=4, channel_id="test_channel")

        assert result is None
        mock_formatter.format_mini_digest.assert_not_called()

    @patch("bot.daily_signals.DailySignalsCollector")
    @patch("bot.digest.DigestFormatter")
    def test_e2e_digest_with_watchlist_hits(
        self,
        mock_formatter_class: Any,
        mock_collector_class: Any,
        mock_signals: list[SignalV2],
    ) -> None:
        """Test digest generation includes watchlist hits."""
        mock_collector = Mock()
        mock_formatter = Mock()

        mock_collector_class.return_value = mock_collector
        mock_formatter_class.return_value = mock_formatter

        # Signal with watchlist hit
        watchlist_signal = SignalV2(
            source="federal_register",
            source_id="FR-2024-00123",
            timestamp=datetime.now(timezone.utc),
            title="Google Privacy Policy Update",
            link="https://example.com",
            watchlist_hit=True,
            priority_score=7.0,
        )

        mock_collector.collect_signals.return_value = [watchlist_signal]
        mock_formatter.format_daily_digest.return_value = "📋 Digest with watchlist"

        result = run_daily_digest(hours_back=24, channel_id="test_channel")

        assert result == "📋 Digest with watchlist"
        # Verify watchlist signal was passed to formatter
        call_args = mock_formatter.format_daily_digest.call_args[0]
        assert len(call_args[0]) == 1
        assert call_args[0][0].watchlist_hit is True
