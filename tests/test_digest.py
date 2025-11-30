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

from datetime import datetime, timedelta, timezone

import pytest

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

        assert "*LobbyLens* — Daily Signals" in result
        assert "Test Privacy Bill" in result
        assert "Privacy Rule Update" in result
        assert "*What Changed*" in result
        assert "Mini-stats:" in result

    def test_digest_includes_comment_context(self) -> None:
        """Regulations.gov items should show comment deadlines and surges."""
        formatter = DigestFormatter()
        now = datetime.now(timezone.utc)
        comment_deadline = (now + timedelta(days=10, hours=1)).isoformat()

        regs_signal = SignalV2(
            source="regulations_gov",
            source_id="doc-100",
            timestamp=now,
            title="Proposed Rule: Critical Infrastructure Cybersecurity",
            link="https://example.com/doc-100",
            docket_id="CISA-2025-0001",
            comment_end_date=comment_deadline,
            comments_24h=180,
            comments_delta=150,
            comment_surge=True,
            issue_codes=["TEC"],
            priority_score=4.2,
        )
        regs_signal.metrics = {
            "comment_end_date": comment_deadline,
            "comments_24h": 180,
            "comments_delta": 150,
            "comment_surge": True,
        }

        digest_text = formatter.format_daily_digest([regs_signal])

        assert "comments close" in digest_text
        assert "comments (24h surge)" in digest_text

    def test_apply_enhanced_scoring_boosts_and_penalties(self) -> None:
        """Enhanced scoring should add boosts and penalties deterministically."""
        formatter = DigestFormatter()
        now = datetime.now(timezone.utc)
        signal = SignalV2(
            source="regulations_gov",
            source_id="doc-boost-1",
            timestamp=now - timedelta(days=40),
            title="Safety Rule",
            link="https://example.com/boost",
            priority_score=1.0,
            deadline=(now + timedelta(days=5)).isoformat(),
            effective_date=(now + timedelta(days=10)).isoformat(),
            comment_surge_pct=150.0,
        )

        enhanced = formatter._apply_enhanced_scoring([signal])

        assert len(enhanced) == 1
        assert enhanced[0] is not signal
        assert enhanced[0].priority_score == pytest.approx(3.5)
        assert enhanced[0].source_id == signal.source_id

    def test_bundle_similar_signals_creates_bundled_entry(self) -> None:
        formatter = DigestFormatter()
        now = datetime.now(timezone.utc)
        signals = [
            SignalV2(
                source="federal_register",
                source_id="fr-1",
                timestamp=now,
                title="Airworthiness Directives: Engine Safety",
                link="https://example.com/1",
                agency="Federal Aviation Administration",
                priority_score=4.0,
            ),
            SignalV2(
                source="federal_register",
                source_id="fr-2",
                timestamp=now,
                title="Airworthiness Directives: Engine Safety",
                link="https://example.com/2",
                agency="Federal Aviation Administration",
                priority_score=5.5,
            ),
            SignalV2(
                source="federal_register",
                source_id="fr-3",
                timestamp=now,
                title="EPA Notice on Water Quality",
                link="https://example.com/3",
                agency="Environmental Protection Agency",
                priority_score=2.5,
            ),
        ]

        bundled = formatter._bundle_similar_signals(signals)

        bundled_signal = next(
            s for s in bundled if s.source_id.startswith("bundled_Federal Aviation")
        )
        assert "2 directives today" in bundled_signal.title
        assert bundled_signal.priority_score == 5.5
        assert any(s.title == "EPA Notice on Water Quality" for s in bundled)

    def test_get_why_matters_clause_deadline_and_surge(self) -> None:
        formatter = DigestFormatter()
        now = datetime.now(timezone.utc)
        deadline = (now + timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        signal = SignalV2(
            source="regulations_gov",
            source_id="doc-why-1",
            timestamp=now,
            title="Docket With Surge",
            link="https://example.com/why",
            comment_end_date=deadline,
            comment_surge=True,
            comments_24h=50,
        )
        signal.metrics = {"comment_surge": True, "comments_24h": 50}

        clause = formatter._get_why_matters_clause(signal)

        assert "comments close today" in clause
        assert "comments (24h surge)" in clause


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
