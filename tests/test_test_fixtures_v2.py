"""
Tests for bot/test_fixtures_v2.py
"""

import pytest
from datetime import datetime, timedelta, timezone

from bot.test_fixtures_v2 import TestFixturesV2, TestValidator
from bot.signals_v2 import SignalV2, SignalType, Urgency


class TestTestFixturesV2:
    """Test TestFixturesV2 class"""

    def test_get_fixture_a_mixed_day(self):
        """Test fixture A - mixed day scenario"""
        signals = TestFixturesV2.get_fixture_a_mixed_day()

        assert len(signals) == 7

        # Check signal types and sources
        sources = [s.source for s in signals]
        assert "federal_register" in sources
        assert "congress" in sources
        assert "regulations_gov" in sources

        # Check specific signals
        fr_signals = [s for s in signals if s.source == "federal_register"]
        assert len(fr_signals) == 3

        congress_signals = [s for s in signals if s.source == "congress"]
        assert len(congress_signals) == 3

        reg_gov_signals = [s for s in signals if s.source == "regulations_gov"]
        assert len(reg_gov_signals) == 1

        # Check issue codes
        issue_codes = set()
        for signal in signals:
            issue_codes.update(signal.issue_codes)
        assert "ENE" in issue_codes
        assert "TEC" in issue_codes
        assert "HCR" in issue_codes
        assert "ENV" in issue_codes
        assert "FIN" in issue_codes

    def test_get_fixture_b_watchlist_hit(self):
        """Test fixture B - watchlist hit scenario"""
        signals = TestFixturesV2.get_fixture_b_watchlist_hit()

        assert len(signals) == 1

        signal = signals[0]
        assert signal.source == "federal_register"
        assert "Google" in signal.title
        assert signal.watchlist_hit is True
        assert signal.issue_codes == ["TEC"]

    def test_get_fixture_c_mini_digest_threshold(self):
        """Test fixture C - mini digest threshold scenario"""
        signals = TestFixturesV2.get_fixture_c_mini_digest_threshold()

        assert len(signals) == 12

        # Check that we have the right number of signals
        sources = [s.source for s in signals]
        congress_count = sources.count("congress")
        fr_count = sources.count("federal_register")

        assert congress_count == 4  # Every 3rd signal
        assert fr_count == 8  # The rest

        # Check priority scores
        priority_scores = [s.priority_score for s in signals]
        assert 6.0 in priority_scores  # One high-priority signal
        assert 2.0 in priority_scores  # Others are low-priority

        # Check issue codes
        issue_codes = set()
        for signal in signals:
            issue_codes.update(signal.issue_codes)
        assert "TEC" in issue_codes
        assert "HCR" in issue_codes

    def test_get_fixture_d_character_budget_stress(self):
        """Test fixture D - character budget stress test"""
        signals = TestFixturesV2.get_fixture_d_character_budget_stress()

        assert len(signals) == 45

        # Check sources distribution
        sources = [s.source for s in signals]
        congress_count = sources.count("congress")
        fr_count = sources.count("federal_register")
        reg_gov_count = sources.count("regulations_gov")

        assert congress_count == 12  # Every 4th signal
        assert fr_count == 11  # Every 4th + 1 signal
        assert reg_gov_count == 22  # The rest

        # Check that titles are long (stress test)
        long_titles = [s for s in signals if len(s.title) > 50]
        assert len(long_titles) == 45  # All titles should be long

        # Check issue codes variety
        issue_codes = set()
        for signal in signals:
            issue_codes.update(signal.issue_codes)
        assert "TEC" in issue_codes
        assert "HCR" in issue_codes
        assert "ENV" in issue_codes
        assert "FIN" in issue_codes
        assert "ENE" in issue_codes

    def test_get_fixture_e_timezone_test(self):
        """Test fixture E - timezone handling test"""
        signals = TestFixturesV2.get_fixture_e_timezone_test()

        assert len(signals) == 1

        signal = signals[0]
        assert signal.source == "federal_register"
        assert signal.stable_id == "TZ-TEST-001"
        assert signal.title == "Timezone Test Signal"
        assert signal.issue_codes == ["TEC"]

        # Check that deadline is in the future
        now = datetime.now(timezone.utc)
        assert signal.deadline > now

    def test_fixture_timestamps(self):
        """Test that all fixtures have proper timestamps"""
        fixtures = [
            TestFixturesV2.get_fixture_a_mixed_day(),
            TestFixturesV2.get_fixture_b_watchlist_hit(),
            TestFixturesV2.get_fixture_c_mini_digest_threshold(),
            TestFixturesV2.get_fixture_d_character_budget_stress(),
            TestFixturesV2.get_fixture_e_timezone_test(),
        ]

        for signals in fixtures:
            for signal in signals:
                assert isinstance(signal.timestamp, datetime)
                assert signal.timestamp.tzinfo is not None
                assert signal.timestamp.tzinfo == timezone.utc

    def test_fixture_urls(self):
        """Test that all fixtures have proper URLs"""
        fixtures = [
            TestFixturesV2.get_fixture_a_mixed_day(),
            TestFixturesV2.get_fixture_b_watchlist_hit(),
            TestFixturesV2.get_fixture_c_mini_digest_threshold(),
            TestFixturesV2.get_fixture_d_character_budget_stress(),
            TestFixturesV2.get_fixture_e_timezone_test(),
        ]

        for signals in fixtures:
            for signal in signals:
                assert signal.url.startswith("https://")
                assert len(signal.url) > 10

    def test_fixture_stable_ids(self):
        """Test that all fixtures have unique stable IDs"""
        fixtures = [
            TestFixturesV2.get_fixture_a_mixed_day(),
            TestFixturesV2.get_fixture_b_watchlist_hit(),
            TestFixturesV2.get_fixture_c_mini_digest_threshold(),
            TestFixturesV2.get_fixture_d_character_budget_stress(),
            TestFixturesV2.get_fixture_e_timezone_test(),
        ]

        all_stable_ids = []
        for signals in fixtures:
            for signal in signals:
                all_stable_ids.append(signal.stable_id)

        # Check uniqueness
        assert len(all_stable_ids) == len(set(all_stable_ids))

        # Check format
        for stable_id in all_stable_ids:
            assert len(stable_id) > 5
            assert "-" in stable_id or "_" in stable_id


class TestTestValidator:
    """Test TestValidator class"""

    @pytest.fixture
    def validator(self):
        """Create validator instance"""
        return TestValidator()

    def test_init(self, validator):
        """Test validator initialization"""
        assert validator.errors == []
        assert validator.warnings == []

    def test_validate_digest_format_valid(self, validator):
        """Test digest format validation with valid digest"""
        valid_digest = """🔍 LobbyLens — Daily Signals (2025-09-28) · 24h
Mini-stats: Bills 3 · FR 2 · Dockets 1 · Watchlist hits 0

🔎 **Watchlist Alerts**
• No watchlist hits

📈 **What Changed**
• [Energy] Final Rule — FERC: Grid reliability performance standards
  <https://fr.gov/doc/1|FR>

🏭 **Industry Snapshots**
• Energy: 2 signals
• Tech: 1 signal

⏰ **Deadlines (next 7d)**
• Grid reliability standards: 21d
  <https://fr.gov/doc/1|FR>

📊 **Docket Surges**
• EPA methane standards: +320% (24h)
  <https://reg.gov/docket/epa1|Regulations.gov>

📜 **New Bills & Actions**
• H.R. 8123 — AI Accountability Act: Introduced
  <https://congress.gov/hr8123|Congress>

+ 2 more items in thread · /lobbylens help · Updated 08:00 PT"""

        result = validator.validate_digest_format(valid_digest)
        assert result is True
        assert len(validator.errors) == 0

    def test_validate_digest_format_missing_header(self, validator):
        """Test digest format validation with missing header"""
        invalid_digest = "Some content without proper header"

        result = validator.validate_digest_format(invalid_digest)
        assert result is False
        assert "Missing required header format" in validator.errors

    def test_validate_digest_format_missing_mini_stats(self, validator):
        """Test digest format validation with missing mini-stats"""
        invalid_digest = """🔍 LobbyLens — Daily Signals (2025-09-28) · 24h
Some content without mini-stats"""

        result = validator.validate_digest_format(invalid_digest)
        assert result is False
        assert "Missing mini-stats section" in validator.errors

    def test_validate_digest_format_missing_sections(self, validator):
        """Test digest format validation with missing sections"""
        invalid_digest = """🔍 LobbyLens — Daily Signals (2025-09-28) · 24h
Mini-stats: Bills 0 · FR 0 · Dockets 0 · Watchlist hits 0

Some content without proper sections"""

        result = validator.validate_digest_format(invalid_digest)
        assert result is True  # No errors, just warnings
        assert len(validator.warnings) > 0
        assert any("Missing section" in warning for warning in validator.warnings)

    def test_validate_digest_format_character_limit(self, validator):
        """Test digest format validation with character limit warning"""
        # Create a very long digest with proper format
        long_digest = (
            """🔍 LobbyLens — Daily Signals (2025-09-28) · 24h
Mini-stats: Bills 3 · FR 2 · Dockets 1 · Watchlist hits 0

🔎 **Watchlist Alerts**
• No watchlist hits

📈 **What Changed**
• [Energy] Final Rule — FERC: Grid reliability performance standards
  <https://fr.gov/doc/1|FR>

🏭 **Industry Snapshots**
• Energy: 2 signals

⏰ **Deadlines (next 7d)**
• Grid reliability standards: 21d

📊 **Docket Surges**
• EPA methane standards: +320%

📜 **New Bills & Actions**
• H.R. 8123 — AI Accountability Act: Introduced

"""
            + "x" * 5000
        )  # Add lots of content to exceed limit

        result = validator.validate_digest_format(long_digest)
        assert result is True  # No errors, just warnings
        assert any("Slack message limits" in warning for warning in validator.warnings)

    def test_validate_digest_format_no_links(self, validator):
        """Test digest format validation with no links"""
        invalid_digest = """🔍 LobbyLens — Daily Signals (2025-09-28) · 24h
Mini-stats: Bills 0 · FR 0 · Dockets 0 · Watchlist hits 0

Some content without links"""

        result = validator.validate_digest_format(invalid_digest)
        assert result is True  # No errors, just warnings
        assert any(
            "No properly formatted links found" in warning
            for warning in validator.warnings
        )

    def test_validate_section_limits_valid(self, validator):
        """Test section limits validation with valid digest"""
        valid_digest = """🔍 LobbyLens — Daily Signals (2025-09-28) · 24h
Mini-stats: Bills 3 · FR 2 · Dockets 1 · Watchlist hits 0

🔎 **Watchlist Alerts**
• Item 1
• Item 2

📈 **What Changed**
• Item 1
• Item 2
• Item 3

🏭 **Industry Snapshots**
• Item 1
• Item 2

⏰ **Deadlines (next 7d)**
• Item 1

📊 **Docket Surges**
• Item 1

📜 **New Bills & Actions**
• Item 1
• Item 2"""

        result = validator.validate_section_limits(valid_digest)
        assert result is True
        assert len(validator.errors) == 0

    def test_validate_section_limits_exceeded(self, validator):
        """Test section limits validation with exceeded limits"""
        invalid_digest = """🔍 LobbyLens — Daily Signals (2025-09-28) · 24h
Mini-stats: Bills 3 · FR 2 · Dockets 1 · Watchlist hits 0

🔎 **Watchlist Alerts**
• Item 1
• Item 2
• Item 3
• Item 4
• Item 5
• Item 6  # Exceeds limit of 5

📈 **What Changed**
• Item 1
• Item 2
• Item 3
• Item 4
• Item 5
• Item 6
• Item 7
• Item 8  # Exceeds limit of 7"""

        result = validator.validate_section_limits(invalid_digest)
        assert result is False
        assert len(validator.errors) > 0
        assert any("exceeds limit" in error for error in validator.errors)

    def test_validate_mobile_formatting_with_ellipses(self, validator):
        """Test mobile formatting validation with ellipses"""
        digest_with_ellipses = """🔍 LobbyLens — Daily Signals (2025-09-28) · 24h
Mini-stats: Bills 3 · FR 2 · Dockets 1 · Watchlist hits 0

Some content with ellipses..."""

        result = validator.validate_mobile_formatting(digest_with_ellipses)
        assert result is True  # No errors, just warnings
        assert any("ellipses" in warning for warning in validator.warnings)

    def test_validate_mobile_formatting_long_titles(self, validator):
        """Test mobile formatting validation with long titles"""
        digest_with_long_titles = """🔍 LobbyLens — Daily Signals (2025-09-28) · 24h
Mini-stats: Bills 3 · FR 2 · Dockets 1 · Watchlist hits 0

• This is a very long title that should trigger mobile formatting warnings because it exceeds the recommended length for mobile devices and should be broken into multiple lines for better readability"""

        result = validator.validate_mobile_formatting(digest_with_long_titles)
        assert result is True  # No errors, just warnings
        assert any("long title lines" in warning for warning in validator.warnings)

    def test_validate_mobile_formatting_no_indentation(self, validator):
        """Test mobile formatting validation without indentation"""
        digest_without_indentation = """🔍 LobbyLens — Daily Signals (2025-09-28) · 24h
Mini-stats: Bills 3 · FR 2 · Dockets 1 · Watchlist hits 0

• Item 1
• Item 2
• Item 3"""

        result = validator.validate_mobile_formatting(digest_without_indentation)
        assert result is True  # No errors, just warnings
        assert any(
            "indented continuation lines" in warning for warning in validator.warnings
        )

    def test_validate_timezone_handling_with_pt(self, validator):
        """Test timezone handling validation with PT timezone"""
        digest_with_pt = """🔍 LobbyLens — Daily Signals (2025-09-28) · 24h
Mini-stats: Bills 3 · FR 2 · Dockets 1 · Watchlist hits 0

Some content

+ 2 more items in thread · /lobbylens help · Updated 08:00 PT"""

        result = validator.validate_timezone_handling(digest_with_pt)
        assert result is True
        assert len(validator.warnings) == 0

    def test_validate_timezone_handling_without_pt(self, validator):
        """Test timezone handling validation without PT timezone"""
        digest_without_pt = """🔍 LobbyLens — Daily Signals (2025-09-28) · 24h
Mini-stats: Bills 3 · FR 2 · Dockets 1 · Watchlist hits 0

Some content

+ 2 more items in thread · /lobbylens help · Updated 08:00 UTC"""

        result = validator.validate_timezone_handling(digest_without_pt)
        assert result is True  # No errors, just warnings
        assert any("PT timezone" in warning for warning in validator.warnings)

    def test_validate_timezone_handling_without_date(self, validator):
        """Test timezone handling validation without proper date format"""
        digest_without_date = """🔍 LobbyLens — Daily Signals · 24h
Mini-stats: Bills 3 · FR 2 · Dockets 1 · Watchlist hits 0

Some content"""

        result = validator.validate_timezone_handling(digest_without_date)
        assert result is True  # No errors, just warnings
        assert any("date format" in warning for warning in validator.warnings)

    def test_get_validation_report_no_issues(self, validator):
        """Test validation report with no issues"""
        report = validator.get_validation_report()
        assert "✅ All validations passed!" in report

    def test_get_validation_report_with_errors(self, validator):
        """Test validation report with errors"""
        validator.errors = ["Test error 1", "Test error 2"]
        validator.warnings = ["Test warning 1"]

        report = validator.get_validation_report()
        assert "❌ ERRORS:" in report
        assert "• Test error 1" in report
        assert "• Test error 2" in report
        assert "⚠️  WARNINGS:" in report
        assert "• Test warning 1" in report

    def test_get_validation_report_with_warnings_only(self, validator):
        """Test validation report with warnings only"""
        validator.warnings = ["Test warning 1", "Test warning 2"]

        report = validator.get_validation_report()
        assert "❌ ERRORS:" not in report
        assert "⚠️  WARNINGS:" in report
        assert "• Test warning 1" in report
        assert "• Test warning 2" in report

    def test_validator_reset(self, validator):
        """Test that validator can be reset"""
        validator.errors = ["Test error"]
        validator.warnings = ["Test warning"]

        # Create new validator
        new_validator = TestValidator()
        assert new_validator.errors == []
        assert new_validator.warnings == []

    def test_validate_digest_format_realistic(self, validator):
        """Test digest format validation with realistic digest"""
        realistic_digest = """🔍 LobbyLens — Daily Signals (2025-09-28) · 24h
Mini-stats: Bills 3 · FR 2 · Dockets 1 · Watchlist hits 0

🔎 **Watchlist Alerts**
• No watchlist hits

📈 **What Changed**
• [Energy] Final Rule — FERC: Grid reliability performance standards
  Imposes updated performance standards for transmission operators.
  <https://fr.gov/doc/1|FR>

• [Tech] Proposed Rule — FTC: Children's Online Privacy Update (COPPA 2.0)
  Expands verifiable parental consent and limits ad targeting.
  <https://fr.gov/doc/2|FR>

🏭 **Industry Snapshots**
• Energy: 2 signals (Grid reliability, Methane standards)
• Tech: 2 signals (COPPA 2.0, AI Accountability Act)
• Health: 1 signal (Hospital price transparency)

⏰ **Deadlines (next 7d)**
• Grid reliability standards: 21d
  <https://fr.gov/doc/1|FR>

• COPPA 2.0 comment period: 14d
  <https://fr.gov/doc/2|FR>

📊 **Docket Surges**
• EPA methane standards: +320% (24h)
  <https://reg.gov/docket/epa1|Regulations.gov>

📜 **New Bills & Actions**
• H.R. 8123 — AI Accountability Act: Introduced
  Establishes AI audit requirements for high-risk systems.
  <https://congress.gov/hr8123|Congress>

• H.R. 7891 — Stablecoin Consumer Protections: Markup scheduled
  Sets reserve, disclosure rules for stablecoins.
  <https://congress.gov/hr7891|Congress>

+ 1 more items in thread · /lobbylens help · Updated 08:00 PT"""

        result = validator.validate_digest_format(realistic_digest)
        assert result is True
        assert len(validator.errors) == 0
        # May have some warnings, but that's okay for a realistic digest
