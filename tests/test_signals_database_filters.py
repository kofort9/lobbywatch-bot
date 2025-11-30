"""Additional tests for SignalsDatabaseV2 filtering."""

import tempfile
from datetime import datetime, timezone

from bot.signals import SignalV2
from bot.signals_database import SignalsDatabaseV2


def test_recent_signals_min_priority() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db = SignalsDatabaseV2(db_path=tmp.name)
        now = datetime.now(timezone.utc)
        signals = [
            SignalV2(
                source="congress",
                source_id="low",
                timestamp=now,
                title="Low",
                link="https://example.com/low",
                priority_score=1.0,
            ),
            SignalV2(
                source="congress",
                source_id="high",
                timestamp=now,
                title="High",
                link="https://example.com/high",
                priority_score=5.0,
            ),
        ]
        db.save_signals(signals)
        filtered = db.get_recent_signals(24, min_priority=3.0)
        assert len(filtered) == 1
        assert filtered[0].priority_score >= 3.0


def test_health_check_ok() -> None:
    db = SignalsDatabaseV2(":memory:")
    status = db.health_check()
    assert status["database"] == "ok"
