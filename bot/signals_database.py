"""Database operations for daily signals."""

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from .daily_signals import SignalEvent

logger = logging.getLogger(__name__)


class SignalsDatabase:
    """Database operations for signal events."""

    def __init__(self, db_manager: Any) -> None:
        self.db_manager = db_manager
        self._ensure_signals_schema()

    def _ensure_signals_schema(self) -> None:
        """Ensure the signals schema exists."""
        conn = self.db_manager.get_connection()

        # Signal events table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signal_event (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                agency TEXT,
                committee TEXT,
                bill_id TEXT,
                rin TEXT,
                docket_id TEXT,
                issue_codes TEXT,  -- JSON array
                metric_json TEXT,  -- JSON object
                priority_score REAL DEFAULT 0.0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source, source_id)
            )
        """
        )

        # Entity aliases for fuzzy matching
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS entity_alias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id INTEGER,
                alias_text TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entity_id) REFERENCES entity(id)
            )
        """
        )

        # ID mapping for cross-references
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS id_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id INTEGER,
                cik TEXT,
                fec_id TEXT,
                ticker TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entity_id) REFERENCES entity(id)
            )
        """
        )

        # Indexes for performance
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_signal_timestamp ON signal_event(timestamp)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_signal_source ON signal_event(source)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_signal_priority ON signal_event(priority_score)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alias_text ON entity_alias(alias_text)"
        )

        conn.commit()
        logger.info("Signals database schema ensured")

    def store_signals(self, signals: List[SignalEvent]) -> int:
        """Store signal events in the database."""
        if not signals:
            return 0

        conn = self.db_manager.get_connection()
        stored_count = 0

        for signal in signals:
            try:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO signal_event 
                    (source, source_id, timestamp, title, link, agency, committee, 
                     bill_id, rin, docket_id, issue_codes, metric_json, priority_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        signal.source,
                        signal.source_id,
                        signal.timestamp.isoformat(),
                        signal.title,
                        signal.link,
                        signal.agency,
                        signal.committee,
                        signal.bill_id,
                        signal.rin,
                        signal.docket_id,
                        str(signal.issue_codes),  # Convert list to string for storage
                        str(signal.metric_json),  # Convert dict to string for storage
                        signal.priority_score,
                    ),
                )
                stored_count += 1
            except Exception as e:
                logger.error(f"Failed to store signal {signal.source_id}: {e}")

        conn.commit()
        logger.info(f"Stored {stored_count} signal events")
        return stored_count

    def get_recent_signals(
        self, hours_back: int = 24, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent signal events."""
        conn = self.db_manager.get_connection()

        since_time = (
            datetime.now(timezone.utc) - timedelta(hours=hours_back)
        ).isoformat()

        cursor = conn.execute(
            """
            SELECT * FROM signal_event 
            WHERE timestamp >= ? 
            ORDER BY priority_score DESC, timestamp DESC 
            LIMIT ?
        """,
            (since_time, limit),
        )

        signals = []
        for row in cursor.fetchall():
            signal = dict(row)
            # Parse JSON fields
            try:
                signal["issue_codes"] = (
                    eval(signal["issue_codes"]) if signal["issue_codes"] else []
                )
                signal["metric_json"] = (
                    eval(signal["metric_json"]) if signal["metric_json"] else {}
                )
            except:
                signal["issue_codes"] = []
                signal["metric_json"] = {}

            signals.append(signal)

        return signals

    def get_signals_by_issue(
        self, issue_code: str, hours_back: int = 24
    ) -> List[Dict[str, Any]]:
        """Get signals filtered by issue code."""
        conn = self.db_manager.get_connection()

        since_time = (
            datetime.now(timezone.utc) - timedelta(hours=hours_back)
        ).isoformat()

        cursor = conn.execute(
            """
            SELECT * FROM signal_event 
            WHERE timestamp >= ? AND issue_codes LIKE ?
            ORDER BY priority_score DESC, timestamp DESC
        """,
            (since_time, f"%{issue_code}%"),
        )

        signals = []
        for row in cursor.fetchall():
            signal = dict(row)
            try:
                signal["issue_codes"] = (
                    eval(signal["issue_codes"]) if signal["issue_codes"] else []
                )
                signal["metric_json"] = (
                    eval(signal["metric_json"]) if signal["metric_json"] else {}
                )
            except:
                signal["issue_codes"] = []
                signal["metric_json"] = {}

            signals.append(signal)

        return signals

    def get_comment_surges(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """Get signals with comment surges."""
        conn = self.db_manager.get_connection()

        since_time = (
            datetime.now(timezone.utc) - timedelta(hours=hours_back)
        ).isoformat()

        cursor = conn.execute(
            """
            SELECT * FROM signal_event 
            WHERE timestamp >= ? AND metric_json LIKE '%comment_surge%'
            ORDER BY priority_score DESC, timestamp DESC
        """,
            (since_time,),
        )

        signals = []
        for row in cursor.fetchall():
            signal = dict(row)
            try:
                signal["issue_codes"] = (
                    eval(signal["issue_codes"]) if signal["issue_codes"] else []
                )
                signal["metric_json"] = (
                    eval(signal["metric_json"]) if signal["metric_json"] else {}
                )
            except:
                signal["issue_codes"] = []
                signal["metric_json"] = {}

            signals.append(signal)

        return signals

    def add_entity_alias(
        self, entity_id: int, alias_text: str, source: str, confidence: float = 1.0
    ) -> bool:
        """Add an entity alias for fuzzy matching."""
        conn = self.db_manager.get_connection()

        try:
            conn.execute(
                """
                INSERT INTO entity_alias (entity_id, alias_text, source, confidence)
                VALUES (?, ?, ?, ?)
            """,
                (entity_id, alias_text, source, confidence),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to add entity alias: {e}")
            return False

    def find_entity_by_alias(self, alias_text: str) -> List[Dict[str, Any]]:
        """Find entities by alias text."""
        conn = self.db_manager.get_connection()

        cursor = conn.execute(
            """
            SELECT ea.*, e.name, e.type 
            FROM entity_alias ea
            JOIN entity e ON e.id = ea.entity_id
            WHERE ea.alias_text LIKE ?
            ORDER BY ea.confidence DESC
        """,
            (f"%{alias_text}%",),
        )

        return [dict(row) for row in cursor.fetchall()]

    def cleanup_old_signals(self, days_to_keep: int = 30) -> int:
        """Clean up old signal events to prevent database bloat."""
        conn = self.db_manager.get_connection()

        cutoff_time = (
            datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        ).isoformat()

        cursor = conn.execute(
            "DELETE FROM signal_event WHERE timestamp < ?", (cutoff_time,)
        )
        deleted_count = cursor.rowcount

        conn.commit()
        logger.info(f"Cleaned up {deleted_count} old signal events")
        return int(deleted_count)
