"""Formatting and edge-case tests for EnhancedDigestComputer."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from bot.database import DatabaseManager
from bot.enhanced_digest import EnhancedDigestComputer


def _prepare_enhanced_tables(db_manager: DatabaseManager) -> None:
    """Create minimal enhanced tables on the lightweight fixture schema."""
    with db_manager.get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS channel_settings (
                id TEXT PRIMARY KEY,
                threshold_filings INTEGER DEFAULT 10,
                threshold_amount INTEGER DEFAULT 100000,
                show_descriptions BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS channel_watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                watch_name TEXT NOT NULL,
                display_name TEXT,
                fuzzy_score REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS digest_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                run_type TEXT NOT NULL,
                run_time TEXT NOT NULL,
                filings_count INTEGER DEFAULT 0,
                last_filing_time TEXT,
                digest_content TEXT
            );
            """
        )


def test_format_filing_entry_truncates_and_links() -> None:
    """Ensure long descriptions are trimmed and watchlist entries are highlighted."""
    digest = EnhancedDigestComputer(db_manager=object())  # DB not used here
    filing = {
        "client_name": "Client",
        "registrant_name": "Reg",
        "amount": 1500000,
        "description": (
            "A very long description that should be truncated because it exceeds the "
            "limit set by the formatter."
        ),
        "url": "http://example.com/filing",
    }

    entry = digest._format_filing_entry(
        filing, is_watchlist=True, show_description=True
    )

    assert entry.startswith("**• Client → Reg ($1.5M)")
    assert entry.endswith("**")
    assert "..." in entry
    assert "<http://example.com/filing|Filing>" in entry


def test_compute_enhanced_digest_mini_watchlist(populated_db: Path) -> None:
    """Mini digest should include watchlist indicator and persist run record."""
    db_manager = DatabaseManager(str(populated_db))
    _prepare_enhanced_tables(db_manager)
    channel_id = "CHAN1"
    now = datetime.now(timezone.utc)
    with db_manager.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO filing (id, client_id, registrant_id, filing_date, created_at,
                                amount, url, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                700,
                3,
                6,
                now.date().isoformat(),
                now.isoformat(),
                55000,
                "http://example.com/watch",
                "Fresh watchlist filing",
            ),
        )
        conn.execute(
            "INSERT INTO filing_issue (id, filing_id, issue_id) VALUES (?, ?, ?)",
            (700, 700, 1),
        )
    db_manager.add_to_watchlist(
        channel_id=channel_id,
        entity_type="client",
        watch_name="MegaPharm LLC",
        display_name="MegaPharm LLC",
        entity_id=3,
    )

    digest_text = EnhancedDigestComputer(db_manager).compute_enhanced_digest(
        channel_id, digest_type="mini"
    )

    assert "LobbyLens Mini Update" in digest_text
    assert "🎯" in digest_text  # watchlist match indicator
    assert "MegaPharm LLC" in digest_text
    assert db_manager.get_last_digest_run(channel_id, "mini") is not None


def test_should_send_mini_digest_triggers_on_watchlist(populated_db: Path) -> None:
    """Watchlist matches should trigger mini digest even below filing threshold."""
    db_manager = DatabaseManager(str(populated_db))
    _prepare_enhanced_tables(db_manager)
    channel_id = "CHAN2"
    db_manager.get_channel_settings(channel_id)  # creates defaults
    db_manager.update_channel_setting(channel_id, "threshold_filings", 5)
    db_manager.record_digest_run(channel_id, "daily")

    # New filing after the daily run
    future_time = datetime.now(timezone.utc) + timedelta(minutes=5)
    with db_manager.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO filing (id, client_id, registrant_id, filing_date, created_at,
                                amount, url, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                999,
                1,
                4,
                future_time.date().isoformat(),
                future_time.isoformat(),
                25000,
                "http://example.com/new",
                "Post-digest filing",
            ),
        )
        conn.execute(
            "INSERT INTO filing_issue (id, filing_id, issue_id) VALUES (?, ?, ?)",
            (999, 999, 1),
        )

    db_manager.add_to_watchlist(
        channel_id=channel_id,
        entity_type="client",
        watch_name="Acme Corp",
        display_name="Acme Corp",
        entity_id=1,
    )

    digest_computer = EnhancedDigestComputer(db_manager)
    assert digest_computer.should_send_mini_digest(channel_id) is True


def test_compute_enhanced_digest_daily_sections(populated_db: Path) -> None:
    """Daily digest should include registrant and issue sections."""
    db_manager = DatabaseManager(str(populated_db))
    _prepare_enhanced_tables(db_manager)
    channel_id = "CHAN3"

    digest_text = EnhancedDigestComputer(db_manager).compute_enhanced_digest(
        channel_id, digest_type="daily"
    )

    assert "Top registrants" in digest_text
    assert "Issue activity" in digest_text
