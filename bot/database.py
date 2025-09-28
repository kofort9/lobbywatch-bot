"""Database schema and management for enhanced LobbyLens."""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages LobbyLens database schema and operations."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper settings."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_enhanced_schema(self) -> None:
        """Ensure enhanced schema exists for LobbyLens features."""
        with self.get_connection() as conn:
            # Create enhanced tables for LobbyLens features
            conn.executescript(
                """
            -- Channel-specific settings and state
            CREATE TABLE IF NOT EXISTS channel_settings (
                id TEXT PRIMARY KEY,  -- Slack channel ID
                name TEXT,            -- Human readable channel name
                threshold_filings INTEGER DEFAULT 10,
                threshold_amount INTEGER DEFAULT 100000,
                show_descriptions BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Per-channel watchlists
            CREATE TABLE IF NOT EXISTS channel_watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                entity_type TEXT NOT NULL,  -- 'client', 'registrant', 'issue', 'agency'
                entity_id INTEGER,          -- Reference to actual entity if matched
                watch_name TEXT NOT NULL,   -- Original name user wanted to watch
                display_name TEXT,          -- Cleaned/canonical name for display
                fuzzy_score REAL,          -- Match confidence score
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (channel_id) REFERENCES channel_settings(id),
                UNIQUE(channel_id, entity_type, watch_name)
            );
            
            -- Alias mapping for fast future matches
            CREATE TABLE IF NOT EXISTS entity_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alias_name TEXT NOT NULL,
                canonical_name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                confidence_score REAL DEFAULT 1.0,
                usage_count INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(alias_name, entity_type)
            );
            
            -- Digest run tracking per channel
            CREATE TABLE IF NOT EXISTS digest_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                run_type TEXT NOT NULL,    -- 'daily', 'mini', 'alert'
                run_time TEXT NOT NULL,
                filings_count INTEGER DEFAULT 0,
                last_filing_time TEXT,
                digest_content TEXT,
                FOREIGN KEY (channel_id) REFERENCES channel_settings(id)
            );
            
            -- Enhanced filing tracking
            CREATE TABLE IF NOT EXISTS filing_tracking (
                filing_id INTEGER PRIMARY KEY,
                processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                digest_sent_to TEXT,       -- JSON array of channel IDs
                watchlist_matches TEXT,    -- JSON of matches per channel
                FOREIGN KEY (filing_id) REFERENCES filing(id)
            );
            
            -- Create indexes for performance
            CREATE INDEX IF NOT EXISTS idx_watchlist_channel ON channel_watchlist(channel_id);
            CREATE INDEX IF NOT EXISTS idx_aliases_name ON entity_aliases(alias_name);
            CREATE INDEX IF NOT EXISTS idx_digest_runs_channel_time ON digest_runs(channel_id, run_time);
            CREATE INDEX IF NOT EXISTS idx_filing_tracking_processed ON filing_tracking(processed_at);
            """
            )

            logger.info("Enhanced database schema ensured")

    def get_channel_settings(self, channel_id: str) -> Dict[str, Any]:
        """Get settings for a channel, creating defaults if needed."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM channel_settings WHERE id = ?", (channel_id,)
            )
            result = cursor.fetchone()

            if not result:
                # Create default settings
                defaults = {
                    "id": channel_id,
                    "threshold_filings": 10,
                    "threshold_amount": 100000,
                    "show_descriptions": True,
                    "created_at": datetime.now().isoformat(),
                }

                conn.execute(
                    """
                    INSERT INTO channel_settings 
                    (id, threshold_filings, threshold_amount, show_descriptions, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        channel_id,
                        defaults["threshold_filings"],
                        defaults["threshold_amount"],
                        defaults["show_descriptions"],
                        defaults["created_at"],
                    ),
                )

                return defaults

            return dict(result)

    def update_channel_setting(self, channel_id: str, key: str, value: Any) -> None:
        """Update a specific channel setting."""
        with self.get_connection() as conn:
            # Ensure channel exists
            self.get_channel_settings(channel_id)

            conn.execute(
                f"""
                UPDATE channel_settings 
                SET {key} = ?, updated_at = ?
                WHERE id = ?
            """,
                (value, datetime.now().isoformat(), channel_id),
            )

    def get_channel_watchlist(self, channel_id: str) -> List[Dict[str, Any]]:
        """Get watchlist for a channel."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM channel_watchlist 
                WHERE channel_id = ?
                ORDER BY created_at DESC
            """,
                (channel_id,),
            )

            return [dict(row) for row in cursor.fetchall()]

    def add_to_watchlist(
        self,
        channel_id: str,
        entity_type: str,
        watch_name: str,
        display_name: str = None,
        entity_id: int = None,
        fuzzy_score: float = 1.0,
    ) -> bool:
        """Add entity to channel watchlist."""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO channel_watchlist
                    (channel_id, entity_type, entity_id, watch_name, display_name, fuzzy_score)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        channel_id,
                        entity_type,
                        entity_id,
                        watch_name,
                        display_name or watch_name,
                        fuzzy_score,
                    ),
                )
                return True
        except sqlite3.Error as e:
            logger.error(f"Failed to add to watchlist: {e}")
            return False

    def remove_from_watchlist(self, channel_id: str, watch_name: str) -> bool:
        """Remove entity from channel watchlist."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM channel_watchlist 
                    WHERE channel_id = ? AND (watch_name = ? OR display_name = ?)
                """,
                    (channel_id, watch_name, watch_name),
                )
                return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Failed to remove from watchlist: {e}")
            return False

    def record_digest_run(
        self,
        channel_id: str,
        run_type: str,
        filings_count: int = 0,
        last_filing_time: str = None,
        digest_content: str = None,
    ) -> None:
        """Record a digest run for tracking."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO digest_runs
                (channel_id, run_type, run_time, filings_count, last_filing_time, digest_content)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    channel_id,
                    run_type,
                    datetime.now().isoformat(),
                    filings_count,
                    last_filing_time,
                    digest_content,
                ),
            )

    def get_last_digest_run(
        self, channel_id: str, run_type: str = None
    ) -> Optional[Dict[str, Any]]:
        """Get last digest run for a channel."""
        with self.get_connection() as conn:
            query = "SELECT * FROM digest_runs WHERE channel_id = ?"
            params = [channel_id]

            if run_type:
                query += " AND run_type = ?"
                params.append(run_type)

            query += " ORDER BY run_time DESC LIMIT 1"

            cursor = conn.execute(query, params)
            result = cursor.fetchone()
            return dict(result) if result else None

    def add_entity_alias(
        self,
        alias_name: str,
        canonical_name: str,
        entity_type: str,
        entity_id: int = None,
        confidence_score: float = 1.0,
    ) -> None:
        """Add or update entity alias mapping."""
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO entity_aliases
                (alias_name, canonical_name, entity_type, entity_id, confidence_score, updated_at, usage_count)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE((
                    SELECT usage_count + 1 FROM entity_aliases 
                    WHERE alias_name = ? AND entity_type = ?
                ), 1))
            """,
                (
                    alias_name.lower(),
                    canonical_name,
                    entity_type,
                    entity_id,
                    confidence_score,
                    datetime.now().isoformat(),
                    alias_name.lower(),
                    entity_type,
                ),
            )

    def find_entity_alias(
        self, alias_name: str, entity_type: str = None
    ) -> Optional[Dict[str, Any]]:
        """Find existing alias mapping."""
        with self.get_connection() as conn:
            query = "SELECT * FROM entity_aliases WHERE alias_name = ?"
            params = [alias_name.lower()]

            if entity_type:
                query += " AND entity_type = ?"
                params.append(entity_type)

            query += " ORDER BY confidence_score DESC, usage_count DESC LIMIT 1"

            cursor = conn.execute(query, params)
            result = cursor.fetchone()
            return dict(result) if result else None
