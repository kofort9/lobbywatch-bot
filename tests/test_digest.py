"""Tests for digest computation."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from bot.digest import DigestComputer, DigestError, compute_digest
from typing import Any, Dict, List, Optional


class TestDigestComputer:
    """Tests for DigestComputer class."""

    def test_init(self, temp_db: Any) -> None:
        """Test DigestComputer initialization."""
        computer = DigestComputer(str(temp_db))
        assert computer.db_path == temp_db
        assert computer.state_file == Path("state/last_run.json")

    def test_init_nonexistent_db(self) -> None:
        """Test initialization with non-existent database."""
        computer = DigestComputer("/nonexistent/db.sqlite")
        with pytest.raises(DigestError, match="Database file not found"):
            computer._connect()

    def test_connect(self, temp_db: Any) -> None:
        """Test database connection."""
        computer = DigestComputer(str(temp_db))
        with computer._connect() as conn:
            # Test that foreign keys are enabled
            result = conn.execute("PRAGMA foreign_keys").fetchone()
            assert result[0] == 1  # Foreign keys enabled

            # Test row factory is set
            assert conn.row_factory == sqlite3.Row

    def test_last_run_time_no_file(self, temp_db: Any, temp_state_dir: Any) -> None:
        """Test getting last run time when no state file exists."""
        computer = DigestComputer(str(temp_db))
        computer.state_file = temp_state_dir / "last_run.json"

        assert computer._get_last_run_time() is None

    def test_last_run_time_with_file(self, temp_db: Any, temp_state_dir: Any) -> None:
        """Test getting last run time from existing state file."""
        computer = DigestComputer(str(temp_db))
        computer.state_file = temp_state_dir / "last_run.json"

        # Create state file
        test_time = datetime(2023, 10, 15, 12, 0, 0)
        with open(computer.state_file, "w") as f:
            json.dump({"last_run_at": test_time.isoformat()}, f)

        result = computer._get_last_run_time()
        assert result == test_time

    def test_last_run_time_invalid_file(self, temp_db: Any, temp_state_dir: Any) -> None:
        """Test handling of invalid state file."""
        computer = DigestComputer(str(temp_db))
        computer.state_file = temp_state_dir / "last_run.json"

        # Create invalid state file
        with open(computer.state_file, "w") as f:
            f.write("invalid json")

        assert computer._get_last_run_time() is None

    def test_save_last_run_time(self, temp_db: Any, temp_state_dir: Any) -> None:
        """Test saving last run time."""
        computer = DigestComputer(str(temp_db))
        computer.state_file = temp_state_dir / "last_run.json"

        test_time = datetime(2023, 10, 15, 12, 0, 0)
        computer._save_last_run_time(test_time)

        assert computer.state_file.exists()

        with open(computer.state_file) as f:
            data = json.load(f)
            assert data["last_run_at"] == test_time.isoformat()
            assert data["version"] == "1.0"

    def test_get_new_filings(self, populated_db: Any) -> None:
        """Test getting new filings from database."""
        computer = DigestComputer(str(populated_db))

        # Get filings from last 2 days
        since = datetime.now() - timedelta(days=2)

        with computer._connect() as conn:
            filings = computer._get_new_filings(conn, since, limit=10)

        assert len(filings) >= 2  # Should have recent filings

        # Check first filing structure
        filing = filings[0]
        assert "client_name" in filing.keys()
        assert "registrant_name" in filing.keys()
        assert "amount" in filing.keys()
        assert "url" in filing.keys()

    def test_get_top_registrants(self, populated_db: Any) -> None:
        """Test getting top registrants."""
        computer = DigestComputer(str(populated_db))

        since = datetime.now() - timedelta(days=8)  # Get week of data

        with computer._connect() as conn:
            registrants = computer._get_top_registrants(conn, since, limit=5)

        assert len(registrants) > 0

        # Check structure
        reg = registrants[0]
        assert "name" in reg.keys()
        assert "filing_count" in reg.keys()
        assert "total_amount" in reg.keys()

        # Should be sorted by total_amount DESC
        if len(registrants) > 1:
            assert registrants[0]["total_amount"] >= registrants[1]["total_amount"]

    def test_get_issue_surges(self, populated_db: Any) -> None:
        """Test getting issue surges."""
        computer = DigestComputer(str(populated_db))

        now = datetime.now()
        week_start = now - timedelta(days=7)
        prev_week_start = week_start - timedelta(days=7)

        with computer._connect() as conn:
            surges = computer._get_issue_surges(
                conn, week_start, prev_week_start, limit=5
            )

        if len(surges) > 0:
            surge = surges[0]
            assert "code" in surge.keys()
            assert "count_current" in surge.keys()
            assert "count_previous" in surge.keys()
            assert "pct_change" in surge.keys()

    def test_format_amount(self, temp_db: Any) -> None:
        """Test amount formatting."""
        computer = DigestComputer(str(temp_db))

        assert computer._format_amount(0) == "—"
        assert computer._format_amount(500) == "$500"
        assert computer._format_amount(1500) == "$2K"
        assert computer._format_amount(1000000) == "$1.0M"
        assert computer._format_amount(2500000) == "$2.5M"

    def test_format_percentage(self, temp_db: Any) -> None:
        """Test percentage formatting."""
        computer = DigestComputer(str(temp_db))

        assert computer._format_percentage(0) == "—"
        assert computer._format_percentage(0.5) == "+50%"
        assert computer._format_percentage(1.2) == "+120%"
        assert computer._format_percentage(-0.3) == "-30%"
        assert computer._format_percentage(10.0) == "∞"  # Represents infinity

    @patch("bot.digest.datetime")
    def test_compute_digest_success(self, mock_datetime: Any, populated_db: Any, temp_state_dir: Any) -> None:
        """Test successful digest computation."""
        # Mock current time
        fixed_now = datetime(2023, 10, 15, 12, 0, 0)
        mock_datetime.now.return_value = fixed_now

        computer = DigestComputer(str(populated_db))
        computer.state_file = temp_state_dir / "last_run.json"

        result = computer.compute_digest()

        assert isinstance(result, str)
        assert "LobbyLens Daily Digest" in result
        assert "2023-10-15" in result
        assert "New filings" in result

        # Verify state was saved
        assert computer.state_file.exists()

    def test_compute_digest_no_data(self, temp_db: Any, temp_state_dir: Any) -> None:
        """Test digest computation with no data."""
        computer = DigestComputer(str(temp_db))
        computer.state_file = temp_state_dir / "last_run.json"

        result = computer.compute_digest()

        assert (
            "No fresh lobbying activity detected" in result
            or "LobbyLens Daily Digest" in result
        )

    def test_compute_digest_database_error(self, temp_state_dir: Any) -> None:
        """Test digest computation with database error."""
        # Use non-existent database
        computer = DigestComputer("/nonexistent/path.db")
        computer.state_file = temp_state_dir / "last_run.json"

        with pytest.raises(DigestError, match="Database file not found"):
            computer.compute_digest()


class TestDigestFormatting:
    """Tests for digest message formatting."""

    def test_digest_structure(self, populated_db: Any, temp_state_dir: Any) -> None:
        """Test that digest has expected structure."""
        computer = DigestComputer(str(populated_db))
        computer.state_file = temp_state_dir / "last_run.json"

        result = computer.compute_digest()
        lines = result.split("\n")

        # Should have header
        assert any("LobbyLens Daily Digest" in line for line in lines)

        # Should have sections
        section_headers = ["New filings", "Top registrants", "Issue activity"]

        for header in section_headers:
            assert any(header in line for line in lines)

    def test_digest_with_urls(self, populated_db: Any, temp_state_dir: Any) -> None:
        """Test digest formatting with filing URLs."""
        computer = DigestComputer(str(populated_db))
        computer.state_file = temp_state_dir / "last_run.json"

        result = computer.compute_digest()

        # Should contain URL formatting for Slack
        assert "http://example.com" in result or "View>" in result


def test_compute_digest_convenience_function(populated_db: Any) -> None:
    """Test the convenience function."""
    result = compute_digest(str(populated_db))

    assert isinstance(result, str)
    assert len(result) > 0
