"""PostgreSQL database support for production deployments."""

import logging
import os
from pathlib import Path
from typing import Any, Optional  # Dict, List removed

import psycopg2
import psycopg2.extras

from .database import DatabaseManager

# from urllib.parse import urlparse  # Unused for now

logger = logging.getLogger(__name__)


class PostgresManager(DatabaseManager):
    """PostgreSQL-specific database manager for production."""

    def __init__(self, database_url: str):
        """Initialize PostgreSQL manager.

        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url
        # For compatibility with parent class
        self.db_path = Path(database_url)

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
                -- Core LDA entities (clients, registrants)
                CREATE TABLE IF NOT EXISTS entity (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,  -- 'client', 'registrant'
                    normalized_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(normalized_name, type)
                );

                -- Issue codes (HCR, TAX, DEF, etc.)
                CREATE TABLE IF NOT EXISTS issue (
                    id SERIAL PRIMARY KEY,
                    code TEXT NOT NULL UNIQUE,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Filing records (quarterly LDA data)
                CREATE TABLE IF NOT EXISTS filing (
                    id SERIAL PRIMARY KEY,
                    filing_uid TEXT NOT NULL UNIQUE,  -- Source unique ID
                    client_id INTEGER,
                    registrant_id INTEGER,
                    filing_date TIMESTAMP,
                    quarter TEXT,  -- e.g., "2025Q3"
                    year INTEGER,
                    amount INTEGER,  -- NULL for not reported, 0 for explicitly zero
                    url TEXT,
                    summary TEXT,  -- From specific_issues/description
                filing_type TEXT,  -- Q1, Q2, Q3, Q4, etc.
                filing_status TEXT DEFAULT 'original',  -- original, amended
                is_amendment BOOLEAN DEFAULT FALSE,
                    source_system TEXT DEFAULT 'senate',  -- senate, house
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES entity(id),
                    FOREIGN KEY (registrant_id) REFERENCES entity(id)
                );

                -- Filing-issue relationships (many-to-many)
                CREATE TABLE IF NOT EXISTS filing_issue (
                    id SERIAL PRIMARY KEY,
                    filing_id INTEGER NOT NULL,
                    issue_id INTEGER NOT NULL,
                    FOREIGN KEY (filing_id) REFERENCES filing(id),
                    FOREIGN KEY (issue_id) REFERENCES issue(id),
                    UNIQUE(filing_id, issue_id)
                );

                -- Metadata for ETL tracking
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Channel-specific digest settings
                CREATE TABLE IF NOT EXISTS channel_digest_settings (
                    channel_id TEXT PRIMARY KEY,
                    min_amount INTEGER DEFAULT 10000,  -- $10K minimum for "new since last run"
                    max_lines_main INTEGER DEFAULT 15,  -- main post line cap
                    last_lda_digest_at TIMESTAMP,  -- timestamp of last digest
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Ingest log for ETL runs
                CREATE TABLE IF NOT EXISTS ingest_log (
                    id SERIAL PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    started_at TIMESTAMP NOT NULL,
                    completed_at TIMESTAMP,
                    source TEXT NOT NULL,  -- 'bulk', 'api'
                    mode TEXT NOT NULL,     -- 'backfill', 'update'
                    added_count INTEGER DEFAULT 0,
                    updated_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    errors TEXT,  -- JSON array of error messages
                    status TEXT DEFAULT 'running'  -- 'running', 'completed', 'failed'
                );

                -- Create indexes for core LDA tables
                CREATE INDEX IF NOT EXISTS idx_entity_normalized ON entity(normalized_name, type);
                CREATE INDEX IF NOT EXISTS idx_filing_uid ON filing(filing_uid);
                CREATE INDEX IF NOT EXISTS idx_filing_quarter ON filing(quarter, year);
                CREATE INDEX IF NOT EXISTS idx_filing_date ON filing(filing_date);
                CREATE INDEX IF NOT EXISTS idx_filing_amount ON filing(amount);
                CREATE INDEX IF NOT EXISTS idx_filing_client ON filing(client_id);
                CREATE INDEX IF NOT EXISTS idx_filing_registrant ON filing(registrant_id);
                CREATE INDEX IF NOT EXISTS idx_issue_code ON issue(code);

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

                -- Per-channel digest tracking for "since last run" logic
                CREATE TABLE IF NOT EXISTS channel_digest_state (
                    id SERIAL PRIMARY KEY,
                    channel_id TEXT NOT NULL,
                    service TEXT NOT NULL,  -- 'lda', 'v2', etc.
                    last_digest_at TIMESTAMP,
                    last_filing_date TIMESTAMP,  -- Track latest filing date seen
                    last_ingested_at TIMESTAMP,  -- Track latest ingested_at seen
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(channel_id, service)
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
