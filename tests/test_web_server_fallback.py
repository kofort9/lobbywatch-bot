"""Ensure web_server falls back to SQLite when Postgres unavailable."""

from unittest.mock import patch

from bot.web_server import create_web_server


@patch("bot.signals_database.SignalsDatabasePG", side_effect=RuntimeError("fail pg"))
def test_web_server_sqlite_fallback(_mock_pg: object) -> None:
    """Create server without raising when PG unavailable."""
    app = create_web_server()
    assert app is not None
