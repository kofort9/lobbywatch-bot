"""
LobbyLens Signals Database - Government activity signal storage and retrieval

This module handles signal database operations for both V1 (basic) and
V2 (enhanced) systems.

Architecture:
- V1: Basic signal storage (legacy)
- V2: Enhanced schema with priority scoring, urgency, and industry tagging
"""

# =============================================================================
# V2: Enhanced Signals Database (Current Active System)
# =============================================================================

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from bot.signals import SignalV2

try:
    import psycopg2
    import psycopg2.extras
except Exception:  # pragma: no cover - optional dependency
    psycopg2 = None  # type: ignore


class SignalsDatabaseV2:
    """Enhanced database manager for V2 signals.

    This is the current active system for signal storage.
    Features:
    - Enhanced schema with priority scoring and urgency
    - Industry tagging and watchlist hit tracking
    - Rich metadata storage with JSON fields
    - Deduplication support with stable IDs
    """

    def __init__(self, db_path: str = "signals.db"):
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create the enhanced signals table."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Create signals table with V2 fields
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS signal_event (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                ts TEXT NOT NULL,
                title TEXT NOT NULL,
                link TEXT NOT NULL,
                agency TEXT,
                committee TEXT,
                bill_id TEXT,
                rin TEXT,
                docket_id TEXT,
                issue_codes TEXT DEFAULT '[]',
                metric_json TEXT DEFAULT '{}',
                priority_score REAL DEFAULT 0.0,
                signal_type TEXT,
                urgency TEXT,
                watchlist_matches TEXT DEFAULT '[]',
                regs_object_id TEXT,
                regs_docket_id TEXT,
                comment_end_date TEXT,
                comments_24h INTEGER DEFAULT 0,
                comments_delta INTEGER DEFAULT 0,
                comment_surge INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source, source_id)
            )
            """
        )

        # Create indexes for performance
        cur.execute("CREATE INDEX IF NOT EXISTS idx_signal_ts ON signal_event(ts)")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_signal_priority "
            "ON signal_event(priority_score)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_signal_source ON signal_event(source)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_signal_agency ON signal_event(agency)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_signal_created ON signal_event(created_at)"
        )

        alter_statements = [
            "ALTER TABLE signal_event ADD COLUMN regs_object_id TEXT",
            "ALTER TABLE signal_event ADD COLUMN regs_docket_id TEXT",
            "ALTER TABLE signal_event ADD COLUMN comment_end_date TEXT",
            "ALTER TABLE signal_event ADD COLUMN comments_24h INTEGER DEFAULT 0",
            "ALTER TABLE signal_event ADD COLUMN comments_delta INTEGER DEFAULT 0",
            "ALTER TABLE signal_event ADD COLUMN comment_surge INTEGER DEFAULT 0",
        ]

        for statement in alter_statements:
            try:
                cur.execute(statement)
            except sqlite3.OperationalError as exc:
                if "duplicate column" in str(exc).lower():
                    continue
                raise

        # Watchlist and channel settings
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist_item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                term TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(channel_id, term)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS channel_settings (
                channel_id TEXT PRIMARY KEY,
                mini_digest_threshold INTEGER DEFAULT 10,
                high_priority_threshold REAL DEFAULT 5.0,
                surge_threshold REAL DEFAULT 200.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.commit()
        conn.close()

    def save_signals(self, signals: List[SignalV2]) -> int:
        """Save signals to database with deduplication."""
        if not signals:
            return 0

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        saved_count = 0

        for signal in signals:
            try:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO signal_event (
                        source, source_id, ts, title, link, agency, committee,
                        bill_id, rin, docket_id, issue_codes, metric_json,
                        priority_score, signal_type, urgency, watchlist_matches,
                        regs_object_id, regs_docket_id, comment_end_date,
                        comments_24h, comments_delta, comment_surge
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        json.dumps(signal.issue_codes),
                        json.dumps(signal.metrics),
                        signal.priority_score,
                        (signal.signal_type.value if signal.signal_type else None),
                        signal.urgency.value if signal.urgency else None,
                        json.dumps(signal.watchlist_matches),
                        signal.regs_object_id,
                        signal.regs_docket_id,
                        signal.comment_end_date,
                        signal.comments_24h or 0,
                        signal.comments_delta or 0,
                        1 if signal.comment_surge else 0,
                    ),
                )
                saved_count += 1
            except Exception as e:
                print(f"Error saving signal {signal.source_id}: {e}")
                continue

        conn.commit()
        conn.close()

        return saved_count

    def get_recent_signals(
        self, hours_back: int = 24, min_priority: float = 0.0
    ) -> List[SignalV2]:
        """Get recent signals from database."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(
            """
            SELECT * FROM signal_event
            WHERE ts >= ? AND priority_score >= ?
            ORDER BY priority_score DESC, ts DESC
            """,
            (cutoff_time.isoformat(), min_priority),
        )

        rows = cur.fetchall()
        conn.close()

        signals = []
        for row in rows:
            try:
                signal = self._row_to_signal(row)
                signals.append(signal)
            except Exception as e:
                print(f"Error converting row to signal: {e}")
                continue

        return signals

    def get_signals_by_source(
        self, source: str, hours_back: int = 24
    ) -> List[SignalV2]:
        """Get signals from specific source."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute(
            """
            SELECT * FROM signal_event
            WHERE source = ? AND ts >= ?
            ORDER BY ts DESC
            """,
            (source, cutoff_time.isoformat()),
        )

        rows = cur.fetchall()
        conn.close()

        signals = []
        for row in rows:
            try:
                signal = self._row_to_signal(row)
                signals.append(signal)
            except Exception as e:
                print(f"Error converting row to signal: {e}")
                continue

        return signals

    def get_watchlist_signals(
        self, watchlist: List[str], hours_back: int = 24
    ) -> List[SignalV2]:
        """Get signals that match watchlist entities."""
        if not watchlist:
            return []

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Build query for watchlist matches
        watchlist_conditions = []
        params = [cutoff_time.isoformat()]

        for entity in watchlist:
            watchlist_conditions.append("title LIKE ? OR agency LIKE ?")
            params.extend([f"%{entity}%", f"%{entity}%"])

        query = f"""
            SELECT * FROM signal_event
            WHERE ts >= ? AND ({' OR '.join(watchlist_conditions)})
            ORDER BY priority_score DESC, ts DESC
        """

        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        signals = []
        for row in rows:
            try:
                signal = self._row_to_signal(row)
                signals.append(signal)
            except Exception as e:
                print(f"Error converting row to signal: {e}")
                continue

        return signals

    def get_signals_by_issue_codes(
        self, issue_codes: List[str], hours_back: int = 24
    ) -> List[SignalV2]:
        """Get signals by issue codes."""
        if not issue_codes:
            return []

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Build query for issue code matches
        issue_conditions = []
        params = [cutoff_time.isoformat()]

        for code in issue_codes:
            issue_conditions.append("issue_codes LIKE ?")
            params.append(f'%"{code}"%')

        query = f"""
            SELECT * FROM signal_event
            WHERE ts >= ? AND ({' OR '.join(issue_conditions)})
            ORDER BY priority_score DESC, ts DESC
        """

        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        signals = []
        for row in rows:
            try:
                signal = self._row_to_signal(row)
                signals.append(signal)
            except Exception as e:
                print(f"Error converting row to signal: {e}")
                continue

        return signals

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Total signals
        cur.execute("SELECT COUNT(*) FROM signal_event")
        total_signals = cur.fetchone()[0]

        # Signals by source
        cur.execute(
            """
            SELECT source, COUNT(*) as count
            FROM signal_event
            GROUP BY source
            ORDER BY count DESC
        """
        )
        by_source = dict(cur.fetchall())

        # Recent signals (last 24h)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        cur.execute(
            "SELECT COUNT(*) FROM signal_event WHERE ts >= ?",
            (cutoff_time.isoformat(),),
        )
        recent_signals = cur.fetchone()[0]

        # High priority signals (last 24h)
        cur.execute(
            "SELECT COUNT(*) FROM signal_event WHERE ts >= ? AND priority_score >= 3.0",
            (cutoff_time.isoformat(),),
        )
        high_priority = cur.fetchone()[0]

        # Average priority score
        cur.execute(
            "SELECT AVG(priority_score) FROM signal_event WHERE ts >= ?",
            (cutoff_time.isoformat(),),
        )
        avg_priority = cur.fetchone()[0] or 0.0

        conn.close()

        return {
            "total_signals": total_signals,
            "recent_signals_24h": recent_signals,
            "high_priority_24h": high_priority,
            "average_priority": round(avg_priority, 2),
            "by_source": by_source,
        }

    def cleanup_old_signals(self, days_to_keep: int = 30) -> int:
        """Clean up old signals beyond retention period."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute("DELETE FROM signal_event WHERE ts < ?", (cutoff_time.isoformat(),))

        deleted_count = cur.rowcount
        conn.commit()
        conn.close()

        return deleted_count

    def _row_to_signal(self, row: sqlite3.Row) -> SignalV2:
        """Convert database row to SignalV2 object."""
        from bot.signals import SignalType, Urgency

        # Parse JSON fields
        issue_codes = json.loads(row["issue_codes"]) if row["issue_codes"] else []
        metrics = json.loads(row["metric_json"]) if row["metric_json"] else {}
        watchlist_matches = (
            json.loads(row["watchlist_matches"]) if row["watchlist_matches"] else []
        )

        # Parse timestamp
        timestamp = datetime.fromisoformat(row["ts"])

        # Parse enums
        signal_type = SignalType(row["signal_type"]) if row["signal_type"] else None
        urgency = Urgency(row["urgency"]) if row["urgency"] else None

        return SignalV2(
            source=row["source"],
            source_id=row["source_id"],
            timestamp=timestamp,
            title=row["title"],
            link=row["link"],
            agency=row["agency"],
            committee=row["committee"],
            bill_id=row["bill_id"],
            rin=row["rin"],
            docket_id=row["docket_id"],
            issue_codes=issue_codes,
            metrics=metrics,
            priority_score=row["priority_score"],
            deadline=row["comment_end_date"] or metrics.get("comment_end_date"),
            comment_end_date=row["comment_end_date"],
            comments_24h=row["comments_24h"],
            comments_delta=row["comments_delta"],
            comment_surge=bool(row["comment_surge"]),
            regs_object_id=row["regs_object_id"],
            regs_document_id=row["source_id"],
            regs_docket_id=row["regs_docket_id"],
            signal_type=signal_type,
            urgency=urgency,
            watchlist_matches=watchlist_matches,
            watchlist_hit=bool(watchlist_matches),
        )

    # Additional methods for web server compatibility
    def get_signal_stats(self) -> Dict[str, Any]:
        """Get signal statistics for web interface."""
        return self.get_database_stats()

    def add_watchlist_item(self, channel_id: str, term: str) -> bool:
        """Add a watchlist item."""
        if not channel_id or not term:
            return False

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        try:
            cur.execute(
                """
                INSERT OR IGNORE INTO watchlist_item (channel_id, term)
                VALUES (?, ?)
                """,
                (channel_id, term.strip()),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False
        finally:
            conn.close()

    def remove_watchlist_item(self, channel_id: str, term: str) -> bool:
        """Remove a watchlist item."""
        if not channel_id or not term:
            return False

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        try:
            cur.execute(
                """
                DELETE FROM watchlist_item
                WHERE channel_id = ? AND term = ?
                """,
                (channel_id, term.strip()),
            )
            conn.commit()
            return cur.rowcount > 0
        except Exception:
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_watchlist(self, channel_id: str) -> List[str]:
        """Get watchlist items for a channel."""
        if not channel_id:
            return []

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT term FROM watchlist_item
            WHERE channel_id = ?
            ORDER BY created_at DESC
            """,
            (channel_id,),
        )

        rows = cur.fetchall()
        conn.close()

        return [row[0] for row in rows]

    def update_channel_setting(self, channel_id: str, setting: str, value: Any) -> bool:
        """Update or insert a channel setting."""
        if setting not in {
            "mini_digest_threshold",
            "high_priority_threshold",
            "surge_threshold",
        }:
            return False

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        try:
            # Ensure row exists
            cur.execute(
                """
                INSERT OR IGNORE INTO channel_settings (channel_id)
                VALUES (?)
                """,
                (channel_id,),
            )

            cur.execute(
                f"""
                UPDATE channel_settings
                SET {setting} = ?, updated_at = CURRENT_TIMESTAMP
                WHERE channel_id = ?
                """,
                (value, channel_id),
            )
            conn.commit()
            return cur.rowcount > 0
        except Exception:
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_channel_settings(self, channel_id: str) -> Dict[str, Any]:
        """Get channel settings with defaults when missing."""
        defaults: Dict[str, Any] = {
            "mini_digest_threshold": 10,
            "high_priority_threshold": 5.0,
            "surge_threshold": 200.0,
        }

        if not channel_id:
            return defaults

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT mini_digest_threshold, high_priority_threshold, surge_threshold
            FROM channel_settings
            WHERE channel_id = ?
            """,
            (channel_id,),
        )
        row = cur.fetchone()
        conn.close()

        if not row:
            return defaults

        return {
            "mini_digest_threshold": row[0],
            "high_priority_threshold": row[1],
            "surge_threshold": row[2],
        }

    def health_check(self) -> Dict[str, Any]:
        """Perform a simple database health check."""
        try:
            conn = sqlite3.connect(self.db_path, timeout=2)
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            conn.close()
            return {"database": "ok"}
        except Exception as exc:
            return {"database": "error", "detail": str(exc)}


# -----------------------------------------------------------------------------
# Postgres implementation for production
# -----------------------------------------------------------------------------


class SignalsDatabasePG(SignalsDatabaseV2):
    """PostgreSQL-backed signals database (subset of methods used today)."""

    def __init__(self, database_url: str):
        if not psycopg2:
            raise RuntimeError("psycopg2 is required for PostgreSQL backend")
        self.database_url = database_url
        self._ensure_schema_pg()

    def _conn(self):
        return psycopg2.connect(
            self.database_url, cursor_factory=psycopg2.extras.RealDictCursor
        )

    def _ensure_schema_pg(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS signal_event (
            id SERIAL PRIMARY KEY,
            source TEXT NOT NULL,
            source_id TEXT NOT NULL,
            ts TIMESTAMPTZ NOT NULL,
            title TEXT NOT NULL,
            link TEXT NOT NULL,
            agency TEXT,
            committee TEXT,
            bill_id TEXT,
            rin TEXT,
            docket_id TEXT,
            issue_codes JSONB DEFAULT '[]',
            metric_json JSONB DEFAULT '{}',
            priority_score REAL DEFAULT 0.0,
            signal_type TEXT,
            urgency TEXT,
            watchlist_matches JSONB DEFAULT '[]',
            regs_object_id TEXT,
            regs_docket_id TEXT,
            comment_end_date TEXT,
            comments_24h INTEGER DEFAULT 0,
            comments_delta INTEGER DEFAULT 0,
            comment_surge BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source, source_id)
        );

        CREATE TABLE IF NOT EXISTS watchlist_item (
            id SERIAL PRIMARY KEY,
            channel_id TEXT NOT NULL,
            term TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(channel_id, term)
        );

        CREATE TABLE IF NOT EXISTS channel_settings (
            channel_id TEXT PRIMARY KEY,
            mini_digest_threshold INTEGER DEFAULT 10,
            high_priority_threshold REAL DEFAULT 5.0,
            surge_threshold REAL DEFAULT 200.0,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_signal_ts ON signal_event(ts);
        CREATE INDEX IF NOT EXISTS idx_signal_priority ON signal_event(priority_score);
        CREATE INDEX IF NOT EXISTS idx_signal_source ON signal_event(source);
        CREATE INDEX IF NOT EXISTS idx_signal_agency ON signal_event(agency);
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()

    def save_signals(self, signals: List[SignalV2]) -> int:
        if not signals:
            return 0
        saved = 0
        with self._conn() as conn:
            with conn.cursor() as cur:
                for signal in signals:
                    try:
                        cur.execute(
                            """
                            INSERT INTO signal_event (
                                source, source_id, ts, title, link, agency, committee,
                                bill_id, rin, docket_id, issue_codes, metric_json,
                                priority_score, signal_type, urgency, watchlist_matches,
                                regs_object_id, regs_docket_id, comment_end_date,
                                comments_24h, comments_delta, comment_surge
                            )
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (source, source_id) DO UPDATE SET
                                ts = EXCLUDED.ts,
                                title = EXCLUDED.title,
                                link = EXCLUDED.link,
                                agency = EXCLUDED.agency,
                                committee = EXCLUDED.committee,
                                bill_id = EXCLUDED.bill_id,
                                rin = EXCLUDED.rin,
                                docket_id = EXCLUDED.docket_id,
                                issue_codes = EXCLUDED.issue_codes,
                                metric_json = EXCLUDED.metric_json,
                                priority_score = EXCLUDED.priority_score,
                                signal_type = EXCLUDED.signal_type,
                                urgency = EXCLUDED.urgency,
                                watchlist_matches = EXCLUDED.watchlist_matches,
                                regs_object_id = EXCLUDED.regs_object_id,
                                regs_docket_id = EXCLUDED.regs_docket_id,
                                comment_end_date = EXCLUDED.comment_end_date,
                                comments_24h = EXCLUDED.comments_24h,
                                comments_delta = EXCLUDED.comments_delta,
                                comment_surge = EXCLUDED.comment_surge
                            """,
                            (
                                signal.source,
                                signal.source_id,
                                signal.timestamp,
                                signal.title,
                                signal.link,
                                signal.agency,
                                signal.committee,
                                signal.bill_id,
                                signal.rin,
                                signal.docket_id,
                                psycopg2.extras.Json(signal.issue_codes),
                                psycopg2.extras.Json(signal.metrics),
                                signal.priority_score,
                                (
                                    signal.signal_type.value
                                    if signal.signal_type
                                    else None
                                ),
                                signal.urgency.value if signal.urgency else None,
                                psycopg2.extras.Json(signal.watchlist_matches),
                                signal.regs_object_id,
                                signal.regs_docket_id,
                                signal.comment_end_date,
                                signal.comments_24h or 0,
                                signal.comments_delta or 0,
                                bool(signal.comment_surge),
                            ),
                        )
                        saved += 1
                    except Exception:
                        conn.rollback()
                        continue
            conn.commit()
        return saved

    def get_recent_signals(
        self, hours_back: int = 24, min_priority: float = 0.0
    ) -> List[SignalV2]:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM signal_event
                    WHERE ts >= %s AND priority_score >= %s
                    ORDER BY priority_score DESC, ts DESC
                    """,
                    (cutoff_time, min_priority),
                )
                rows = cur.fetchall()
        signals: List[SignalV2] = []
        for row in rows:
            try:
                signals.append(self._row_to_signal_pg(row))
            except Exception:
                continue
        return signals

    def get_database_stats(self) -> Dict[str, Any]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM signal_event")
                total_signals = cur.fetchone()["count"]

                cur.execute(
                    "SELECT source, COUNT(*) as count FROM signal_event GROUP BY source"
                )
                by_source = {row["source"]: row["count"] for row in cur.fetchall()}

                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
                cur.execute(
                    "SELECT COUNT(*) FROM signal_event WHERE ts >= %s",
                    (cutoff_time,),
                )
                recent_signals = cur.fetchone()["count"]

                cur.execute(
                    "SELECT COUNT(*) FROM signal_event WHERE ts >= %s AND priority_score >= 3.0",
                    (cutoff_time,),
                )
                high_priority = cur.fetchone()["count"]

                cur.execute(
                    "SELECT AVG(priority_score) FROM signal_event WHERE ts >= %s",
                    (cutoff_time,),
                )
                avg_priority = cur.fetchone()["avg"]

        return {
            "total_signals": total_signals,
            "recent_signals_24h": recent_signals,
            "high_priority_24h": high_priority,
            "average_priority": round(avg_priority or 0.0, 2),
            "by_source": by_source,
        }

    def add_watchlist_item(self, channel_id: str, term: str) -> bool:
        if not channel_id or not term:
            return False
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO watchlist_item (channel_id, term)
                    VALUES (%s, %s)
                    ON CONFLICT (channel_id, term) DO NOTHING
                    """,
                    (channel_id, term.strip()),
                )
            conn.commit()
        return True

    def remove_watchlist_item(self, channel_id: str, term: str) -> bool:
        if not channel_id or not term:
            return False
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM watchlist_item WHERE channel_id = %s AND term = %s",
                    (channel_id, term.strip()),
                )
                deleted = cur.rowcount
            conn.commit()
        return deleted > 0

    def get_watchlist(self, channel_id: str) -> List[str]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT term FROM watchlist_item WHERE channel_id = %s ORDER BY created_at DESC",
                    (channel_id,),
                )
                rows = cur.fetchall()
        return [row["term"] for row in rows]

    def update_channel_setting(self, channel_id: str, setting: str, value: Any) -> bool:
        if setting not in {
            "mini_digest_threshold",
            "high_priority_threshold",
            "surge_threshold",
        }:
            return False
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO channel_settings (channel_id)
                    VALUES (%s)
                    ON CONFLICT (channel_id) DO NOTHING
                    """,
                    (channel_id,),
                )
                cur.execute(
                    f"""
                    UPDATE channel_settings
                    SET {setting} = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE channel_id = %s
                    """,
                    (value, channel_id),
                )
            conn.commit()
        return True

    def get_channel_settings(self, channel_id: str) -> Dict[str, Any]:
        defaults: Dict[str, Any] = {
            "mini_digest_threshold": 10,
            "high_priority_threshold": 5.0,
            "surge_threshold": 200.0,
        }
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT mini_digest_threshold, high_priority_threshold, surge_threshold
                    FROM channel_settings
                    WHERE channel_id = %s
                    """,
                    (channel_id,),
                )
                row = cur.fetchone()
        if not row:
            return defaults
        return {
            "mini_digest_threshold": row["mini_digest_threshold"],
            "high_priority_threshold": row["high_priority_threshold"],
            "surge_threshold": row["surge_threshold"],
        }

    def health_check(self) -> Dict[str, Any]:
        try:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return {"database": "ok", "backend": "postgres"}
        except Exception as exc:
            return {"database": "error", "backend": "postgres", "detail": str(exc)}

    def _row_to_signal_pg(self, row: Any) -> SignalV2:
        from bot.signals import SignalType, Urgency

        issue_codes = row["issue_codes"] or []
        metrics = row["metric_json"] or {}
        watchlist_matches = row["watchlist_matches"] or []
        timestamp = row["ts"]
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        signal_type = SignalType(row["signal_type"]) if row.get("signal_type") else None
        urgency = Urgency(row["urgency"]) if row.get("urgency") else None
        return SignalV2(
            source=row["source"],
            source_id=row["source_id"],
            timestamp=timestamp,
            title=row["title"],
            link=row["link"],
            agency=row["agency"],
            committee=row["committee"],
            bill_id=row["bill_id"],
            rin=row["rin"],
            docket_id=row["docket_id"],
            issue_codes=issue_codes,
            metrics=metrics,
            priority_score=row["priority_score"],
            deadline=row.get("comment_end_date") or metrics.get("comment_end_date"),
            comment_end_date=row.get("comment_end_date"),
            comments_24h=row.get("comments_24h"),
            comments_delta=row.get("comments_delta"),
            comment_surge=bool(row.get("comment_surge")),
            regs_object_id=row.get("regs_object_id"),
            regs_document_id=row.get("source_id"),
            regs_docket_id=row.get("regs_docket_id"),
            signal_type=signal_type,
            urgency=urgency,
            watchlist_matches=watchlist_matches,
            watchlist_hit=bool(watchlist_matches),
        )


# =============================================================================
# V1: Basic Signals Database (Legacy - Maintained for Compatibility)
# =============================================================================


class LegacySignalsDatabase:
    """Legacy V1 signals database (deprecated).

    This is maintained for backward compatibility only.
    New code should use SignalsDatabaseV2 above.
    """

    def __init__(self, db_path: str = "signals.db"):
        self.db_path = db_path
        import logging

        logging.warning(
            "Using legacy V1 SignalsDatabase. Consider upgrading to SignalsDatabaseV2."
        )

    def save_signals(self, signals: List[Dict]) -> int:
        """Legacy signal saving (deprecated)."""
        import logging

        logging.warning("Legacy save_signals called. Use V2 SignalsDatabaseV2 instead.")
        return 0

    def get_recent_signals(self, hours_back: int = 24) -> List[Dict]:
        """Legacy signal retrieval (deprecated)."""
        import logging

        logging.warning(
            "Legacy get_recent_signals called. Use V2 SignalsDatabaseV2 instead."
        )
        return []


# =============================================================================
# Public API - Use V2 by default
# =============================================================================

# Export V2 as the default
SignalsDatabase = SignalsDatabaseV2  # For backward compatibility


def create_signals_database(database_url: Optional[str] = None) -> SignalsDatabaseV2:
    """Factory to create appropriate signals database backend."""
    if database_url and database_url.startswith("postgres"):
        try:
            return SignalsDatabasePG(database_url)
        except Exception as exc:
            logging.warning(
                "Failed to connect to Postgres backend (%s); falling back to SQLite. Detail: %s",
                database_url,
                exc,
            )
    return SignalsDatabaseV2()
