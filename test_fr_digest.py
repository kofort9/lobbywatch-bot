"""
Test script for FR Daily Digest implementation

Tests the new FR digest formatter with the test fixture.
"""

import os
import sys

# Add the bot directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "bot"))

# Import after path modification
from fr_digest import FRDigestFormatter  # noqa: E402
from test_fr_digest_fixture import create_test_fixture  # noqa: E402


def test_fr_digest() -> None:
    """Test the FR digest formatter."""
    print("🧪 Testing FR Daily Digest Implementation")
    print("=" * 50)

    # Create test fixture
    signals = create_test_fixture()
    print(f"📊 Created {len(signals)} test signals")

    # Create formatter
    formatter = FRDigestFormatter()

    # Generate digest
    digest = formatter.format_daily_digest(signals)

    print("\n📋 Generated Digest:")
    print("-" * 50)
    print(digest)
    print("-" * 50)

    # Verify requirements
    print("\n✅ Verification:")

    # Check for real links (no placeholders)
    if "<FR|View>" in digest or "<FR|link>" in digest:
        print("❌ Found placeholder links - should be real URLs")
    else:
        print("✅ All links are real URLs (no placeholders)")

    # Check for FAA bundling
    if "FAA Airworthiness Directives —" in digest and "notices today" in digest:
        print("✅ FAA ADs are bundled")
    else:
        print("❌ FAA ADs not properly bundled")

    # Check for industry tags
    industry_tags = [
        "[Aviation]",
        "[Health]",
        "[Energy]",
        "[Tech/Telecom]",
        "[Finance]",
        "[Cyber]",
    ]
    found_tags = [tag for tag in industry_tags if tag in digest]
    if found_tags:
        print(f"✅ Found industry tags: {', '.join(found_tags)}")
    else:
        print("❌ No industry tags found")

    # Check for why-it-matters clauses
    why_matters_indicators = [
        "Effective",
        "Comments close",
        "Emergency",
        "Immediate",
        "Enforcement",
    ]
    found_indicators = [
        indicator for indicator in why_matters_indicators if indicator in digest
    ]
    if found_indicators:
        print(f"✅ Found why-it-matters clauses: {', '.join(found_indicators)}")
    else:
        print("❌ No why-it-matters clauses found")

    # Check section structure
    sections = [
        "What Changed",
        "Industry Snapshot",
        "FAA Airworthiness Directives",
        "Outlier",
    ]
    found_sections = [section for section in sections if section in digest]
    if found_sections:
        print(f"✅ Found sections: {', '.join(found_sections)}")
    else:
        print("❌ Missing expected sections")

    # Check mini-stats
    if "Mini-stats:" in digest and "Final" in digest and "Proposed" in digest:
        print("✅ Mini-stats present")
    else:
        print("❌ Mini-stats missing")

    print("\n🎯 Expected Results:")
    print("- FAA bundled line with 5 notices")
    print("- What Changed includes BIS, CMS, FERC, FCC, OFAC, CISA")
    print(
        "- Industry Snapshot shows Tech/Trade, Health, Energy, Telecom, Finance, Cyber"
    )
    print("- Outlier picks highest-scored remaining item")
    print("- All links are real URLs")
    print("- No generic notices (filtered out)")


if __name__ == "__main__":
    test_fr_digest()
