"""
Tests for digest link rendering with real Slack links.

This module tests that all digest formatters use real URLs with proper
Slack mrkdwn formatting instead of placeholder links.
"""

import os
import sys
from datetime import datetime, timezone

# Add the bot directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.digest import DigestFormatter  # noqa: E402
from bot.signals import SignalType, SignalV2  # noqa: E402


def test_fr_link_rendering() -> None:
    """Test FR link rendering in digest formatter."""
    fmt = DigestFormatter()

    signal = SignalV2(
        source="federal_register",
        source_id="FR-2024-12345",
        timestamp=datetime.now(timezone.utc),
        title="Proposed Rule — Example",
        link="https://www.federalregister.gov/doc/2025-12345",
        agency="EPA",
        issue_codes=["TEC"],
        priority_score=5.0,
        signal_type=SignalType.PROPOSED_RULE,
    )

    line = fmt._format_front_page_signal(signal)
    assert "<https://www.federalregister.gov/doc/2025-12345|FR>" in line
    assert "<FR|View>" not in line  # No placeholder
    print("✅ FR link rendering test passed")


def test_regs_link_rendering() -> None:
    """Test Regulations.gov link rendering in digest formatter."""
    fmt = DigestFormatter()

    signal = SignalV2(
        source="regulations_gov",
        source_id="EPA-HQ-2025-0001",
        timestamp=datetime.now(timezone.utc),
        title="Docket — Example",
        link="https://www.regulations.gov/docket/EPA-HQ-2025-0001",
        agency="EPA",
        docket_id="EPA-HQ-2025-0001",
        issue_codes=["ENV"],
        priority_score=4.0,
        signal_type=SignalType.DOCKET,
    )

    line = fmt._format_front_page_signal(signal)
    assert "<https://www.regulations.gov/docket/EPA-HQ-2025-0001|Docket>" in line
    assert "<Docket|View>" not in line  # No placeholder
    print("✅ Regulations.gov link rendering test passed")


def test_congress_link_rendering() -> None:
    """Test Congress link rendering in digest formatter."""
    fmt = DigestFormatter()

    signal = SignalV2(
        source="congress",
        source_id="HR1234",
        timestamp=datetime.now(timezone.utc),
        title="HR 1234: Example Bill",
        link="https://www.congress.gov/bill/118-congress/house-bill/1234",
        agency="Congress",
        bill_id="HR1234",
        issue_codes=["TEC"],
        priority_score=3.0,
        signal_type=SignalType.BILL,
    )

    line = fmt._format_front_page_signal(signal)
    assert (
        "<https://www.congress.gov/bill/118-congress/house-bill/1234|Congress>" in line
    )
    assert "<Congress|View>" not in line  # No placeholder
    print("✅ Congress link rendering test passed")


def test_no_placeholder_if_missing_url() -> None:
    """Test that no placeholder is shown when URL is missing."""
    fmt = DigestFormatter()

    signal = SignalV2(
        source="federal_register",
        source_id="FR-2024-12345",
        timestamp=datetime.now(timezone.utc),
        title="Notice — No URL",
        link="",  # No URL
        agency="EPA",
        issue_codes=["TEC"],
        priority_score=1.0,
        signal_type=SignalType.NOTICE,
    )

    line = fmt._format_front_page_signal(signal)
    assert "<" not in line  # No fake placeholder
    assert "Notice — No URL" in line
    print("✅ No placeholder for missing URL test passed")


def test_slack_link_helper() -> None:
    """Test the slack_link helper function directly."""
    from bot.utils import slack_link

    # Test with valid URL
    result = slack_link("https://example.com", "Test")
    assert result == "<https://example.com|Test>"

    # Test with empty URL
    result = slack_link("", "Test")
    assert result == ""

    # Test with default label
    result = slack_link("https://example.com")
    assert result == "<https://example.com|Link>"

    print("✅ slack_link helper test passed")


if __name__ == "__main__":
    print("🧪 Testing Digest Link Rendering")
    print("=" * 50)

    test_slack_link_helper()
    test_fr_link_rendering()
    test_regs_link_rendering()
    test_congress_link_rendering()
    test_no_placeholder_if_missing_url()

    print("\n🎉 All digest link tests passed!")
