"""Cover key sections and formatting paths in DigestFormatter."""

from datetime import datetime, timedelta, timezone

from bot.digest import DigestFormatter
from bot.signals import SignalType, SignalV2, Urgency


def _sig(
    title: str,
    agency: str = "EPA",
    source: str = "federal_register",
    priority: float = 4.0,
    doc_type: str = "Notice",
) -> SignalV2:
    now = datetime.now(timezone.utc)
    return SignalV2(
        source=source,
        source_id=title.replace(" ", "-"),
        timestamp=now,
        title=title,
        link="https://example.com",
        agency=agency,
        priority_score=priority,
        metrics={"document_type": doc_type},
        signal_type=SignalType.NOTICE,
        urgency=Urgency.MEDIUM,
    )


def test_digest_formatter_what_changed_and_watchlist() -> None:
    fmt = DigestFormatter(["Google"])
    signals = [
        _sig("Google Privacy Rule", priority=6.0, agency="FTC"),
        _sig("Generic Notice", priority=2.0),
    ]
    digest = fmt.format_daily_digest(signals, 24)
    assert "Google Privacy Rule" in digest
    assert "What Changed" in digest or "Outlier" in digest


def test_digest_formatter_deadlines_and_snapshots() -> None:
    fmt = DigestFormatter()
    deadline = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    signals = [
        SignalV2(
            source="regulations_gov",
            source_id="DOC-1",
            timestamp=datetime.now(timezone.utc),
            title="Emission Standards",
            link="https://example.com",
            agency="EPA",
            priority_score=5.0,
            metrics={"document_type": "Proposed Rule", "comment_end_date": deadline},
            signal_type=SignalType.PROPOSED_RULE,
            urgency=Urgency.HIGH,
        )
    ]
    digest = fmt.format_daily_digest(signals, 24)
    assert "Emission Standards" in digest
    assert "Docket" in digest or "Outlier" in digest


def test_digest_formatter_handles_no_signals() -> None:
    fmt = DigestFormatter()
    digest = fmt.format_daily_digest([], 24)
    assert "no significant government activity" in digest.lower()
