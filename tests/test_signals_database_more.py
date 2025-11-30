"""Additional coverage for SignalsDatabaseV2 helpers."""

import tempfile
from datetime import datetime, timedelta, timezone

from bot.signals import SignalV2
from bot.signals_database import SignalsDatabaseV2


def test_cleanup_old_signals_removes_stale_rows() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db = SignalsDatabaseV2(db_path=tmp.name)
        old = SignalV2(
            source="congress",
            source_id="old",
            timestamp=datetime.now(timezone.utc) - timedelta(days=40),
            title="Old",
            link="https://example.com/old",
            priority_score=1.0,
        )
        recent = SignalV2(
            source="congress",
            source_id="new",
            timestamp=datetime.now(timezone.utc),
            title="New",
            link="https://example.com/new",
            priority_score=1.0,
        )
        db.save_signals([old, recent])
        deleted = db.cleanup_old_signals(days_to_keep=30)
        assert deleted >= 1
        remaining = db.get_recent_signals(1000)
        ids = {s.source_id for s in remaining}
        assert "new" in ids and "old" not in ids


def test_get_signals_by_source_and_issue() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db = SignalsDatabaseV2(db_path=tmp.name)
        now = datetime.now(timezone.utc)
        sig = SignalV2(
            source="regulations_gov",
            source_id="DOC1",
            timestamp=now,
            title="Tech Rule",
            link="https://example.com/doc1",
            issue_codes=["TEC"],
            priority_score=3.0,
        )
        db.save_signals([sig])
        by_source = db.get_signals_by_source("regulations_gov", 24)
        assert len(by_source) == 1
        by_issue = db.get_signals_by_issue_codes(["TEC"], 24)
        assert len(by_issue) == 1
