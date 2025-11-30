"""Test create_signals_database fallback behavior."""

from bot.signals_database import SignalsDatabaseV2, create_signals_database


def test_create_signals_database_fallback_to_sqlite() -> None:
    """Invalid PG URL should return SQLite backend."""
    db = create_signals_database("postgresql://invalid-url")
    assert isinstance(db, SignalsDatabaseV2)
