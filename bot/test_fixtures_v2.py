"""
LobbyLens Test Fixtures v2 - Comprehensive test data for v2 signals
Implements the test fixtures specified in the requirements.
"""

from datetime import datetime, timedelta, timezone
from typing import List

from bot.signals_v2 import SignalV2


class TestFixturesV2:
    """Test fixtures for v2 signals system"""

    @staticmethod
    def get_fixture_a_mixed_day() -> List[SignalV2]:
        """Fixture A - Mixed day with various signal types"""
        now = datetime.now(timezone.utc)

        signals = [
            # A1: Final Rule - Grid reliability
            SignalV2(
                source="federal_register",
                stable_id="FR-2025-09-28-001",
                title="Final Rule: Grid reliability performance standards",
                summary="Imposes updated performance standards for transmission operators.",
                url="https://fr.gov/doc/1",
                timestamp=now - timedelta(hours=2),
                issue_codes=["ENE"],
                deadline=now + timedelta(days=21),
                agency="FERC",
            ),
            # A2: Proposed Rule - COPPA 2.0
            SignalV2(
                source="federal_register",
                stable_id="FR-2025-09-28-002",
                title="Proposed Rule: Children's Online Privacy Update (COPPA 2.0)",
                summary="Expands verifiable parental consent and limits ad targeting.",
                url="https://fr.gov/doc/2",
                timestamp=now - timedelta(hours=1),
                issue_codes=["TEC"],
                deadline=now + timedelta(days=14),
                agency="FTC",
            ),
            # A3: Docket with surge
            SignalV2(
                source="regulations_gov",
                stable_id="REG-epa-methane-001",
                title="EPA: Methane emissions standards docket",
                summary="Significant public interest; new analysis on monitoring.",
                url="https://reg.gov/docket/epa1",
                timestamp=now - timedelta(hours=3),
                issue_codes=["ENE", "ENV"],
                comment_count=1480,
                metric_json={
                    "baseline_comments_14d": 2100,
                    "comments_24h_delta": 480,
                    "comments_24h_delta_pct": 320.0,
                },
                deadline=now + timedelta(days=5),
                agency="EPA",
            ),
            # A4: Hearing scheduled
            SignalV2(
                source="congress",
                stable_id="HR-4815-118-2025-09-28",
                bill_id="HR-4815-118",
                action_type="hearing_scheduled",
                title="Hearing: Hospital Price Transparency",
                summary="House E&C Subcommittee hearing on price transparency.",
                url="https://congress.gov/hr4815",
                timestamp=now - timedelta(hours=1),
                issue_codes=["HCR", "TAX"],
                deadline=now + timedelta(days=3),
            ),
            # A5: Bill introduced
            SignalV2(
                source="congress",
                stable_id="HR-8123-118-2025-09-28",
                bill_id="HR-8123-118",
                action_type="introduced",
                title="H.R. 8123 — AI Accountability Act",
                summary="Establishes AI audit requirements for high-risk systems.",
                url="https://congress.gov/hr8123",
                timestamp=now - timedelta(minutes=30),
                issue_codes=["TEC"],
            ),
            # A6: Markup scheduled
            SignalV2(
                source="congress",
                stable_id="HR-7891-118-2025-09-28",
                bill_id="HR-7891-118",
                action_type="markup_scheduled",
                title="H.R. 7891 — Stablecoin Consumer Protections",
                summary="Sets reserve, disclosure rules for stablecoins.",
                url="https://congress.gov/hr7891",
                timestamp=now - timedelta(hours=2),
                issue_codes=["FIN", "TEC"],
                deadline=now + timedelta(days=7),
            ),
            # A7: Notice
            SignalV2(
                source="federal_register",
                stable_id="FR-2025-09-28-003",
                title="Notice: NEPA categorical exclusions update",
                summary="Updates to environmental review process.",
                url="https://fr.gov/doc/3",
                timestamp=now - timedelta(hours=4),
                issue_codes=["ENV"],
                agency="CEQ",
            ),
        ]

        return signals

    @staticmethod
    def get_fixture_b_watchlist_hit() -> List[SignalV2]:
        """Fixture B - Watchlist hit scenario"""
        now = datetime.now(timezone.utc)

        signals = [
            # B1: Google-related signal
            SignalV2(
                source="federal_register",
                stable_id="FR-2025-09-28-004",
                title="Proposed Rule: Google Play children's ads restrictions",
                summary="Affects app store ad targeting for children's apps.",
                url="https://fr.gov/doc/4",
                timestamp=now - timedelta(hours=1),
                issue_codes=["TEC"],
                deadline=now + timedelta(days=14),
                agency="FTC",
                watchlist_hit=True,  # Explicitly set watchlist hit
            )
        ]

        return signals

    @staticmethod
    def get_fixture_c_mini_digest_threshold() -> List[SignalV2]:
        """Fixture C - Mini-digest threshold scenario"""
        now = datetime.now(timezone.utc)

        signals = []

        # Generate 12 assorted signals in last 4h
        for i in range(12):
            signal = SignalV2(
                source="congress" if i % 3 == 0 else "federal_register",
                stable_id=f"TEST-{i:03d}",
                title=f"Test Signal {i+1}",
                summary=f"Test summary for signal {i+1}",
                url=f"https://test.gov/signal{i+1}",
                timestamp=now - timedelta(hours=3, minutes=i * 20),
                issue_codes=["TEC"] if i % 2 == 0 else ["HCR"],
                priority_score=6.0 if i == 0 else 2.0,  # One high-priority signal
            )
            signals.append(signal)

        return signals

    @staticmethod
    def get_fixture_d_character_budget_stress() -> List[SignalV2]:
        """Fixture D - Character budget stress test (40+ signals)"""
        now = datetime.now(timezone.utc)

        signals = []

        # Generate 40+ signals
        for i in range(45):
            signal = SignalV2(
                source=(
                    "congress"
                    if i % 4 == 0
                    else "federal_register" if i % 4 == 1 else "regulations_gov"
                ),
                stable_id=f"STRESS-{i:03d}",
                title=f"Stress Test Signal {i+1} with a Very Long Title That Should Test Character Budget Limits and Mobile Formatting",
                summary=f"This is a very long summary that should test the character budget limits and mobile formatting capabilities of the digest system. Signal {i+1} has extensive content.",
                url=f"https://stress-test.gov/signal{i+1}",
                timestamp=now - timedelta(hours=23, minutes=i * 30),
                issue_codes=(
                    ["TEC", "HCR", "ENV"]
                    if i % 3 == 0
                    else ["FIN"] if i % 3 == 1 else ["ENE"]
                ),
                priority_score=float(i % 10),  # Varying priority scores
                agency="EPA" if i % 5 == 0 else "FTC" if i % 5 == 1 else "FCC",
            )
            signals.append(signal)

        return signals

    @staticmethod
    def get_fixture_e_timezone_test() -> List[SignalV2]:
        """Fixture E - Timezone handling test"""
        now = datetime.now(timezone.utc)

        signals = [
            SignalV2(
                source="federal_register",
                stable_id="TZ-TEST-001",
                title="Timezone Test Signal",
                summary="Test signal for timezone handling",
                url="https://test.gov/tz1",
                timestamp=now - timedelta(hours=1),
                issue_codes=["TEC"],
                deadline=now + timedelta(hours=2),  # 2 hours from now
            )
        ]

        return signals


class TestValidator:
    """Validator for test scenarios"""

    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate_digest_format(self, digest_text: str) -> bool:
        """Validate digest format against requirements"""
        lines = digest_text.split("\n")

        # Check header format
        if not any("LobbyLens — Daily Signals" in line for line in lines):
            self.errors.append("Missing required header format")

        # Check mini-stats format
        if not any("Mini-stats:" in line for line in lines):
            self.errors.append("Missing mini-stats section")

        # Check section headers
        required_sections = [
            "Watchlist Alerts",
            "What Changed",
            "Industry Snapshots",
            "Deadlines",
            "Docket Surges",
            "New Bills & Actions",
        ]

        for section in required_sections:
            if not any(section in line for line in lines):
                self.warnings.append(f"Missing section: {section}")

        # Check character limits
        if len(digest_text) > 4000:  # Slack message limit
            self.warnings.append("Digest may exceed Slack message limits")

        # Check link format
        if not any("<https://" in line and "|" in line for line in lines):
            self.warnings.append("No properly formatted links found")

        return len(self.errors) == 0

    def validate_section_limits(self, digest_text: str) -> bool:
        """Validate section item limits"""
        lines = digest_text.split("\n")

        # Count items in each section
        section_counts = {}
        current_section = None

        for line in lines:
            if line.startswith("🔎 **Watchlist Alerts**"):
                current_section = "watchlist"
                section_counts[current_section] = 0
            elif line.startswith("📈 **What Changed**"):
                current_section = "what_changed"
                section_counts[current_section] = 0
            elif line.startswith("🏭 **Industry Snapshots**"):
                current_section = "industry"
                section_counts[current_section] = 0
            elif line.startswith("⏰ **Deadlines**"):
                current_section = "deadlines"
                section_counts[current_section] = 0
            elif line.startswith("📊 **Docket Surges**"):
                current_section = "surges"
                section_counts[current_section] = 0
            elif line.startswith("📜 **New Bills & Actions**"):
                current_section = "bills"
                section_counts[current_section] = 0
            elif line.startswith("•") and current_section:
                section_counts[current_section] += 1

        # Check limits
        limits = {
            "watchlist": 5,
            "what_changed": 7,
            "industry": 12,
            "deadlines": 5,
            "surges": 3,
            "bills": 5,
        }

        for section, count in section_counts.items():
            if count > limits.get(section, 0):
                self.errors.append(
                    f"Section {section} exceeds limit: {count} > {limits[section]}"
                )

        return len(self.errors) == 0

    def validate_mobile_formatting(self, digest_text: str) -> bool:
        """Validate mobile-friendly formatting"""
        lines = digest_text.split("\n")

        # Check for ellipses (should be avoided)
        if any("..." in line for line in lines):
            self.warnings.append("Found ellipses - should use line breaks instead")

        # Check for proper line breaks in long titles
        long_title_lines = [
            line for line in lines if len(line) > 80 and line.startswith("•")
        ]
        if long_title_lines:
            self.warnings.append(
                "Found long title lines that may need mobile formatting"
            )

        # Check for proper indentation
        indented_lines = [line for line in lines if line.startswith("  ")]
        if not indented_lines:
            self.warnings.append("No indented continuation lines found")

        return True

    def validate_timezone_handling(self, digest_text: str) -> bool:
        """Validate timezone handling"""
        lines = digest_text.split("\n")

        # Check for PT timezone in footer
        if not any("PT" in line for line in lines):
            self.warnings.append("No PT timezone found in footer")

        # Check for proper date format
        if not any("2025-" in line for line in lines):
            self.warnings.append("No proper date format found")

        return True

    def get_validation_report(self) -> str:
        """Get validation report"""
        report = []

        if self.errors:
            report.append("❌ ERRORS:")
            for error in self.errors:
                report.append(f"  • {error}")

        if self.warnings:
            report.append("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                report.append(f"  • {warning}")

        if not self.errors and not self.warnings:
            report.append("✅ All validations passed!")

        return "\n".join(report)
