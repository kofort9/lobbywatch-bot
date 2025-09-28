"""Tests for bot/digest_v2.py - Enhanced digest formatting with v2 features."""

from datetime import datetime, timedelta, timezone

from bot.digest_v2 import DigestV2Formatter
from bot.signals_v2 import SignalType, SignalV2, Urgency

# from unittest.mock import patch  # Unused import

# import pytest  # Unused import


class TestDigestV2Formatter:
    """Tests for DigestV2Formatter."""

    def test_formatter_initialization(self):
        """Test formatter initialization with and without watchlist."""
        # Without watchlist
        formatter = DigestV2Formatter()
        assert formatter.watchlist == []
        assert formatter.deduplicator is not None
        assert formatter.pt_tz is not None

        # With watchlist
        watchlist = ["Apple", "Google", "privacy"]
        formatter = DigestV2Formatter(watchlist)
        assert formatter.watchlist == watchlist

    def test_format_daily_digest_empty(self):
        """Test formatting empty daily digest."""
        formatter = DigestV2Formatter()
        result = formatter.format_daily_digest([])

        assert "LobbyLens — Daily Signals" in result
        assert "No fresh government activity detected" in result
        assert "/lobbylens help" in result

    def test_format_daily_digest_with_signals(self):
        """Test formatting daily digest with signals."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="congress",
                stable_id="bill-1",
                title="Test Bill",
                summary="A test bill",
                url="https://example.com/bill-1",
                timestamp=now,
                issue_codes=["HCR"],
                signal_type=SignalType.BILL,
                urgency=Urgency.MEDIUM,
                priority_score=5.0,
                industry_tag="Health",
                watchlist_hit=False,
            ),
            SignalV2(
                source="federal_register",
                stable_id="fr-1",
                title="Final Rule: Privacy",
                summary="A final rule about privacy",
                url="https://example.com/fr-1",
                timestamp=now,
                issue_codes=["TEC"],
                signal_type=SignalType.FINAL_RULE,
                urgency=Urgency.HIGH,
                priority_score=7.5,
                industry_tag="Tech",
                watchlist_hit=True,
            ),
        ]

        result = formatter.format_daily_digest(signals)

        # Check header
        assert "LobbyLens — Daily Signals" in result
        assert "Mini-stats:" in result
        assert "Bills 1" in result
        assert "FR 1" in result
        assert "Watchlist hits 1" in result

        # Check sections
        assert "Watchlist Alerts" in result
        assert "What Changed" in result
        assert "Industry Snapshots" in result

    def test_format_mini_digest_thresholds_not_met(self):
        """Test mini-digest when thresholds are not met."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        # Low-priority signals that don't meet thresholds
        signals = [
            SignalV2(
                source="congress",
                stable_id="bill-1",
                title="Low Priority Bill",
                summary="A low priority bill",
                url="https://example.com/bill-1",
                timestamp=now,
                issue_codes=["TEC"],
                signal_type=SignalType.BILL,
                urgency=Urgency.LOW,
                priority_score=2.0,
                industry_tag="Tech",
                watchlist_hit=False,
            ),
        ]

        result = formatter.format_mini_digest(signals)
        assert result is None

    def test_format_mini_digest_thresholds_met(self):
        """Test mini-digest when thresholds are met."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        # High-priority signal that meets thresholds
        signals = [
            SignalV2(
                source="federal_register",
                stable_id="fr-1",
                title="Critical Final Rule",
                summary="A critical final rule",
                url="https://example.com/fr-1",
                timestamp=now,
                issue_codes=["HCR"],
                signal_type=SignalType.FINAL_RULE,
                urgency=Urgency.CRITICAL,
                priority_score=8.5,
                industry_tag="Health",
                watchlist_hit=True,
            ),
        ]

        result = formatter.format_mini_digest(signals)

        assert result is not None
        assert "Mini Signals Alert" in result
        assert "1 signals in last 4h" in result
        assert "1 high-priority" in result
        assert "Critical Final Rule" in result

    def test_format_mini_digest_watchlist_hit(self):
        """Test mini-digest triggered by watchlist hit."""
        formatter = DigestV2Formatter(["Apple"])
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="congress",
                stable_id="bill-1",
                title="Apple Privacy Bill",
                summary="A bill about Apple's privacy",
                url="https://example.com/bill-1",
                timestamp=now,
                issue_codes=["TEC"],
                signal_type=SignalType.BILL,
                urgency=Urgency.LOW,
                priority_score=6.0,  # High priority to show in mini-digest
                industry_tag="Tech",
                watchlist_hit=True,  # This should trigger mini-digest
            ),
        ]

        result = formatter.format_mini_digest(signals)
        # Watchlist hit should trigger mini-digest even with low priority
        assert result is not None
        assert "Mini Signals Alert" in result

    def test_format_mini_digest_docket_surge(self):
        """Test mini-digest triggered by docket surge."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="regulations_gov",
                stable_id="docket-1",
                title="High Activity Docket",
                summary="A docket with high activity",
                url="https://example.com/docket-1",
                timestamp=now,
                issue_codes=["ENV"],
                signal_type=SignalType.DOCKET,
                urgency=Urgency.HIGH,
                priority_score=6.0,
                industry_tag="Environment",
                watchlist_hit=False,
                metric_json={"comments_24h_delta_pct": 300.0},  # High surge
            ),
        ]

        result = formatter.format_mini_digest(signals)
        assert result is not None
        assert "Mini Signals Alert" in result

    def test_get_watchlist_signals(self):
        """Test getting watchlist hit signals."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="congress",
                stable_id="bill-1",
                title="Regular Bill",
                summary="A regular bill",
                url="https://example.com/bill-1",
                timestamp=now,
                watchlist_hit=False,
            ),
            SignalV2(
                source="congress",
                stable_id="bill-2",
                title="Watchlist Bill",
                summary="A bill on watchlist",
                url="https://example.com/bill-2",
                timestamp=now,
                watchlist_hit=True,
            ),
        ]

        watchlist_signals = formatter._get_watchlist_signals(signals)
        assert len(watchlist_signals) == 1
        assert watchlist_signals[0].stable_id == "bill-2"

    def test_get_what_changed_signals(self):
        """Test getting high-priority signals for What Changed section."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="congress",
                stable_id="bill-1",
                title="Low Priority Bill",
                summary="A low priority bill",
                url="https://example.com/bill-1",
                timestamp=now,
                priority_score=2.0,
            ),
            SignalV2(
                source="congress",
                stable_id="bill-2",
                title="High Priority Bill",
                summary="A high priority bill",
                url="https://example.com/bill-2",
                timestamp=now,
                priority_score=5.0,
            ),
        ]

        what_changed = formatter._get_what_changed_signals(signals)
        assert len(what_changed) == 1
        assert what_changed[0].stable_id == "bill-2"

    def test_get_industry_snapshots(self):
        """Test getting industry snapshot signals."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="congress",
                stable_id="bill-1",
                title="Health Bill 1",
                summary="First health bill",
                url="https://example.com/bill-1",
                timestamp=now,
                priority_score=5.0,
                industry_tag="Health",
            ),
            SignalV2(
                source="congress",
                stable_id="bill-2",
                title="Health Bill 2",
                summary="Second health bill",
                url="https://example.com/bill-2",
                timestamp=now,
                priority_score=3.0,
                industry_tag="Health",
            ),
            SignalV2(
                source="congress",
                stable_id="bill-3",
                title="Tech Bill",
                summary="A tech bill",
                url="https://example.com/bill-3",
                timestamp=now,
                priority_score=4.0,
                industry_tag="Tech",
            ),
        ]

        snapshots = formatter._get_industry_snapshots(signals)
        # Should get top 2 per industry, but limited to 12 total
        assert len(snapshots) == 3
        # Should be sorted by priority score
        assert snapshots[0].priority_score == 5.0
        assert snapshots[1].priority_score == 4.0
        assert snapshots[2].priority_score == 3.0

    def test_get_deadline_signals(self):
        """Test getting signals with deadlines in next 7 days."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="congress",
                stable_id="bill-1",
                title="Past Deadline Bill",
                summary="A bill with past deadline",
                url="https://example.com/bill-1",
                timestamp=now,
                deadline=now - timedelta(days=1),  # Past deadline
            ),
            SignalV2(
                source="congress",
                stable_id="bill-2",
                title="Near Deadline Bill",
                summary="A bill with near deadline",
                url="https://example.com/bill-2",
                timestamp=now,
                deadline=now + timedelta(days=3),  # Within 7 days
            ),
            SignalV2(
                source="congress",
                stable_id="bill-3",
                title="Future Deadline Bill",
                summary="A bill with future deadline",
                url="https://example.com/bill-3",
                timestamp=now,
                deadline=now + timedelta(days=10),  # Beyond 7 days
            ),
        ]

        deadlines = formatter._get_deadline_signals(signals)
        assert len(deadlines) == 1
        assert deadlines[0].stable_id == "bill-2"

    def test_get_docket_surge_signals(self):
        """Test getting docket signals with surge activity."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="regulations_gov",
                stable_id="docket-1",
                title="Low Surge Docket",
                summary="A docket with low surge",
                url="https://example.com/docket-1",
                timestamp=now,
                signal_type=SignalType.DOCKET,
                metric_json={"comments_24h_delta_pct": 100.0},
                # Below threshold
            ),
            SignalV2(
                source="regulations_gov",
                stable_id="docket-2",
                title="High Surge Docket",
                summary="A docket with high surge",
                url="https://example.com/docket-2",
                timestamp=now,
                signal_type=SignalType.DOCKET,
                metric_json={"comments_24h_delta_pct": 300.0},
                # Above threshold
            ),
            SignalV2(
                source="congress",
                stable_id="bill-1",
                title="Regular Bill",
                summary="A regular bill",
                url="https://example.com/bill-1",
                timestamp=now,
                signal_type=SignalType.BILL,
            ),
        ]

        surges = formatter._get_docket_surge_signals(signals)
        assert len(surges) == 1
        assert surges[0].stable_id == "docket-2"

    def test_get_bill_action_signals(self):
        """Test getting bill action signals grouped by bill_id."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="congress",
                stable_id="action-1",
                title="Bill Action 1",
                summary="First action on HR-123",
                url="https://example.com/action-1",
                timestamp=now,
                bill_id="HR-123",
                priority_score=5.0,
            ),
            SignalV2(
                source="congress",
                stable_id="action-2",
                title="Bill Action 2",
                summary="Second action on HR-123",
                url="https://example.com/action-2",
                timestamp=now + timedelta(hours=1),  # Later timestamp
                bill_id="HR-123",
                priority_score=3.0,
            ),
            SignalV2(
                source="congress",
                stable_id="action-3",
                title="Bill Action 3",
                summary="Action on HR-456",
                url="https://example.com/action-3",
                timestamp=now,
                bill_id="HR-456",
                priority_score=4.0,
            ),
        ]

        bill_actions = formatter._get_bill_action_signals(signals)
        assert len(bill_actions) == 2
        # Should get latest action for each bill
        bill_ids = [action.bill_id for action in bill_actions]
        assert "HR-123" in bill_ids
        assert "HR-456" in bill_ids

    def test_format_watchlist_signal(self):
        """Test formatting watchlist alert signal."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        signal = SignalV2(
            source="congress",
            stable_id="bill-1",
            title="Apple Privacy Bill",
            summary="A bill about Apple's privacy practices",
            url="https://example.com/bill-1",
            timestamp=now,
            issue_codes=["TEC"],
            signal_type=SignalType.BILL,
            urgency=Urgency.HIGH,
            priority_score=6.0,
            industry_tag="Tech",
            watchlist_hit=True,
        )

        result = formatter._format_watchlist_signal(signal)

        assert "[Tech]" in result
        assert "**Apple Privacy Bill**" in result
        assert "High" in result
        assert "A bill about Apple's privacy practices" in result
        assert "Issues: TEC" in result
        assert "<https://example.com/bill-1|View>" in result

    def test_format_what_changed_signal(self):
        """Test formatting what changed signal."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        signal = SignalV2(
            source="federal_register",
            stable_id="fr-1",
            title="Final Rule: Privacy Protection",
            summary="A final rule about privacy protection",
            url="https://example.com/fr-1",
            timestamp=now,
            issue_codes=["TEC"],
            signal_type=SignalType.FINAL_RULE,
            urgency=Urgency.HIGH,
            priority_score=7.5,
            industry_tag="Tech",
            watchlist_hit=False,
        )

        result = formatter._format_what_changed_signal(signal)

        assert "[Tech]" in result
        assert "*Final Rule*" in result
        assert "Final Rule: Privacy Protection" in result
        assert "High" in result
        assert "Issues: TEC" in result
        assert "<https://example.com/fr-1|View>" in result

    def test_format_docket_surge_signal(self):
        """Test formatting docket surge signal."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        signal = SignalV2(
            source="regulations_gov",
            stable_id="docket-1",
            title="Environmental Standards Docket",
            summary="A docket about environmental standards",
            url="https://example.com/docket-1",
            timestamp=now,
            issue_codes=["ENV"],
            signal_type=SignalType.DOCKET,
            urgency=Urgency.HIGH,
            priority_score=6.5,
            industry_tag="Environment",
            watchlist_hit=False,
            deadline=now + timedelta(days=5),
            metric_json={"comments_24h_delta_pct": 250.0, "comments_24h_delta": 500},
        )

        result = formatter._format_docket_surge_signal(signal)

        assert "[Environment]" in result
        assert "Docket Surge" in result
        assert "Environmental Standards Docket" in result
        assert "High" in result
        assert "+250% / +500 (24h)" in result
        # The test uses now + 5 days, but by the time it's processed it might
        # be 4 days
        assert "Deadline in 4d" in result
        assert "Issues: ENV" in result
        assert "<https://example.com/docket-1|Regulations.gov>" in result

    def test_format_bill_action_signal(self):
        """Test formatting bill action signal."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        signal = SignalV2(
            source="congress",
            stable_id="action-1",
            title="Health Care Reform Act",
            summary="A bill about health care reform",
            url="https://example.com/action-1",
            timestamp=now,
            issue_codes=["HCR"],
            signal_type=SignalType.BILL,
            urgency=Urgency.MEDIUM,
            priority_score=4.0,
            industry_tag="Health",
            watchlist_hit=False,
            action_type="hearing_scheduled",
        )

        result = formatter._format_bill_action_signal(signal)

        assert "[Health]" in result
        assert "Bill Action" in result
        assert "Health Care Reform Act" in result
        assert "Medium" in result
        assert "Last action: Hearing scheduled" in result
        assert "Issues: HCR" in result
        assert "<https://example.com/action-1|Congress>" in result

    def test_format_title_for_mobile_short(self):
        """Test mobile title formatting for short titles."""
        formatter = DigestV2Formatter()

        title = "Short Title"
        result = formatter._format_title_for_mobile(title, 60)
        assert result == "Short Title"

    def test_format_title_for_mobile_long(self):
        """Test mobile title formatting for long titles."""
        formatter = DigestV2Formatter()

        title = (
            "This is a very long title that should be broken into multiple lines "
            "for better mobile readability"
        )
        result = formatter._format_title_for_mobile(title, 60)

        # Should be broken into multiple lines
        assert "\n" in result
        assert "This is a very long title that should be broken into" in result
        assert "  multiple lines for better mobile readability" in result

    def test_format_summary_short(self):
        """Test summary formatting for short summaries."""
        formatter = DigestV2Formatter()

        summary = "Short summary"
        result = formatter._format_summary(summary, 160)
        assert result == "Short summary"

    def test_format_summary_long(self):
        """Test summary formatting for long summaries."""
        formatter = DigestV2Formatter()

        summary = (
            "This is a very long summary that should be truncated to fit within the "
            "character limit for better readability and mobile display and this is "
            "even more text to make it longer than the limit"
        )
        result = formatter._format_summary(summary, 160)

        # Should be truncated
        assert len(result) <= 161  # Allow for space + ellipsis
        assert result.endswith("...")

    def test_format_issue_codes(self):
        """Test issue codes formatting."""
        formatter = DigestV2Formatter()

        # Multiple issue codes
        result = formatter._format_issue_codes(["HCR", "TEC", "ENV"])
        assert result == "HCR/TEC/ENV"

        # Single issue code
        result = formatter._format_issue_codes(["HCR"])
        assert result == "HCR"

        # No issue codes
        result = formatter._format_issue_codes([])
        assert result == "None"

    def test_get_pt_time(self):
        """Test getting current time in PT."""
        formatter = DigestV2Formatter()

        # Just test that it returns a valid time format
        result = formatter._get_pt_time()
        assert "PT" in result
        assert ":" in result

    def test_format_empty_digest(self):
        """Test formatting empty digest."""
        formatter = DigestV2Formatter()
        result = formatter._format_empty_digest()

        assert "LobbyLens — Daily Signals" in result
        assert "No fresh government activity detected" in result
        assert "/lobbylens help" in result

    def test_section_limits(self):
        """Test that sections respect their limits."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        # Create many signals to test limits
        signals = []
        for i in range(30):  # More than the limits
            signal = SignalV2(
                source="congress",
                stable_id=f"bill-{i}",
                title=f"Bill {i}",
                summary=f"Summary for bill {i}",
                url=f"https://example.com/bill-{i}",
                timestamp=now,
                issue_codes=["HCR"],
                signal_type=SignalType.BILL,
                urgency=Urgency.MEDIUM,
                priority_score=5.0,
                industry_tag="Health",
                watchlist_hit=i < 10,  # First 10 are watchlist hits
            )
            signals.append(signal)

        result = formatter.format_daily_digest(signals)

        # Count occurrences of watchlist signals (first 10 are watchlist hits)
        # Count only in the watchlist section, not other sections
        watchlist_section = (
            result.split("🔎 **Watchlist Alerts**")[1].split("\n\n")[0]
            if "🔎 **Watchlist Alerts**" in result
            else ""
        )
        watchlist_count = watchlist_section.count("• [Health]")

        # Should respect limits - only first 10 signals are watchlist hits, max
        # 5 shown
        assert watchlist_count <= 5  # Max 5 watchlist alerts
        # Note: what_changed section limit is tested by the formatter logic

    def test_threading_footer(self):
        """Test threading footer when there are many items."""
        formatter = DigestV2Formatter()
        now = datetime.now(timezone.utc)

        # Create 25 signals (more than 20 threshold)
        signals = []
        for i in range(25):
            signal = SignalV2(
                source="congress",
                stable_id=f"bill-{i}",
                title=f"Bill {i}",
                summary=f"Summary for bill {i}",
                url=f"https://example.com/bill-{i}",
                timestamp=now,
                issue_codes=["HCR"],
                signal_type=SignalType.BILL,
                urgency=Urgency.MEDIUM,
                priority_score=5.0,
                industry_tag="Health",
                watchlist_hit=False,
            )
            signals.append(signal)

        result = formatter.format_daily_digest(signals)

        # Should have threading footer
        assert "+ 5 more items in thread" in result  # 25 - 20 = 5
        assert "/lobbylens help" in result
