"""PostgreSQL database support for production deployments."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

from .database import DatabaseManager

logger = logging.getLogger(__name__)


class PostgresManager(DatabaseManager):
    """PostgreSQL-specific database manager for production."""

    def __init__(self, database_url: str):
        """Initialize PostgreSQL manager.

        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url
        self.db_path = Path(database_url)  # For compatibility with parent class

    def get_connection(self) -> Any:
        """Get PostgreSQL connection with proper settings."""
        try:
            conn = psycopg2.connect(
                self.database_url, cursor_factory=psycopg2.extras.RealDictCursor
            )
            conn.autocommit = False
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise

    def ensure_enhanced_schema(self) -> None:
        """Ensure enhanced schema exists for LobbyLens features."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                # Create enhanced tables for LobbyLens features
                cursor.execute(
                    """
                -- Channel-specific settings and state
                CREATE TABLE IF NOT EXISTS channel_settings (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    threshold_filings INTEGER DEFAULT 10,
                    threshold_amount INTEGER DEFAULT 100000,
                    show_descriptions BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Per-channel watchlists
                CREATE TABLE IF NOT EXISTS channel_watchlist (
                    id SERIAL PRIMARY KEY,
                    channel_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id INTEGER,
                    watch_name TEXT NOT NULL,
                    display_name TEXT,
                    fuzzy_score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (channel_id) REFERENCES channel_settings(id),
                    UNIQUE(channel_id, entity_type, watch_name)
                );
                
                -- Alias mapping for fast future matches
                CREATE TABLE IF NOT EXISTS entity_aliases (
                    id SERIAL PRIMARY KEY,
                    alias_name TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id INTEGER,
                    confidence_score REAL DEFAULT 1.0,
                    usage_count INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(alias_name, entity_type)
                );
                
                -- Digest run tracking per channel
                CREATE TABLE IF NOT EXISTS digest_runs (
                    id SERIAL PRIMARY KEY,
                    channel_id TEXT NOT NULL,
                    run_type TEXT NOT NULL,
                    run_time TIMESTAMP NOT NULL,
                    filings_count INTEGER DEFAULT 0,
                    last_filing_time TIMESTAMP,
                    digest_content TEXT,
                    FOREIGN KEY (channel_id) REFERENCES channel_settings(id)
                );
                
                -- Enhanced filing tracking
                CREATE TABLE IF NOT EXISTS filing_tracking (
                    filing_id INTEGER PRIMARY KEY,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    digest_sent_to TEXT,
                    watchlist_matches TEXT
                );
                
                -- Create indexes for performance
                CREATE INDEX IF NOT EXISTS idx_watchlist_channel ON channel_watchlist(channel_id);
                CREATE INDEX IF NOT EXISTS idx_aliases_name ON entity_aliases(alias_name);
                CREATE INDEX IF NOT EXISTS idx_digest_runs_channel_time ON digest_runs(channel_id, run_time);
                CREATE INDEX IF NOT EXISTS idx_filing_tracking_processed ON filing_tracking(processed_at);
                """
                )

                conn.commit()
                logger.info("Enhanced PostgreSQL schema ensured")


def create_database_manager(database_url: Optional[str] = None) -> DatabaseManager:
    """Factory function to create appropriate database manager."""

    # Use DATABASE_URL if provided (Railway/Heroku style)
    if not database_url:
        database_url = os.getenv("DATABASE_URL")

    if database_url and database_url.startswith("postgres"):
        logger.info("Using PostgreSQL database manager")
        return PostgresManager(database_url)
    else:
        # Fall back to SQLite
        database_file = os.getenv("DATABASE_FILE", "lobbywatch.db")
        logger.info(f"Using SQLite database manager: {database_file}")
        return DatabaseManager(database_file)
