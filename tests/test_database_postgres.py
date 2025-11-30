"""Tests for bot/database_postgres.py - PostgreSQL database support."""

from typing import Any
from unittest.mock import Mock, patch

import pytest

from bot.database_postgres import PostgresManager, create_database_manager


class TestPostgresManager:
    """Tests for PostgresManager class."""

    def test_init(self) -> None:
        """Test PostgresManager initialization."""
        manager = PostgresManager("postgresql://user:pass@host:5432/db")
        assert manager.database_url == "postgresql://user:pass@host:5432/db"
        assert manager.db_path is not None

    @patch("bot.database_postgres.psycopg2.connect")
    def test_get_connection_success(self, mock_connect: Mock) -> None:
        """Test successful database connection."""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        manager = PostgresManager("postgresql://user:pass@host:5432/db")
        conn = manager.get_connection()

        assert conn == mock_conn
        mock_connect.assert_called_once()
        assert not mock_conn.autocommit

    @patch("bot.database_postgres.psycopg2.connect")
    def test_get_connection_failure(self, mock_connect: Mock) -> None:
        """Test database connection failure."""
        mock_connect.side_effect = Exception("Connection failed")

        manager = PostgresManager("postgresql://user:pass@host:5432/db")

        with pytest.raises(Exception, match="Connection failed"):
            manager.get_connection()

    @patch("bot.database_postgres.psycopg2.connect")
    def test_ensure_enhanced_schema(self, mock_connect: Mock) -> None:
        """Test schema creation."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)
        mock_connect.return_value = mock_conn

        manager = PostgresManager("postgresql://user:pass@host:5432/db")
        manager.ensure_enhanced_schema()

        # Verify cursor.execute was called (schema creation)
        assert mock_cursor.execute.called
        # Verify commit was called
        assert mock_conn.commit.called


class TestCreateDatabaseManager:
    """Tests for create_database_manager factory function."""

    @patch.dict("os.environ", {}, clear=True)
    @patch("bot.database_postgres.DatabaseManager")
    def test_create_database_manager_postgres_url(self, mock_db_manager: Mock) -> None:
        """Test creating PostgresManager with PostgreSQL URL."""
        manager = create_database_manager("postgresql://user:pass@host:5432/db")

        assert isinstance(manager, PostgresManager)
        assert manager.database_url == "postgresql://user:pass@host:5432/db"

    @patch.dict("os.environ", {"DATABASE_URL": "postgresql://user:pass@host:5432/db"})
    @patch("bot.database_postgres.PostgresManager")
    def test_create_database_manager_from_env(self, mock_postgres: Mock) -> None:
        """Test creating PostgresManager from DATABASE_URL env var."""
        mock_postgres.return_value = Mock()
        manager = create_database_manager()

        mock_postgres.assert_called_once_with("postgresql://user:pass@host:5432/db")

    @patch.dict("os.environ", {"DATABASE_FILE": "test.db"}, clear=True)
    @patch("bot.database_postgres.DatabaseManager")
    def test_create_database_manager_sqlite_fallback(
        self, mock_db_manager: Mock
    ) -> None:
        """Test falling back to SQLite when no PostgreSQL URL."""
        mock_db_manager.return_value = Mock()
        manager = create_database_manager()

        mock_db_manager.assert_called_once_with("test.db")

    @patch.dict("os.environ", {}, clear=True)
    @patch("bot.database_postgres.DatabaseManager")
    def test_create_database_manager_sqlite_default(
        self, mock_db_manager: Mock
    ) -> None:
        """Test defaulting to SQLite with default filename."""
        mock_db_manager.return_value = Mock()
        manager = create_database_manager()

        mock_db_manager.assert_called_once_with("lobbywatch.db")
