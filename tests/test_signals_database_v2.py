"""Tests for bot/signals_database_v2.py - Enhanced database for v2 signals."""

# import json  # Unused import
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from bot.signals_database_v2 import SignalsDatabaseV2
from bot.signals_v2 import SignalType, SignalV2, Urgency

class TestSignalsDatabaseV2:
    """Tests for SignalsDatabaseV2."""

    @pytest.fixture
    def temp_db(self) -> Any:
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        db = SignalsDatabaseV2(db_path)
        yield db

        # Cleanup
        Path(db_path).unlink(missing_ok=True)

    def test_database_initialization(self, temp_db: Any) -> None:
        """Test database initialization and schema creation."""
        # Check that tables were created
        conn = sqlite3.connect(temp_db.db_path)
        cur = conn.cursor()

        # Check signals_v2 table
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='signals_v2'"
        )
        assert cur.fetchone() is not None

        # Check watchlist_v2 table
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='watchlist_v2'"
        )
        assert cur.fetchone() is not None

        # Check channel_settings_v2 table
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND
        name='channel_settings_v2'"
        )
        assert cur.fetchone() is not None

        # Check indexes were created
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE
        'idx_signals_%'"
        )
        indexes = [row[0] for row in cur.fetchall()]
        assert len(indexes) > 0

        conn.close()

    def test_store_signal(self, temp_db: Any) -> None:
        """Test storing a single signal."""
        now = datetime.now(timezone.utc)
        signal = SignalV2(
            source="congress",
            stable_id="bill-123",
            title="Test Bill",
            summary="A test bill",
            url="https://example.com/bill-123",
            timestamp=now,
            issue_codes=["HCR"],
            bill_id="HR-123",
            action_type="introduced",
            agency="HHS",
            comment_count=100,
            deadline=now + timedelta(days=30),
            metric_json={"comments_24h_delta_pct": 50.0},
            signal_type=SignalType.BILL,
            urgency=Urgency.MEDIUM,
            priority_score=5.0,
            industry_tag="Health",
            watchlist_hit=True,
        )

        result = temp_db.store_signal(signal)
        assert result is True

        # Verify signal was stored
        signals = temp_db.get_recent_signals(24)
        assert len(signals) == 1
        assert signals[0].stable_id == "bill-123"
        assert signals[0].title == "Test Bill"
        assert signals[0].issue_codes == ["HCR"]
        assert signals[0].priority_score == 5.0
        # SQLite stores booleans as integers
        assert signals[0].watchlist_hit == 1

    def test_store_signal_duplicate(self, temp_db: Any) -> None:
        """Test storing duplicate signal (should update)."""
        now = datetime.now(timezone.utc)
        signal1 = SignalV2(
            source="congress",
            stable_id="bill-123",
            title="Original Bill",
            summary="Original summary",
            url="https://example.com/bill-123",
            timestamp=now,
            priority_score=3.0,
        )

        signal2 = SignalV2(
            source="congress",
            stable_id="bill-123",  # Same stable_id
            title="Updated Bill",
            summary="Updated summary",
            url="https://example.com/bill-123",
            timestamp=now,
            priority_score=7.0,  # Higher priority
        )

        # Store both signals
        temp_db.store_signal(signal1)
        temp_db.store_signal(signal2)

        # Should only have one signal (the updated one)
        signals = temp_db.get_recent_signals(24)
        assert len(signals) == 1
        assert signals[0].title == "Updated Bill"
        assert signals[0].priority_score == 7.0

    def test_store_signals_multiple(self, temp_db: Any) -> None:
        """Test storing multiple signals."""
        now = datetime.now(timezone.utc)
        signals = [
            SignalV2(
                source="congress",
                stable_id=f"bill-{i}",
                title=f"Bill {i}",
                summary=f"Summary {i}",
                url=f"https://example.com/bill-{i}",
                timestamp=now,
                priority_score=float(i),
            )
            for i in range(5)
        ]

        stored_count = temp_db.store_signals(signals)
        assert stored_count == 5

        # Verify all signals were stored
        recent_signals = temp_db.get_recent_signals(24)
        assert len(recent_signals) == 5

    def test_get_recent_signals(self, temp_db: Any) -> None:
        """Test getting recent signals."""
        now = datetime.now(timezone.utc)

        # Create signals with different timestamps
        old_signal = SignalV2(
            source="congress",
            stable_id="old-bill",
            title="Old Bill",
            summary="An old bill",
            url="https://example.com/old-bill",
            timestamp=now - timedelta(hours=25),  # 25 hours ago
            priority_score=3.0,
        )

        recent_signal = SignalV2(
            source="congress",
            stable_id="recent-bill",
            title="Recent Bill",
            summary="A recent bill",
            url="https://example.com/recent-bill",
            timestamp=now - timedelta(hours=12),  # 12 hours ago
            priority_score=5.0,
        )

        temp_db.store_signal(old_signal)
        temp_db.store_signal(recent_signal)

        # Get signals from last 24 hours
        recent_signals = temp_db.get_recent_signals(24)
        assert len(recent_signals) == 1
        assert recent_signals[0].stable_id == "recent-bill"

        # Get signals from last 30 hours
        recent_signals = temp_db.get_recent_signals(30)
        assert len(recent_signals) == 2

    def test_get_high_priority_signals(self, temp_db: Any) -> None:
        """Test getting high priority signals."""
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="congress",
                stable_id=f"bill-{i}",
                title=f"Bill {i}",
                summary=f"Summary {i}",
                url=f"https://example.com/bill-{i}",
                timestamp=now,
                priority_score=float(i * 2),  # 0, 2, 4, 6, 8
            )
            for i in range(5)
        ]

        temp_db.store_signals(signals)

        # Get signals with priority >= 5.0
        high_priority = temp_db.get_high_priority_signals(5.0)
        assert len(high_priority) == 2  # Only signals with score 6.0 and 8.0
        assert all(s.priority_score >= 5.0 for s in high_priority)

    def test_watchlist_operations(self, temp_db: Any) -> None:
        """Test watchlist add/remove/get operations."""
        channel_id = "C1234567890"

        # Add watchlist items
        assert temp_db.add_watchlist_item(channel_id, "Apple", "company") is True
        assert temp_db.add_watchlist_item(channel_id, "Google", "company") is True
        assert temp_db.add_watchlist_item(channel_id, "privacy", "topic") is True

        # Get watchlist
        watchlist = temp_db.get_watchlist(channel_id)
        assert len(watchlist) == 3
        assert any(item["name"] == "Apple" for item in watchlist)
        assert any(item["name"] == "Google" for item in watchlist)
        assert any(item["name"] == "privacy" for item in watchlist)

        # Remove watchlist item
        assert temp_db.remove_watchlist_item(channel_id, "Google") is True

        # Verify removal
        watchlist = temp_db.get_watchlist(channel_id)
        assert len(watchlist) == 2
        assert not any(item["name"] == "Google" for item in watchlist)

    def test_get_watchlist_signals(self, temp_db: Any) -> None:
        """Test getting signals that match watchlist."""
        channel_id = "C1234567890"
        now = datetime.now(timezone.utc)

        # Add to watchlist
        temp_db.add_watchlist_item(channel_id, "Apple")
        temp_db.add_watchlist_item(channel_id, "privacy")

        # Create signals
        signals = [
            SignalV2(
                source="congress",
                stable_id="bill-1",
                title="Apple Privacy Bill",
                summary="A bill about Apple's privacy practices",
                url="https://example.com/bill-1",
                timestamp=now,
                priority_score=5.0,
            ),
            SignalV2(
                source="congress",
                stable_id="bill-2",
                title="Google Data Bill",
                summary="A bill about Google's data practices",
                url="https://example.com/bill-2",
                timestamp=now,
                priority_score=4.0,
            ),
            SignalV2(
                source="congress",
                stable_id="bill-3",
                title="Privacy Protection Act",
                summary="A bill about privacy protection",
                url="https://example.com/bill-3",
                timestamp=now,
                priority_score=6.0,
            ),
        ]

        temp_db.store_signals(signals)

        # Get watchlist signals
        watchlist_signals = temp_db.get_watchlist_signals(channel_id)
        # Apple, privacy, and Google matches (privacy matches both Apple and
        # Google bills)
        assert len(watchlist_signals) == 3
        assert all(s.watchlist_hit for s in watchlist_signals)

    def test_get_docket_surges(self, temp_db: Any) -> None:
        """Test getting docket signals with surge activity."""
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

        temp_db.store_signals(signals)

        # Get docket surges
        surges = temp_db.get_docket_surges(200.0)
        assert len(surges) == 1
        assert surges[0].stable_id == "docket-2"

    def test_get_deadline_signals(self, temp_db: Any) -> None:
        """Test getting signals with deadlines."""
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

        temp_db.store_signals(signals)

        # Get deadline signals
        deadlines = temp_db.get_deadline_signals(7)
        assert len(deadlines) == 1
        assert deadlines[0].stable_id == "bill-2"

    def test_get_industry_signals(self, temp_db: Any) -> None:
        """Test getting signals by industry."""
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="congress",
                stable_id="health-1",
                title="Health Bill 1",
                summary="First health bill",
                url="https://example.com/health-1",
                timestamp=now,
                industry_tag="Health",
                priority_score=5.0,
            ),
            SignalV2(
                source="congress",
                stable_id="health-2",
                title="Health Bill 2",
                summary="Second health bill",
                url="https://example.com/health-2",
                timestamp=now,
                industry_tag="Health",
                priority_score=3.0,
            ),
            SignalV2(
                source="congress",
                stable_id="tech-1",
                title="Tech Bill",
                summary="A tech bill",
                url="https://example.com/tech-1",
                timestamp=now,
                industry_tag="Tech",
                priority_score=4.0,
            ),
        ]

        temp_db.store_signals(signals)

        # Get health industry signals (limit 2)
        health_signals = temp_db.get_industry_signals("Health", 2)
        assert len(health_signals) == 2
        assert all(s.industry_tag == "Health" for s in health_signals)
        # Should be sorted by priority score
        assert health_signals[0].priority_score == 5.0
        assert health_signals[1].priority_score == 3.0

    def test_channel_settings(self, temp_db: Any) -> None:
        """Test channel settings operations."""
        channel_id = "C1234567890"

        # Get default settings
        settings = temp_db.get_channel_settings(channel_id)
        assert settings["channel_id"] == channel_id
        assert settings["mini_digest_threshold"] == 10
        assert settings["high_priority_threshold"] == 5.0
        assert settings["surge_threshold"] == 200.0
        assert settings["show_summaries"] is True

        # Update settings
        assert (
            temp_db.update_channel_setting(channel_id, "mini_digest_threshold", 15)
            is True
        )
        assert (
            temp_db.update_channel_setting(channel_id, "high_priority_threshold", 7.0)
            is True
        )
        assert (
            temp_db.update_channel_setting(channel_id, "show_summaries", False) is True
        )

        # Get updated settings
        settings = temp_db.get_channel_settings(channel_id)
        assert settings["mini_digest_threshold"] == 15
        assert settings["high_priority_threshold"] == 7.0
        # SQLite stores booleans as integers
        assert settings["show_summaries"] == 0

    def test_cleanup_old_signals(self, temp_db: Any) -> None:
        """Test cleaning up old signals."""
        now = datetime.now(timezone.utc)

        # Create old and recent signals
        old_signal = SignalV2(
            source="congress",
            stable_id="old-bill",
            title="Old Bill",
            summary="An old bill",
            url="https://example.com/old-bill",
            timestamp=now - timedelta(days=35),  # 35 days old
            priority_score=3.0,
        )

        recent_signal = SignalV2(
            source="congress",
            stable_id="recent-bill",
            title="Recent Bill",
            summary="A recent bill",
            url="https://example.com/recent-bill",
            timestamp=now - timedelta(days=10),  # 10 days old
            priority_score=5.0,
        )

        temp_db.store_signal(old_signal)
        temp_db.store_signal(recent_signal)

        # Clean up signals older than 30 days
        deleted_count = temp_db.cleanup_old_signals(30)
        assert deleted_count == 1

        # Verify only recent signal remains
        signals = temp_db.get_recent_signals(24)
        assert len(signals) == 0  # Recent signal is older than 24 hours

        # Get all signals
        all_signals = temp_db.get_recent_signals(365)  # Get all signals from last year
        assert len(all_signals) == 1
        assert all_signals[0].stable_id == "recent-bill"

    def test_get_signal_stats(self, temp_db: Any) -> None:
        """Test getting signal statistics."""
        now = datetime.now(timezone.utc)

        # Create test signals
        signals = [
            SignalV2(
                source="congress",
                stable_id="bill-1",
                title="Health Bill",
                summary="A health bill",
                url="https://example.com/bill-1",
                timestamp=now,
                signal_type=SignalType.BILL,
                urgency=Urgency.HIGH,
                priority_score=6.0,
                industry_tag="Health",
                watchlist_hit=True,
            ),
            SignalV2(
                source="federal_register",
                stable_id="fr-1",
                title="Tech Rule",
                summary="A tech rule",
                url="https://example.com/fr-1",
                timestamp=now,
                signal_type=SignalType.FINAL_RULE,
                urgency=Urgency.CRITICAL,
                priority_score=8.0,
                industry_tag="Tech",
                watchlist_hit=False,
            ),
            SignalV2(
                source="regulations_gov",
                stable_id="docket-1",
                title="Env Docket",
                summary="An environment docket",
                url="https://example.com/docket-1",
                timestamp=now,
                signal_type=SignalType.DOCKET,
                urgency=Urgency.MEDIUM,
                priority_score=4.0,
                industry_tag="Environment",
                watchlist_hit=False,
            ),
        ]

        temp_db.store_signals(signals)

        # Get statistics
        stats = temp_db.get_signal_stats()

        assert stats["total_signals"] == 3
        assert stats["by_source"]["congress"] == 1
        assert stats["by_source"]["federal_register"] == 1
        assert stats["by_source"]["regulations_gov"] == 1
        assert stats["by_urgency"]["high"] == 1
        assert stats["by_urgency"]["critical"] == 1
        assert stats["by_urgency"]["medium"] == 1
        assert stats["by_industry"]["Health"] == 1
        assert stats["by_industry"]["Tech"] == 1
        assert stats["by_industry"]["Environment"] == 1
        assert stats["high_priority"] == 2  # Scores >= 5.0
        assert stats["watchlist_hits"] == 1

    def test_signal_serialization_roundtrip(self, temp_db: Any) -> None:
        """Test that signal serialization and deserialization works correctly."""
        now = datetime.now(timezone.utc)
        original_signal = SignalV2(
            source="congress",
            stable_id="bill-123",
            title="Test Bill",
            summary="A test bill with special characters: éñü",
            url="https://example.com/bill-123",
            timestamp=now,
            issue_codes=["HCR", "TEC"],
            bill_id="HR-123",
            action_type="introduced",
            agency="HHS",
            comment_count=100,
            deadline=now + timedelta(days=30),
            metric_json={"comments_24h_delta_pct": 50.0, "nested": {"key": "value"}},
            signal_type=SignalType.BILL,
            urgency=Urgency.HIGH,
            priority_score=7.5,
            industry_tag="Health",
            watchlist_hit=True,
        )

        # Store signal
        temp_db.store_signal(original_signal)

        # Retrieve signal
        retrieved_signals = temp_db.get_recent_signals(24)
        assert len(retrieved_signals) == 1

        retrieved_signal = retrieved_signals[0]

        # Compare all fields
        assert retrieved_signal.source == original_signal.source
        assert retrieved_signal.stable_id == original_signal.stable_id
        assert retrieved_signal.title == original_signal.title
        assert retrieved_signal.summary == original_signal.summary
        assert retrieved_signal.url == original_signal.url
        assert retrieved_signal.timestamp == original_signal.timestamp
        assert retrieved_signal.issue_codes == original_signal.issue_codes
        assert retrieved_signal.bill_id == original_signal.bill_id
        assert retrieved_signal.action_type == original_signal.action_type
        assert retrieved_signal.agency == original_signal.agency
        assert retrieved_signal.comment_count == original_signal.comment_count
        assert retrieved_signal.deadline == original_signal.deadline
        assert retrieved_signal.metric_json == original_signal.metric_json
        assert retrieved_signal.signal_type == original_signal.signal_type
        assert retrieved_signal.urgency == original_signal.urgency
        assert retrieved_signal.priority_score == original_signal.priority_score
        assert retrieved_signal.industry_tag == original_signal.industry_tag
        assert retrieved_signal.watchlist_hit == original_signal.watchlist_hit

    def test_error_handling(self, temp_db: Any) -> None:
        """Test error handling in database operations."""
        # Test storing invalid signal data
        # This should not crash but return False
        result = temp_db.store_signal(None)  # type: ignore
        assert result is False

        # Test getting signals from non-existent channel
        watchlist = temp_db.get_watchlist("nonexistent-channel")
        assert watchlist == []

        # Test removing non-existent watchlist item
        result = temp_db.remove_watchlist_item(
            "nonexistent-channel", "nonexistent-item"
        )
        assert result is True  # Should succeed even if nothing to remove
