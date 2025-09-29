"""
Test fixture for FR Daily Digest

Creates ~15 FR documents as specified in the requirements:
- 5 FAA AD notices (Boeing, Airbus, De Havilland...)
- 1 BIS export-controls proposed rule (deadline in 12d)
- 1 CMS final rule (effective in 21d)
- 1 FERC final rule
- 1 FCC proposed rule
- 1 OFAC policy notice (keywords: "enforcement policy")
- 1 CISA meeting (with time)
- 4 generic notices (should be filtered out)
"""

from datetime import datetime, timedelta, timezone
from typing import Dict

from bot.signals import SignalType, SignalV2


def create_test_fixture() -> list[SignalV2]:
    """Create test fixture with ~15 FR documents."""
    now = datetime.now(timezone.utc)

    signals = []

    # 5 FAA AD notices (Boeing, Airbus, De Havilland...)
    faa_ads = [
        {
            "title": "Airworthiness Directives; The Boeing Company Airplanes",
            "agency": "Federal Aviation Administration",
            "doc_type": "Notice",
            "manufacturer": "Boeing",
        },
        {
            "title": "Airworthiness Directives; Airbus SAS Airplanes",
            "agency": "Federal Aviation Administration",
            "doc_type": "Notice",
            "manufacturer": "Airbus",
        },
        {
            "title": (
                "Airworthiness Directives; De Havilland Aircraft of Canada "
                "Limited Airplanes"
            ),
            "agency": "Federal Aviation Administration",
            "doc_type": "Notice",
            "manufacturer": "De Havilland",
        },
        {
            "title": "Airworthiness Directives; Bombardier Inc. Airplanes",
            "agency": "Federal Aviation Administration",
            "doc_type": "Notice",
            "manufacturer": "Bombardier",
        },
        {
            "title": "Airworthiness Directives; Textron Aviation Inc. Airplanes",
            "agency": "Federal Aviation Administration",
            "doc_type": "Notice",
            "manufacturer": "Textron",
        },
    ]

    for i, ad in enumerate(faa_ads):
        signal = SignalV2(
            source="federal_register",
            source_id=f"FAA-2024-{i+1:04d}",
            timestamp=now - timedelta(hours=i),
            title=ad["title"],
            link=(
                f"https://www.federalregister.gov/documents/2024/01/15/"
                f"FAA-2024-{i+1:04d}"
            ),
            agency=ad["agency"],
            industry="Aviation",
            metrics={
                "document_type": ad["doc_type"],
                "manufacturer": ad["manufacturer"],
            },
            priority_score=1.0,  # Will be demoted by -1.5
            signal_type=SignalType.NOTICE,
        )
        signals.append(signal)

    # 1 BIS export-controls proposed rule (deadline in 12d)
    comment_deadline = now + timedelta(days=12)
    bis_signal = SignalV2(
        source="federal_register",
        source_id="BIS-2024-0001",
        timestamp=now - timedelta(hours=2),
        title=("Export Administration Regulations: Revisions to License Exception ENC"),
        link="https://www.federalregister.gov/documents/2024/01/15/BIS-2024-0001",
        agency="Bureau of Industry and Security",
        industry="Trade/Tech",
        metrics={
            "document_type": "Proposed Rule",
            "comment_date": comment_deadline.isoformat(),
        },
        priority_score=3.5,  # Base score
        signal_type=SignalType.PROPOSED_RULE,
    )
    signals.append(bis_signal)

    # 1 CMS final rule (effective in 21d)
    effective_date = now + timedelta(days=21)
    cms_signal = SignalV2(
        source="federal_register",
        source_id="CMS-2024-0001",
        timestamp=now - timedelta(hours=1),
        title=("Medicare Program; Hospital Inpatient Prospective Payment Systems"),
        link="https://www.federalregister.gov/documents/2024/01/15/CMS-2024-0001",
        agency="Centers for Medicare & Medicaid Services",
        industry="Health",
        metrics={
            "document_type": "Final Rule",
            "effective_date": effective_date.isoformat(),
        },
        priority_score=5.0,  # Base score
        signal_type=SignalType.FINAL_RULE,
    )
    signals.append(cms_signal)

    # 1 FERC final rule
    ferc_signal = SignalV2(
        source="federal_register",
        source_id="FERC-2024-0001",
        timestamp=now - timedelta(hours=3),
        title="Electric Transmission Incentives Policy Statement",
        link="https://www.federalregister.gov/documents/2024/01/15/FERC-2024-0001",
        agency="Federal Energy Regulatory Commission",
        industry="Energy",
        metrics={
            "document_type": "Final Rule",
        },
        priority_score=5.0,  # Base score
        signal_type=SignalType.FINAL_RULE,
    )
    signals.append(ferc_signal)

    # 1 FCC proposed rule
    fcc_signal = SignalV2(
        source="federal_register",
        source_id="FCC-2024-0001",
        timestamp=now - timedelta(hours=4),
        title="Spectrum Rules and Policies for the 6 GHz Band",
        link="https://www.federalregister.gov/documents/2024/01/15/FCC-2024-0001",
        agency="Federal Communications Commission",
        industry="Tech/Telecom",
        metrics={
            "document_type": "Proposed Rule",
        },
        priority_score=3.5,  # Base score
        signal_type=SignalType.PROPOSED_RULE,
    )
    signals.append(fcc_signal)

    # 1 OFAC policy notice (keywords: "enforcement policy")
    ofac_signal = SignalV2(
        source="federal_register",
        source_id="OFAC-2024-0001",
        timestamp=now - timedelta(hours=5),
        title="Enforcement Policy for Sanctions Violations",
        link="https://www.federalregister.gov/documents/2024/01/15/OFAC-2024-0001",
        agency="Office of Foreign Assets Control",
        industry="Finance",
        metrics={
            "document_type": "Notice",
        },
        priority_score=1.0,  # Base score
        signal_type=SignalType.NOTICE,
    )
    signals.append(ofac_signal)

    # 1 CISA meeting (with time)
    cisa_signal = SignalV2(
        source="federal_register",
        source_id="CISA-2024-0001",
        timestamp=now - timedelta(hours=6),
        title=(
            "Cybersecurity and Infrastructure Security Agency Advisory "
            "Committee Meeting"
        ),
        link="https://www.federalregister.gov/documents/2024/01/15/CISA-2024-0001",
        agency="Cybersecurity and Infrastructure Security Agency",
        industry="Cyber",
        metrics={
            "document_type": "Meeting",
            "meeting_time": "2:00 PM EST",
        },
        priority_score=3.0,  # Base score
        signal_type=SignalType.HEARING,
    )
    signals.append(cisa_signal)

    # 4 generic notices (should be filtered out)
    generic_notices = [
        {
            "title": (
                "Agency Information Collection Activities; Submission for OMB Review"
            ),
            "agency": "Department of Agriculture",
        },
        {
            "title": "Notice of Public Meeting",
            "agency": "Department of Transportation",
        },
        {
            "title": ("Agency Information Collection Activities; Proposed Collection"),
            "agency": "Department of Education",
        },
        {
            "title": "Notice of Availability of Environmental Assessment",
            "agency": "Department of the Interior",
        },
    ]

    for i, notice in enumerate(generic_notices):
        signal = SignalV2(
            source="federal_register",
            source_id=f"GEN-2024-{i+1:04d}",
            timestamp=now - timedelta(hours=7 + i),
            title=notice["title"],
            link=(
                f"https://www.federalregister.gov/documents/2024/01/15/"
                f"GEN-2024-{i+1:04d}"
            ),
            agency=notice["agency"],
            industry="Other",
            metrics={
                "document_type": "Notice",
            },
            priority_score=1.0,  # Base score
            signal_type=SignalType.NOTICE,
        )
        signals.append(signal)

    return signals


if __name__ == "__main__":
    # Test the fixture
    signals = create_test_fixture()
    print(f"Created {len(signals)} test signals")

    # Print summary
    agencies: Dict[str, int] = {}
    doc_types: Dict[str, int] = {}
    for signal in signals:
        agency = signal.agency or "Unknown"
        agencies[agency] = agencies.get(agency, 0) + 1

        doc_type = signal.metrics.get("document_type", "Unknown")
        doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

    print("\nAgencies:")
    for agency, count in agencies.items():
        print(f"  {agency}: {count}")

    print("\nDocument Types:")
    for doc_type, count in doc_types.items():
        print(f"  {doc_type}: {count}")
