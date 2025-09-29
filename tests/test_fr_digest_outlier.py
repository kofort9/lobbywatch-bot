"""
Tests for FR Digest Outlier functionality.

This module tests the outlier section logic and formatting
in the FR Daily Digest implementation.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

# Add the bot directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.fr_digest import FRDigestFormatter  # noqa: E402, C0413
from bot.signals import SignalType, SignalV2  # noqa: E402, C0413


def test_outlier_formatting() -> None:
    """Test outlier item formatting with proper structure."""
    fmt = FRDigestFormatter()

    # Create a test signal for outlier
    signal = SignalV2(
        source="federal_register",
        source_id="OUTLIER-TEST-001",
        timestamp=datetime.now(timezone.utc),
        title="Test Outlier Signal",
        link="https://www.federalregister.gov/documents/2024/01/15/OUTLIER-TEST-001",
        agency="Department of Education",
        industry="Education",
        metrics={
            "document_type": "Final Rule",
        },
        signal_type=SignalType.FINAL_RULE,
    )

    # Test formatting
    formatted = fmt._format_outlier_item(signal)

    # Should include industry tag, document type, title, why-matters, and link
    assert "[Education]" in formatted
    assert "Final Rule" in formatted
    assert "Test Outlier Signal" in formatted
    assert "Regulatory action" in formatted  # why-matters clause
    assert (
        "<https://www.federalregister.gov/documents/2024/01/15/OUTLIER-TEST-001|FR>"
        in formatted
    )

    # Test without URL
    signal_no_url = SignalV2(
        source="federal_register",
        source_id="OUTLIER-TEST-002",
        timestamp=datetime.now(timezone.utc),
        title="Test Outlier No URL",
        link="",  # No URL
        agency="Department of Education",
        industry="Education",
        metrics={
            "document_type": "Notice",
        },
        signal_type=SignalType.NOTICE,
    )

    formatted_no_url = fmt._format_outlier_item(signal_no_url)
    assert "[Education]" in formatted_no_url
    assert "Notice" in formatted_no_url
    assert "Test Outlier No URL" in formatted_no_url
    assert "<" not in formatted_no_url  # No link should be present


def test_outlier_selection_logic() -> None:
    """Test that outlier selection works correctly."""
    fmt = FRDigestFormatter()

    # Create test signals
    now = datetime.now(timezone.utc)

    # High-scoring signals that should be in "What Changed"
    high_signals = [
        SignalV2(
            source="federal_register",
            source_id="HIGH-001",
            timestamp=now,
            title="High Priority Signal 1",
            link="https://example.com/high1",
            agency="EPA",
            industry="Environment",
            metrics={"document_type": "Final Rule"},
            signal_type=SignalType.FINAL_RULE,
        ),
        SignalV2(
            source="federal_register",
            source_id="HIGH-002",
            timestamp=now,
            title="High Priority Signal 2",
            link="https://example.com/high2",
            agency="EPA",
            industry="Environment",
            metrics={"document_type": "Final Rule"},
            signal_type=SignalType.FINAL_RULE,
        ),
    ]

    # Medium-scoring signal that should be outlier
    outlier_signal = SignalV2(
        source="federal_register",
        source_id="OUTLIER-001",
        timestamp=now,
        title="Medium Priority Outlier",
        link="https://example.com/outlier",
        agency="Department of Education",
        industry="Education",
        metrics={"document_type": "Notice"},
        signal_type=SignalType.NOTICE,
    )

    # Low-scoring signals that should be filtered out
    low_signals = [
        SignalV2(
            source="federal_register",
            source_id="LOW-001",
            timestamp=now,
            title="Low Priority Signal",
            link="https://example.com/low1",
            agency="Department of Education",
            industry="Education",
            metrics={"document_type": "Notice"},
            signal_type=SignalType.NOTICE,
        ),
    ]

    all_signals = high_signals + [outlier_signal] + low_signals

    # Test outlier selection
    selected_outlier = fmt._get_outlier(all_signals, high_signals)

    # Should select the medium-scoring signal
    assert selected_outlier is not None
    assert selected_outlier.source_id == "OUTLIER-001"
    assert selected_outlier.title == "Medium Priority Outlier"


def test_no_outlier_when_all_included() -> None:
    """Test that no outlier is selected when all high-scoring signals are included."""
    fmt = FRDigestFormatter()

    # Create signals where all high-scoring ones are in what_changed
    signals = [
        SignalV2(
            source="federal_register",
            source_id="HIGH-001",
            timestamp=datetime.now(timezone.utc),
            title="High Priority Signal",
            link="https://example.com/high1",
            agency="EPA",
            industry="Environment",
            metrics={"document_type": "Final Rule"},
            signal_type=SignalType.FINAL_RULE,
        ),
    ]

    what_changed = signals  # All signals are in what_changed

    # Test outlier selection
    selected_outlier = fmt._get_outlier(signals, what_changed)

    # Should return None since all high-scoring signals are already included
    assert selected_outlier is None


def test_outlier_excludes_faa_bundles() -> None:
    """Test that outlier selection excludes FAA bundled signals."""
    fmt = FRDigestFormatter()

    now = datetime.now(timezone.utc)

    signals = [
        SignalV2(
            source="federal_register",
            source_id="faa_ads_bundle_001",  # FAA bundle ID
            timestamp=now,
            title="FAA Airworthiness Directives Bundle",
            link="https://example.com/faa",
            agency="Federal Aviation Administration",
            industry="Aviation",
            metrics={"document_type": "Notice"},
            signal_type=SignalType.NOTICE,
        ),
        SignalV2(
            source="federal_register",
            source_id="OUTLIER-001",
            timestamp=now,
            title="Regular Outlier Signal",
            link="https://example.com/outlier",
            agency="Department of Education",
            industry="Education",
            metrics={"document_type": "Notice"},
            signal_type=SignalType.NOTICE,
        ),
    ]

    what_changed = []  # No signals in what_changed

    # Test outlier selection
    selected_outlier = fmt._get_outlier(signals, what_changed)

    # Should select the regular signal, not the FAA bundle
    assert selected_outlier is not None
    assert selected_outlier.source_id == "OUTLIER-001"
    assert not selected_outlier.source_id.startswith("faa_ads_bundle_")


def test_outlier_with_long_title() -> None:
    """Test outlier formatting with long title that gets truncated."""
    fmt = FRDigestFormatter()

    # Create signal with very long title
    long_title = (
        "This is a very long title that should be truncated because it exceeds "
        "the 80 character limit for proper formatting"
    )

    signal = SignalV2(
        source="federal_register",
        source_id="LONG-TITLE-001",
        timestamp=datetime.now(timezone.utc),
        title=long_title,
        link="https://www.federalregister.gov/documents/2024/01/15/LONG-TITLE-001",
        agency="Department of Education",
        industry="Education",
        metrics={"document_type": "Final Rule"},
        signal_type=SignalType.FINAL_RULE,
    )

    # Test formatting
    formatted = fmt._format_outlier_item(signal)

    # Should be truncated with ellipsis
    assert len(formatted) < len(long_title) + 100  # Much shorter than original
    assert "..." in formatted
    assert (
        "This is a very long title that should be truncated because it exceeds"
        in formatted
    )


def test_outlier_why_matters_clauses() -> None:
    """Test that outlier formatting includes proper why-matters clauses."""
    fmt = FRDigestFormatter()

    now = datetime.now(timezone.utc)

    # Test with effective date
    effective_signal = SignalV2(
        source="federal_register",
        source_id="EFFECTIVE-001",
        timestamp=now,
        title="Signal with Effective Date",
        link="https://example.com/effective",
        agency="EPA",
        industry="Environment",
        metrics={
            "document_type": "Final Rule",
            "effective_date": (now + timedelta(days=30)).isoformat(),
        },
        signal_type=SignalType.FINAL_RULE,
    )

    formatted = fmt._format_outlier_item(effective_signal)
    assert "Effective" in formatted

    # Test with comment deadline
    comment_signal = SignalV2(
        source="federal_register",
        source_id="COMMENT-001",
        timestamp=now,
        title="Signal with Comment Deadline",
        link="https://example.com/comment",
        agency="EPA",
        industry="Environment",
        metrics={
            "document_type": "Proposed Rule",
            "comment_date": (now + timedelta(days=15)).isoformat(),
        },
        signal_type=SignalType.PROPOSED_RULE,
    )

    formatted = fmt._format_outlier_item(comment_signal)
    assert "Comments close" in formatted

    # Test with high-signal keywords
    keyword_signal = SignalV2(
        source="federal_register",
        source_id="KEYWORD-001",
        timestamp=now,
        title="Signal with Enforcement Policy Keywords",
        link="https://example.com/keyword",
        agency="Department of Education",
        industry="Education",
        metrics={"document_type": "Notice"},
        signal_type=SignalType.NOTICE,
    )

    formatted = fmt._format_outlier_item(keyword_signal)
    assert "Enforcement" in formatted


if __name__ == "__main__":
    print("🧪 Testing FR Digest Outlier Functionality")
    print("=" * 50)

    test_outlier_formatting()
    print("✅ Outlier formatting test passed")

    test_outlier_selection_logic()
    print("✅ Outlier selection logic test passed")

    test_no_outlier_when_all_included()
    print("✅ No outlier when all included test passed")

    test_outlier_excludes_faa_bundles()
    print("✅ Outlier excludes FAA bundles test passed")

    test_outlier_with_long_title()
    print("✅ Outlier with long title test passed")

    test_outlier_why_matters_clauses()
    print("✅ Outlier why-matters clauses test passed")

    print("\n🎉 All FR digest outlier tests passed!")
