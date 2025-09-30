"""Integration tests for the V2 daily digest formatter."""

from datetime import datetime, timezone

from bot.digest import DigestFormatter, TITLE_MAX_LEN
from bot.signals import SignalType, SignalV2


def _make_signal(
    *,
    source_id: str,
    title: str,
    source: str = "federal_register",
    signal_type: SignalType,
    priority: float,
    timestamp: datetime,
    link: str,
    agency: str | None = None,
    issue_codes: list[str] | None = None,
) -> SignalV2:
    """Lightweight helper to build SignalV2 instances for tests."""

    return SignalV2(
        source_id=source_id,
        title=title,
        source=source,
        signal_type=signal_type,
        priority_score=priority,
        timestamp=timestamp,
        link=link,
        agency=agency,
        issue_codes=issue_codes or [],
        metrics={"document_type": signal_type.value.replace("_", " ").title()},
    )


def test_daily_digest_includes_faa_bundle_and_counts() -> None:
    """FAA directives bundle together while emergencies stay high impact."""

    now = datetime(2025, 9, 30, 12, 0, tzinfo=timezone.utc)
    signals = [
        _make_signal(
            source_id="rule-1",
            title="Guidance Regarding Certain Matters Relating to Nonrecognition of Gain or Loss in",
            signal_type=SignalType.NOTICE,
            priority=5.5,
            timestamp=now,
            link="https://example.com/guidance",
            agency="IRS",
            issue_codes=["FIN"],
        ),
        _make_signal(
            source_id="faa-emergency",
            title="Airworthiness Directives; Airbus Helicopters (Emergency)",
            signal_type=SignalType.NOTICE,
            priority=5.2,
            timestamp=now,
            link="https://example.com/airbus-emergency",
            agency="Federal Aviation Administration",
            issue_codes=["TRA"],
        ),
        _make_signal(
            source_id="faa-1",
            title="Airworthiness Directives; Boeing 737 MAX",
            signal_type=SignalType.NOTICE,
            priority=2.0,
            timestamp=now,
            link="https://example.com/boeing-ad",
            agency="Federal Aviation Administration",
            issue_codes=["TRA"],
        ),
        _make_signal(
            source_id="faa-2",
            title="Airworthiness Directives; De Havilland Aircraft",
            signal_type=SignalType.NOTICE,
            priority=1.8,
            timestamp=now,
            link="https://example.com/dehavilland-ad",
            agency="Federal Aviation Administration",
            issue_codes=["TRA"],
        ),
        _make_signal(
            source_id="rule-2",
            title="Updating Class I Rail Carrier Reporting Requirements",
            signal_type=SignalType.PROPOSED_RULE,
            priority=5.0,
            timestamp=now,
            link="https://example.com/rail-requirements",
            agency="FRA",
            issue_codes=["TRA"],
        ),
        _make_signal(
            source_id="notice-2",
            title="Preparer Tax Identification Number (PTIN) User Fee Update",
            signal_type=SignalType.NOTICE,
            priority=3.5,
            timestamp=now,
            link="https://example.com/ptin-fee",
            agency="IRS",
            issue_codes=["FIN"],
        ),
    ]

    formatter = DigestFormatter()
    digest = formatter.format_daily_digest(signals)
    lines = digest.splitlines()

    assert lines[0].startswith("LobbyLens — Daily Signals (")
    assert "Mini-stats: Bills 0 | FR 5 | Dockets 0 | High-priority 4" in lines[1]
    assert "What Changed" in lines
    assert "Outlier — High Impact" in lines
    assert "Industry Snapshot" in lines

    assert any(
        "FAA Airworthiness Directives — 2 notices today" in line for line in lines
    ), "Non-emergency FAA directives should collapse into a bundle"

    high_impact_index = lines.index("Outlier — High Impact")
    high_impact_items = []
    for line in lines[high_impact_index + 1 :]:
        if not line.startswith("•"):
            break
        high_impact_items.append(line)

    assert any(
        "Airworthiness Directives; Airbus Helicopters (Emergency)" in line
        for line in high_impact_items
    ), "Emergency FAA AD should stay in High Impact"

    bullet_titles = []
    for line in lines:
        if line.startswith("•"):
            parts = line.split("•")
            if len(parts) > 1:
                title = parts[1].strip()
                if title:
                    bullet_titles.append(title)

    assert all(len(title) <= TITLE_MAX_LEN for title in bullet_titles)

    snapshot_index = lines.index("Industry Snapshot")
    snapshot_lines = lines[snapshot_index + 1 :]
    assert any(
        "Finance: 2 (rules 0, proposed 0, notices 2, dockets 0)" in line
        for line in snapshot_lines
    )
    assert any(
        "Transport: 4 (rules 0, proposed 1, notices 3, dockets 0)" in line
        for line in snapshot_lines
    )
