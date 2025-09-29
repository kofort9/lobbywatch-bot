"""
Tests for the slack_link helper function.

This module tests the slack_link utility function that creates
proper Slack mrkdwn formatted links.
"""

import os
import sys

# Add the bot directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.utils import slack_link  # noqa: E402


def test_slack_link_with_valid_url() -> None:
    """Test slack_link with valid URL and custom label."""
    result = slack_link("https://example.com", "Test")
    assert result == "<https://example.com|Test>"


def test_slack_link_with_default_label() -> None:
    """Test slack_link with valid URL and default label."""
    result = slack_link("https://example.com")
    assert result == "<https://example.com|Link>"


def test_slack_link_with_empty_string() -> None:
    """Test slack_link with empty string URL."""
    result = slack_link("", "Test")
    assert result == ""


def test_slack_link_with_none_url() -> None:
    """Test slack_link with None URL."""
    result = slack_link(None, "Test")
    assert result == ""


def test_slack_link_with_whitespace_url() -> None:
    """Test slack_link with whitespace-only URL."""
    result = slack_link("   ", "Test")
    assert result == ""


def test_slack_link_with_federal_register_url() -> None:
    """Test slack_link with Federal Register URL."""
    url = "https://www.federalregister.gov/documents/2024/01/15/2024-12345"
    result = slack_link(url, "FR")
    assert result == f"<{url}|FR>"


def test_slack_link_with_regulations_gov_url() -> None:
    """Test slack_link with Regulations.gov URL."""
    url = "https://www.regulations.gov/docket/EPA-HQ-2025-0001"
    result = slack_link(url, "Docket")
    assert result == f"<{url}|Docket>"


def test_slack_link_with_congress_url() -> None:
    """Test slack_link with Congress URL."""
    url = "https://www.congress.gov/bill/118-congress/house-bill/1234"
    result = slack_link(url, "Congress")
    assert result == f"<{url}|Congress>"


def test_slack_link_with_special_characters() -> None:
    """Test slack_link with URL containing special characters."""
    url = "https://example.com/path?param=value&other=test#fragment"
    result = slack_link(url, "Special")
    assert result == f"<{url}|Special>"


def test_slack_link_with_unicode_label() -> None:
    """Test slack_link with Unicode characters in label."""
    url = "https://example.com"
    result = slack_link(url, "🔗 Link")
    assert result == "<https://example.com|🔗 Link>"


if __name__ == "__main__":
    print("🧪 Testing slack_link Helper Function")
    print("=" * 50)

    test_slack_link_with_valid_url()
    print("✅ Valid URL test passed")

    test_slack_link_with_default_label()
    print("✅ Default label test passed")

    test_slack_link_with_empty_string()
    print("✅ Empty string test passed")

    test_slack_link_with_none_url()
    print("✅ None URL test passed")

    test_slack_link_with_whitespace_url()
    print("✅ Whitespace URL test passed")

    test_slack_link_with_federal_register_url()
    print("✅ Federal Register URL test passed")

    test_slack_link_with_regulations_gov_url()
    print("✅ Regulations.gov URL test passed")

    test_slack_link_with_congress_url()
    print("✅ Congress URL test passed")

    test_slack_link_with_special_characters()
    print("✅ Special characters test passed")

    test_slack_link_with_unicode_label()
    print("✅ Unicode label test passed")

    print("\n🎉 All slack_link helper tests passed!")
