"""Pytest configuration and fixtures."""

import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator

import pytest
import requests_mock

from bot.config import Settings
from bot.notifiers.slack import SlackNotifier


@pytest.fixture
def temp_db() -> Generator[Path, None, None]:
    """Create a temporary SQLite database with test schema."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Create test schema matching LobbyLens database structure
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON;")

    # Create basic schema
    conn.executescript(
        """
        CREATE TABLE entity (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT
        );

        CREATE TABLE issue (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL,
            description TEXT
        );

        CREATE TABLE filing (
            id INTEGER PRIMARY KEY,
            client_id INTEGER,
            registrant_id INTEGER,
            filing_date TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            amount INTEGER,
            url TEXT,
            description TEXT,
            FOREIGN KEY (client_id) REFERENCES entity(id),
            FOREIGN KEY (registrant_id) REFERENCES entity(id)
        );

        CREATE TABLE filing_issue (
            id INTEGER PRIMARY KEY,
            filing_id INTEGER NOT NULL,
            issue_id INTEGER NOT NULL,
            FOREIGN KEY (filing_id) REFERENCES filing(id),
            FOREIGN KEY (issue_id) REFERENCES issue(id)
        );
    """
    )

    conn.close()

    try:
        yield db_path
    finally:
        db_path.unlink(missing_ok=True)


@pytest.fixture
def populated_db(temp_db: Path) -> Path:
    """Create a database populated with test data."""
    conn = sqlite3.connect(str(temp_db))

    now = datetime.now()
    yesterday = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    # Insert test entities
    entities = [
        (1, "Acme Corp", "client"),
        (2, "BigTech Inc", "client"),
        (3, "MegaPharm LLC", "client"),
        (4, "K Street Advisors", "registrant"),
        (5, "Capitol Consulting", "registrant"),
        (6, "Influence Partners", "registrant"),
    ]
    conn.executemany("INSERT INTO entity (id, name, type) VALUES (?, ?, ?)", entities)

    # Insert test issues
    issues = [
        (1, "HCR", "Health Care Reform"),
        (2, "TAX", "Tax Policy"),
        (3, "DEF", "Defense Spending"),
        (4, "ENV", "Environmental Policy"),
        (5, "TRD", "Trade Policy"),
    ]
    conn.executemany(
        "INSERT INTO issue (id, code, description) VALUES (?, ?, ?)", issues
    )

    # Insert test filings
    filings = [
        # Recent filings (last 24h)
        (
            1,
            1,
            4,
            yesterday.date().isoformat(),
            yesterday.isoformat(),
            50000,
            "http://example.com/1",
            "Recent filing 1",
        ),
        (
            2,
            2,
            5,
            yesterday.date().isoformat(),
            yesterday.isoformat(),
            75000,
            "http://example.com/2",
            "Recent filing 2",
        ),
        (
            3,
            3,
            6,
            now.date().isoformat(),
            now.isoformat(),
            100000,
            "http://example.com/3",
            "Today's filing",
        ),
        # Week-old filings
        (
            4,
            1,
            4,
            week_ago.date().isoformat(),
            week_ago.isoformat(),
            25000,
            "http://example.com/4",
            "Week old filing",
        ),
        (
            5,
            2,
            5,
            week_ago.date().isoformat(),
            week_ago.isoformat(),
            150000,
            "http://example.com/5",
            "Big week old filing",
        ),
        # Two weeks ago filings
        (
            6,
            1,
            4,
            two_weeks_ago.date().isoformat(),
            two_weeks_ago.isoformat(),
            30000,
            "http://example.com/6",
            "Old filing",
        ),
    ]
    conn.executemany(
        "INSERT INTO filing (id, client_id, registrant_id, filing_date, created_at, amount, url, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        filings,
    )

    # Insert filing-issue relationships
    filing_issues = [
        (1, 1, 1),  # Filing 1 -> Health Care
        (2, 2, 2),  # Filing 2 -> Tax Policy
        (3, 3, 1),  # Filing 3 -> Health Care
        (4, 4, 3),  # Filing 4 -> Defense
        (5, 5, 2),  # Filing 5 -> Tax Policy
        (6, 6, 1),  # Filing 6 -> Health Care
    ]
    conn.executemany(
        "INSERT INTO filing_issue (id, filing_id, issue_id) VALUES (?, ?, ?)",
        filing_issues,
    )

    conn.commit()
    conn.close()

    return temp_db


@pytest.fixture
def temp_state_dir(tmp_path: Path) -> Path:
    """Create temporary state directory."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def test_settings(temp_db: Path, temp_state_dir: Path) -> Settings:
    """Create test settings."""
    return Settings(
        database_file=str(temp_db),
        slack_webhook_url="https://hooks.slack.com/services/TEST/TEST/TEST",
        opensecrets_api_key="test_key",
        propublica_api_key="test_key",
        log_level="DEBUG",
        dry_run=False,
    )


@pytest.fixture
def mock_slack_webhook():
    """Mock Slack webhook requests."""
    with requests_mock.Mocker() as m:
        m.post("https://hooks.slack.com/services/TEST/TEST/TEST", text="ok")
        yield m


@pytest.fixture
def slack_notifier() -> SlackNotifier:
    """Create a test Slack notifier."""
    return SlackNotifier("https://hooks.slack.com/services/TEST/TEST/TEST")


@pytest.fixture
def sample_digest_data():
    """Sample data for digest formatting tests."""
    return {
        "new_filings": [
            {
                "filing_date": "2023-10-15",
                "client_name": "Acme Corp",
                "registrant_name": "K Street Advisors",
                "amount": 50000,
                "url": "http://example.com/filing1",
            },
            {
                "filing_date": "2023-10-15",
                "client_name": "BigTech Inc",
                "registrant_name": "Capitol Consulting",
                "amount": 75000,
                "url": None,
            },
        ],
        "top_registrants": [
            {"name": "Capitol Consulting", "total_amount": 150000, "filing_count": 3},
            {"name": "K Street Advisors", "total_amount": 75000, "filing_count": 2},
        ],
        "issue_surges": [
            {"code": "HCR", "count_current": 5, "count_previous": 2, "pct_change": 1.5},
            {
                "code": "TAX",
                "count_current": 3,
                "count_previous": 0,
                "pct_change": 999.0,
            },
        ],
    }
