"""Basic digest formatter coverage for small inputs."""

from datetime import datetime, timezone

from bot.digest import DigestFormatter
from bot.signals import SignalV2


def test_digest_formatter_handles_minimal_signal() -> None:
    fmt = DigestFormatter()
    now = datetime.now(timezone.utc)
    signals = [
        SignalV2(
            source="federal_register",
            source_id="FR-1",
            timestamp=now,
            title="Test Notice",
            link="https://example.com",
            agency="EPA",
            priority_score=4.0,
        )
    ]
    digest = fmt.format_daily_digest(signals, 24)
    assert "Test Notice" in digest
    # Agency information is included in the mini digest format but not in the
    # main "What Changed" section format. Verify the signal is present.
    assert "FR" in digest  # Link label for federal_register signals
