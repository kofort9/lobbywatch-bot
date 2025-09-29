"""Test LDA Front Page Digest functionality."""

import os
import sys
import tempfile
import unittest

from bot.database import DatabaseManager
from bot.lda_front_page_digest import LDAFrontPageDigest
from bot.lda_issue_codes import seed_issue_codes

# from datetime import datetime, timezone  # Unused

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestLDAFrontPageDigest(unittest.TestCase):
    """Test LDA Front Page Digest functionality."""

    def setUp(self):
        """Set up test database."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        self.db_manager = DatabaseManager(self.db_path)
        self.db_manager.ensure_enhanced_schema()
        seed_issue_codes(self.db_manager)

        self.digest = LDAFrontPageDigest(self.db_manager)

        # Create test data
        self._create_test_data()

    def tearDown(self):
        """Clean up test database."""
        try:
            os.unlink(self.db_path)
        except BaseException:
            pass

    def _create_test_data(self):
        """Create comprehensive test data."""
        with self.db_manager.get_connection() as conn:
            # Create entities
            entities = [
                (1, "Akin Gump", "registrant", "akin gump"),
                (2, "Covington & Burling", "registrant", "covington burling"),
                (11, "Meta Platforms", "client", "meta platforms"),
                (12, "Google LLC", "client", "google llc"),
            ]

            for entity_id, name, entity_type, normalized_name in entities:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO entity (id, name, type, normalized_name)
                    VALUES (?, ?, ?, ?)
                """,
                    (entity_id, name, entity_type, normalized_name),
                )

            # Create current quarter filings
            filings = [
                (
                    1,
                    "filing-001",
                    11,
                    1,
                    "2024-07-15",
                    "2024Q3",
                    2024,
                    420000,
                    "original",
                    False,
                    "2024-09-29T10:00:00Z",
                ),
                (
                    2,
                    "filing-002",
                    12,
                    2,
                    "2024-08-01",
                    "2024Q3",
                    2024,
                    380000,
                    "original",
                    False,
                    "2024-09-29T11:00:00Z",
                ),
                (
                    3,
                    "filing-003",
                    11,
                    1,
                    "2024-09-15",
                    "2024Q3",
                    2024,
                    320000,
                    "amended",
                    True,
                    "2024-09-29T14:00:00Z",
                ),
            ]

            for filing_data in filings:
                (
                    filing_id,
                    filing_uid,
                    client_id,
                    registrant_id,
                    filing_date,
                    quarter,
                    year,
                    amount,
                    filing_status,
                    is_amendment,
                    ingested_at,
                ) = filing_data
                conn.execute(
                    """
                    INSERT OR REPLACE INTO filing
                    (id, filing_uid, client_id, registrant_id, filing_date, quarter, year, amount,
                     filing_type, filing_status, is_amendment, source_system, ingested_at, url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Q3', ?, ?, 'senate', ?,
                            'https://lda.senate.gov/filings/public/filing/' || ? || '/print/')
                """,
                    (
                        filing_id,
                        filing_uid,
                        client_id,
                        registrant_id,
                        filing_date,
                        quarter,
                        year,
                        amount,
                        filing_status,
                        is_amendment,
                        ingested_at,
                        filing_uid,
                    ),
                )

            # Create filing-issue relationships
            issue_map = {}
            cursor = conn.execute(
                "SELECT id, code FROM issue WHERE code IN ('TEC', 'HCR')"
            )
            for row in cursor.fetchall():
                issue_map[row["code"]] = row["id"]

            filing_issues = [
                (1, issue_map["TEC"]),
                (2, issue_map["TEC"]),
                (3, issue_map["HCR"]),
            ]

            for filing_id, issue_id in filing_issues:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO filing_issue (filing_id, issue_id)
                    VALUES (?, ?)
                """,
                    (filing_id, issue_id),
                )

    def test_digest_generation(self):
        """Test basic digest generation."""
        digest = self.digest.generate_digest("test_channel", "2024Q3")

        self.assertIsInstance(digest, str)
        self.assertIn("LDA 2024Q3", digest)
        self.assertIn("Top registrants", digest)
        self.assertIn("Top issues", digest)

    def test_header_narrative(self):
        """Test header narrative contains required elements."""
        digest = self.digest.generate_digest("test_channel", "2024Q3")
        lines = digest.split("\n")
        header = lines[0]

        # Should contain total amount
        self.assertIn("disclosed", header)
        # Should contain QoQ comparison
        self.assertTrue("▲" in header or "▼" in header or "—" in header)
        # Should contain top registrant
        self.assertIn("Top registrant:", header)
        # Should contain top issue
        self.assertIn("Top issue:", header)

    def test_amount_formatting(self):
        """Test amount formatting in digest."""
        digest = self.digest.generate_digest("test_channel", "2024Q3")

        # Should contain formatted amounts
        self.assertTrue(any(c in digest for c in ["K", "M", "$"]))

    def test_amendment_tracking(self):
        """Test amendment tracking and labeling."""
        # Set up last digest time to capture the amended filing
        with self.db_manager.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO channel_digest_settings
                (channel_id, last_lda_digest_at)
                VALUES ('test_channel', '2024-09-29T13:00:00Z')
            """
            )

        digest = self.digest.generate_digest("test_channel", "2024Q3")

        # Should show amended filing
        self.assertIn("(amended)", digest)

    def test_new_since_last_run(self):
        """Test 'new since last run' functionality."""
        # Set up last digest time
        with self.db_manager.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO channel_digest_settings
                (channel_id, last_lda_digest_at)
                VALUES ('test_channel', '2024-09-29T13:00:00Z')
            """
            )

        digest = self.digest.generate_digest("test_channel", "2024Q3")

        # Should have new/amended section
        self.assertIn("New/Amended since last run", digest)

    def test_no_new_items(self):
        """Test digest when no new items since last run."""
        # Set last digest time after all filings
        with self.db_manager.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO channel_digest_settings
                (channel_id, last_lda_digest_at)
                VALUES ('test_channel', '2024-09-29T15:00:00Z')
            """
            )

        digest = self.digest.generate_digest("test_channel", "2024Q3")

        # Should not have new/amended section
        self.assertNotIn("New/Amended since last run", digest)
        # But should still have other sections
        self.assertIn("Top registrants", digest)

    def test_line_limits(self):
        """Test line limits and structure."""
        digest = self.digest.generate_digest("test_channel", "2024Q3")
        lines = digest.split("\n")

        # Should have header
        self.assertIn("LDA 2024Q3", lines[0])

        # Should have footer with help and timestamp
        footer = lines[-1]
        self.assertIn("/lobbylens lda help", footer)
        self.assertIn("Updated", footer)
        self.assertIn("PT", footer)

    def test_channel_settings(self):
        """Test channel-specific settings."""
        # Test default settings creation
        settings = self.digest._get_channel_settings("new_channel")

        self.assertEqual(settings["min_amount"], 10000)
        self.assertEqual(settings["max_lines_main"], 15)
        self.assertIsNone(settings["last_lda_digest_at"])

    def test_digest_state_update(self):
        """Test digest state is updated after generation."""
        # Generate digest
        self.digest.generate_digest("test_channel", "2024Q3")

        # Check that last digest time was updated
        with self.db_manager.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT last_lda_digest_at FROM channel_digest_settings
                WHERE channel_id = 'test_channel'
            """
            )
            row = cursor.fetchone()

            self.assertIsNotNone(row)
            self.assertIsNotNone(row["last_lda_digest_at"])

    def test_quarter_parsing(self):
        """Test quarter parsing functionality."""
        year, q = self.digest._parse_quarter("2024Q3")
        self.assertEqual(year, 2024)
        self.assertEqual(q, 3)

        prev_year, prev_q = self.digest._get_previous_quarter(2024, 1)
        self.assertEqual(prev_year, 2023)
        self.assertEqual(prev_q, 4)

        prev_year, prev_q = self.digest._get_previous_quarter(2024, 2)
        self.assertEqual(prev_year, 2024)
        self.assertEqual(prev_q, 1)

    def test_current_quarter_detection(self):
        """Test current quarter detection."""
        current_quarter = self.digest._get_current_quarter()

        # Should be in format YYYYQX
        self.assertRegex(current_quarter, r"\d{4}Q[1-4]")

    def test_error_handling(self):
        """Test error handling in digest generation."""
        # Test with invalid quarter
        digest = self.digest.generate_digest("test_channel", "invalid")

        # Should return error message
        self.assertIn("Failed to generate", digest)


if __name__ == "__main__":
    unittest.main()
