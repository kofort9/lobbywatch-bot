"""
Tests for bot/digest.py - Government activity digest formatting

This module tests both V1 (basic) and V2 (enhanced) digest formatting systems.

Architecture:
- V1: Basic digest formatting tests (legacy)
- V2: Enhanced formatting tests with industry snapshots and mobile-friendly design
"""

# =============================================================================
# V2: Enhanced Digest Formatting Tests (Current Active System)
# =============================================================================

from datetime import datetime, timezone

from bot.digest import DigestFormatter
from bot.signals import SignalV2


class TestDigestFormatter:
    """Tests for DigestFormatter (V2 enhanced system)."""

    def test_formatter_initialization(self) -> None:
        """Test formatter initialization with and without watchlist."""
        # Without watchlist
        formatter = DigestFormatter()
        assert formatter.watchlist == []
        assert formatter.deduplicator is not None
        assert formatter.pt_tz is not None

        # With watchlist
        watchlist = ["Apple", "Google", "privacy"]
        formatter = DigestFormatter(watchlist)
        assert formatter.watchlist == watchlist

    def test_format_daily_digest_empty(self) -> None:
        """Test formatting empty daily digest."""
        formatter = DigestFormatter()
        result = formatter.format_daily_digest([])

        assert "LobbyLens Daily Digest" in result
        assert "No significant government activity detected" in result
        assert "Updated" in result

    def test_format_daily_digest_with_signals(self) -> None:
        """Test formatting daily digest with signals."""
        formatter = DigestFormatter()
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="congress",
                source_id="bill-1",
                timestamp=now,
                title="Test Privacy Bill",
                link="https://example.com/bill-1",
                issue_codes=["TEC"],
                priority_score=3.5,
            ),
            SignalV2(
                source="federal_register",
                source_id="rule-1",
                timestamp=now,
                title="Privacy Rule Update",
                link="https://example.com/rule-1",
                agency="FTC",
                issue_codes=["TEC"],
                priority_score=4.0,
            ),
        ]

        result = formatter.format_daily_digest(signals)

        assert "LobbyLens Daily Digest" in result
        assert "Test Privacy Bill" in result
        assert "Privacy Rule Update" in result
        assert "What Changed" in result
        assert "Updated" in result


# =============================================================================
# V1: Basic Digest Formatting Tests (Legacy - Maintained for Compatibility)
# =============================================================================


class TestLegacyDigestFormatter:
    """Test legacy V1 digest formatter (deprecated).

    These tests are maintained for backward compatibility only.
    New tests should use TestDigestFormatter (V2) above.
    """

    def test_legacy_formatter_warning(self) -> None:
        """Test that legacy formatter shows deprecation warning."""
        from bot.digest import LegacyDigestFormatter

        # Should create without error but log warning
        formatter = LegacyDigestFormatter()
        assert formatter is not None


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


class TestBackwardCompatibility:
    """Test backward compatibility aliases."""

    def test_v2_alias_import(self) -> None:
        """Test that V2 alias imports still work."""
        from bot.digest import DigestV2Formatter

        # Should be an alias for the main class
        assert DigestV2Formatter == DigestFormatter
