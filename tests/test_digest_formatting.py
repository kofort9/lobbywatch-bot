"""Advanced formatting tests for DigestFormatter bundling and budgets."""

from datetime import datetime, timedelta, timezone

from bot.digest import FRONT_BUDGET_TOTAL, DigestFormatter
from bot.signals import SignalType, SignalV2


def _make_signal(**kwargs: object) -> SignalV2:
    now = kwargs.pop("timestamp", datetime.now(timezone.utc))
    signal = SignalV2(
        source=kwargs.pop("source", "federal_register"),
        source_id=kwargs.pop("source_id"),
        timestamp=now,
        title=kwargs.pop("title"),
        link=kwargs.pop("link"),
        priority_score=kwargs.pop("priority_score", 1.0),
        issue_codes=kwargs.pop("issue_codes", []),
        agency=kwargs.pop("agency", None),
        docket_id=kwargs.pop("docket_id", None),
        bill_id=kwargs.pop("bill_id", None),
        committee=kwargs.pop("committee", None),
        comment_end_date=kwargs.pop("comment_end_date", None),
        comments_24h=kwargs.pop("comments_24h", None),
        comments_delta=kwargs.pop("comments_delta", None),
        comment_surge=kwargs.pop("comment_surge", False),
        signal_type=kwargs.pop("signal_type", None),
    )
    metrics = kwargs.pop("metrics", {})
    if signal.comment_end_date and "comment_end_date" not in metrics:
        metrics["comment_end_date"] = signal.comment_end_date
    if signal.comments_24h and "comments_24h" not in metrics:
        metrics["comments_24h"] = signal.comments_24h
    if signal.comments_delta and "comments_delta" not in metrics:
        metrics["comments_delta"] = signal.comments_delta
    if signal.comment_surge and "comment_surge" not in metrics:
        metrics["comment_surge"] = signal.comment_surge
    signal.metrics.update(metrics)
    return signal


def test_digest_bundles_and_congress_section() -> None:
    formatter = DigestFormatter()
    now = datetime(2025, 10, 1, 15, tzinfo=timezone.utc)

    signals: list[SignalV2] = []

    # Proposed rule closing soon (promoted to What Changed)
    signals.append(
        _make_signal(
            source="federal_register",
            source_id="fr-1",
            timestamp=now,
            title="Proposed Rule: Export Controls on Advanced AI Systems",
            link="https://example.com/fr-1",
            priority_score=4.0,
            issue_codes=["TEC"],
            agency="Department of Commerce",
            comment_end_date=(now + timedelta(days=7)).isoformat(),
            metrics={"document_type": "Proposed Rule"},
        )
    )

    # Final rule high impact
    signals.append(
        _make_signal(
            source="federal_register",
            source_id="fr-2",
            timestamp=now,
            title="Final Rule: Medicare Advantage Risk Adjustment Update",
            link="https://example.com/fr-2",
            priority_score=5.5,
            issue_codes=["HCR"],
            agency="Centers for Medicare & Medicaid Services",
            metrics={"document_type": "Final Rule"},
        )
    )

    # FAA emergency AD (should appear individually in High Impact)
    signals.append(
        _make_signal(
            source="federal_register",
            source_id="faa-1",
            timestamp=now,
            title="Airworthiness Directives; Boeing Model 777 Airplanes — Emergency Inspection",
            link="https://example.com/faa-1",
            priority_score=5.5,
            agency="Federal Aviation Administration",
            issue_codes=["TRA"],
        )
    )

    # Non-emergency FAA ADs (bundled)
    for idx, manufacturer in enumerate(
        ["Airbus", "Textron", "De Havilland", "Embraer", "Sikorsky"], start=2
    ):
        signals.append(
            _make_signal(
                source="federal_register",
                source_id=f"faa-{idx}",
                timestamp=now - timedelta(minutes=idx),
                title=f"Airworthiness Directives; {manufacturer} Aircraft Fleet Inspection",
                link=f"https://example.com/faa-{idx}",
                priority_score=2.0,
                agency="Federal Aviation Administration",
                issue_codes=["TRA"],
            )
        )

    # SEC SRO filings (bundled)
    sro_titles = [
        "Self-Regulatory Organizations; NASDAQ; Immediate Effectiveness",
        "Self-Regulatory Organizations; NYSE Arca; Proposed Rule Change",
        "Self-Regulatory Organizations; CBOE; Fee Schedule",
        "Self-Regulatory Organizations; FINRA; Trade Reporting",
        "Self-Regulatory Organizations; MIAX; Market Data",
    ]
    for idx, title in enumerate(sro_titles, start=1):
        signals.append(
            _make_signal(
                source="federal_register",
                source_id=f"sec-{idx}",
                timestamp=now - timedelta(hours=idx),
                title=title,
                link=f"https://example.com/sec-{idx}",
                priority_score=2.0,
                agency="Securities and Exchange Commission",
                issue_codes=["FIN"],
                metrics={"document_type": "Notice"},
            )
        )

    # IRS routine notices (bundled)
    for idx in range(1, 5):
        signals.append(
            _make_signal(
                source="federal_register",
                source_id=f"irs-{idx}",
                timestamp=now - timedelta(hours=idx + 5),
                title=f"Revenue Procedure 2025-0{idx}: Paperwork Reduction Act Notice",
                link=f"https://example.com/irs-{idx}",
                priority_score=1.5,
                agency="Internal Revenue Service",
                issue_codes=["FIN"],
                metrics={"document_type": "Notice"},
            )
        )

    # EPA administrative notices (bundled)
    for idx in range(1, 4):
        signals.append(
            _make_signal(
                source="federal_register",
                source_id=f"epa-{idx}",
                timestamp=now - timedelta(hours=idx + 8),
                title=f"EPA Administrative Notice Region {idx}",
                link=f"https://example.com/epa-{idx}",
                priority_score=1.2,
                agency="Environmental Protection Agency",
                issue_codes=["ENV"],
                metrics={"document_type": "Notice"},
            )
        )

    # Congress hearings (3 House, 1 Senate)
    hearing_base = now + timedelta(hours=5)
    house_committees = [
        "House Committee on Energy and Commerce",
        "House Committee on Judiciary",
        "House Committee on Ways and Means",
    ]
    for idx, committee in enumerate(house_committees, start=1):
        signals.append(
            _make_signal(
                source="congress",
                source_id=f"house-hearing-{idx}",
                timestamp=now - timedelta(hours=idx),
                title=f"Oversight Hearing on Topic {idx}",
                link=f"https://example.com/house-hearing-{idx}",
                priority_score=2.5,
                committee=committee,
                signal_type=SignalType.HEARING,
                metrics={
                    "chamber": "House",
                    "start_datetime": (hearing_base + timedelta(hours=idx)).isoformat(),
                },
            )
        )

    signals.append(
        _make_signal(
            source="congress",
            source_id="senate-hearing-1",
            timestamp=now - timedelta(hours=2),
            title="Markup on Spectrum Reauthorization",
            link="https://example.com/senate-hearing-1",
            priority_score=2.5,
            committee="Senate Committee on Commerce, Science, and Transportation",
            signal_type=SignalType.MARKUP,
            metrics={
                "chamber": "Senate",
                "start_datetime": (hearing_base + timedelta(hours=4)).isoformat(),
            },
        )
    )

    digest = formatter.format_daily_digest(signals)

    # FAA bundling
    assert "FAA Airworthiness Directives —" in digest
    assert (
        digest.count("Airworthiness Directives; Boeing Model 777 Airplanes — Emergency")
        == 1
    )
    for manufacturer in ["Airbus", "Textron", "De Havilland", "Embraer", "Sikorsky"]:
        assert f"• Airworthiness Directives; {manufacturer}" not in digest

    # Other bundles
    assert "SEC SRO filings —" in digest
    assert "IRS routine notices —" in digest
    assert "EPA administrative notices —" in digest

    # Congress section with bundle line
    assert "*Congress Committees*" in digest
    assert "House — +" in digest
    assert "Mini-stats: Bills" in digest and "Hearings" in digest

    # Ensure total bullet lines within budget
    bullet_lines = [line for line in digest.splitlines() if line.startswith("• ")]
    assert len(bullet_lines) <= FRONT_BUDGET_TOTAL

    # Emergency AD only once
    assert digest.count("Boeing Model 777 Airplanes — Emergency") == 1
