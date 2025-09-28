"""
LobbyLens Signals Database v2 - Enhanced schema for v2 signals
Supports the new signal model with priority scoring, urgency, and industry tagging.
"""

# import json  # Unused import
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from bot.signals_v2 import SignalV2


class SignalsDatabaseV2:
    """Enhanced database manager for v2 signals"""

    def __init__(self, db_path: str = "signals_v2.db"):
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create the enhanced signals table"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Create signals table with v2 fields
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS signals_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                stable_id TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                summary TEXT,
                url TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                issue_codes TEXT DEFAULT '[]',
                bill_id TEXT,
                action_type TEXT,
                agency TEXT,
                comment_count INTEGER,
                deadline TEXT,
                metric_json TEXT,
                signal_type TEXT,
                urgency TEXT,
                priority_score REAL DEFAULT 0.0,
                industry_tag TEXT,
                watchlist_hit BOOLEAN DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create indexes for performance
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_signals_source ON signals_v2(source)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals_v2(timestamp)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_signals_priority ON signals_v2(priority_score)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_signals_urgency ON signals_v2(urgency)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_signals_industry ON signals_v2(industry_tag)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_signals_watchlist ON signals_v2(watchlist_hit)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_signals_bill_id ON signals_v2(bill_id)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_signals_stable_id ON signals_v2(stable_id)"
        )

        # Create watchlist table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS watchlist_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                entity_type TEXT DEFAULT 'entity',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(channel_id, entity_name)
            )
        """
        )

        # Create channel settings table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS channel_settings_v2 (
                channel_id TEXT PRIMARY KEY,
                mini_digest_threshold INTEGER DEFAULT 10,
                high_priority_threshold REAL DEFAULT 5.0,
                surge_threshold REAL DEFAULT 200.0,
                show_summaries BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        conn.commit()
        conn.close()

    def store_signal(self, signal: SignalV2) -> bool:
        """Store a signal in the database"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        try:
            # Convert signal to dict
            signal_data = signal.to_dict()

            # Insert or update signal
            cur.execute(
                """
                INSERT OR REPLACE INTO signals_v2 (
                    source, stable_id, title, summary, url, timestamp, issue_codes,
                    bill_id, action_type, agency, comment_count, deadline, metric_json,
                    signal_type, urgency, priority_score, industry_tag, watchlist_hit,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    signal_data["source"],
                    signal_data["stable_id"],
                    signal_data["title"],
                    signal_data["summary"],
                    signal_data["url"],
                    signal_data["timestamp"],
                    signal_data["issue_codes"],
                    signal_data["bill_id"],
                    signal_data["action_type"],
                    signal_data["agency"],
                    signal_data["comment_count"],
                    signal_data["deadline"],
                    signal_data["metric_json"],
                    signal_data["signal_type"],
                    signal_data["urgency"],
                    signal_data["priority_score"],
                    signal_data["industry_tag"],
                    signal_data["watchlist_hit"],
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

            conn.commit()
            return True

        except Exception as e:
            print(f"Error storing signal: {e}")
            return False
        finally:
            conn.close()

    def store_signals(self, signals: List[SignalV2]) -> int:
        """Store multiple signals in the database"""
        stored_count = 0
        for signal in signals:
            if self.store_signal(signal):
                stored_count += 1
        return stored_count

    def get_recent_signals(self, hours_back: int = 24) -> List[SignalV2]:
        """Get signals from the last N hours"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        since_time = (
            datetime.now(timezone.utc) - timedelta(hours=hours_back)
        ).isoformat()

        cur.execute(
            """
            SELECT * FROM signals_v2
            WHERE timestamp >= ?
            ORDER BY priority_score DESC, timestamp DESC
        """,
            (since_time,),
        )

        rows = cur.fetchall()
        conn.close()

        # Convert rows to SignalV2 objects
        signals = []
        for row in rows:
            signal_data = dict(zip([col[0] for col in cur.description], row))
            try:
                signal = SignalV2.from_dict(signal_data)
                signals.append(signal)
            except Exception as e:
                print(f"Error parsing signal: {e}")
                continue

        return signals

    def get_high_priority_signals(self, threshold: float = 5.0) -> List[SignalV2]:
        """Get signals above priority threshold"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT * FROM signals_v2
            WHERE priority_score >= ?
            ORDER BY priority_score DESC, timestamp DESC
        """,
            (threshold,),
        )

        rows = cur.fetchall()
        conn.close()

        signals = []
        for row in rows:
            signal_data = dict(zip([col[0] for col in cur.description], row))
            try:
                signal = SignalV2.from_dict(signal_data)
                signals.append(signal)
            except Exception as e:
                print(f"Error parsing signal: {e}")
                continue

        return signals

    def get_watchlist_signals(self, channel_id: str) -> List[SignalV2]:
        """Get signals that match channel watchlist"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Get watchlist items for channel
        cur.execute(
            """
            SELECT entity_name FROM watchlist_v2
            WHERE channel_id = ?
        """,
            (channel_id,),
        )

        watchlist_items = [row[0] for row in cur.fetchall()]

        if not watchlist_items:
            conn.close()
            return []

        # Get signals that match watchlist
        signals = []
        for item in watchlist_items:
            cur.execute(
                """
                SELECT * FROM signals_v2
                WHERE (title LIKE ? OR summary LIKE ? OR agency LIKE ?)
                AND timestamp >= ?
                ORDER BY priority_score DESC
            """,
                (
                    f"%{item}%",
                    f"%{item}%",
                    f"%{item}%",
                    (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
                ),
            )

            rows = cur.fetchall()
            for row in rows:
                signal_data = dict(zip([col[0] for col in cur.description], row))
                try:
                    signal = SignalV2.from_dict(signal_data)
                    signal.watchlist_hit = True
                    signals.append(signal)
                except Exception as e:
                    print(f"Error parsing signal: {e}")
                    continue

        conn.close()
        return signals

    def get_docket_surges(self, threshold: float = 200.0) -> List[SignalV2]:
        """Get docket signals with surge activity"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT * FROM signals_v2
            WHERE signal_type = 'docket'
            AND metric_json IS NOT NULL
            AND json_extract(metric_json, '$.comments_24h_delta_pct') >= ?
            ORDER BY json_extract(metric_json, '$.comments_24h_delta_pct') DESC
        """,
            (threshold,),
        )

        rows = cur.fetchall()
        conn.close()

        signals = []
        for row in rows:
            signal_data = dict(zip([col[0] for col in cur.description], row))
            try:
                signal = SignalV2.from_dict(signal_data)
                signals.append(signal)
            except Exception as e:
                print(f"Error parsing signal: {e}")
                continue

        return signals

    def get_deadline_signals(self, days_ahead: int = 7) -> List[SignalV2]:
        """Get signals with deadlines in next N days"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        now = datetime.now(timezone.utc)
        future_deadline = (now + timedelta(days=days_ahead)).isoformat()

        cur.execute(
            """
            SELECT * FROM signals_v2
            WHERE deadline IS NOT NULL
            AND deadline >= ?
            AND deadline <= ?
            ORDER BY deadline ASC
        """,
            (now.isoformat(), future_deadline),
        )

        rows = cur.fetchall()
        conn.close()

        signals = []
        for row in rows:
            signal_data = dict(zip([col[0] for col in cur.description], row))
            try:
                signal = SignalV2.from_dict(signal_data)
                signals.append(signal)
            except Exception as e:
                print(f"Error parsing signal: {e}")
                continue

        return signals

    def get_industry_signals(self, industry: str, limit: int = 2) -> List[SignalV2]:
        """Get top signals for a specific industry"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT * FROM signals_v2
            WHERE industry_tag = ?
            AND timestamp >= ?
            ORDER BY priority_score DESC
            LIMIT ?
        """,
            (
                industry,
                (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
                limit,
            ),
        )

        rows = cur.fetchall()
        conn.close()

        signals = []
        for row in rows:
            signal_data = dict(zip([col[0] for col in cur.description], row))
            try:
                signal = SignalV2.from_dict(signal_data)
                signals.append(signal)
            except Exception as e:
                print(f"Error parsing signal: {e}")
                continue

        return signals

    def add_watchlist_item(
        self, channel_id: str, entity_name: str, entity_type: str = "entity"
    ) -> bool:
        """Add item to channel watchlist"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        try:
            cur.execute(
                """
                INSERT OR IGNORE INTO watchlist_v2 (channel_id, entity_name, entity_type)
                VALUES (?, ?, ?)
            """,
                (channel_id, entity_name, entity_type),
            )

            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding watchlist item: {e}")
            return False
        finally:
            conn.close()

    def remove_watchlist_item(self, channel_id: str, entity_name: str) -> bool:
        """Remove item from channel watchlist"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        try:
            cur.execute(
                """
                DELETE FROM watchlist_v2
                WHERE channel_id = ? AND entity_name = ?
            """,
                (channel_id, entity_name),
            )

            conn.commit()
            return True
        except Exception as e:
            print(f"Error removing watchlist item: {e}")
            return False
        finally:
            conn.close()

    def get_watchlist(self, channel_id: str) -> List[Dict[str, str]]:
        """Get channel watchlist"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT entity_name, entity_type FROM watchlist_v2
            WHERE channel_id = ?
            ORDER BY created_at DESC
        """,
            (channel_id,),
        )

        rows = cur.fetchall()
        conn.close()

        return [{"name": row[0], "type": row[1]} for row in rows]

    def update_channel_setting(self, channel_id: str, setting: str, value: Any) -> bool:
        """Update channel setting"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        try:
            # Ensure channel settings exist
            cur.execute(
                """
                INSERT OR IGNORE INTO channel_settings_v2 (channel_id)
                VALUES (?)
            """,
                (channel_id,),
            )

            # Update setting
            cur.execute(
                f"""
                UPDATE channel_settings_v2
                SET {setting} = ?, updated_at = ?
                WHERE channel_id = ?
            """,
                (value, datetime.now(timezone.utc).isoformat(), channel_id),
            )

            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating channel setting: {e}")
            return False
        finally:
            conn.close()

    def get_channel_settings(self, channel_id: str) -> Dict[str, Any]:
        """Get channel settings"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT * FROM channel_settings_v2
            WHERE channel_id = ?
        """,
            (channel_id,),
        )

        row = cur.fetchone()
        conn.close()

        if row:
            return dict(zip([col[0] for col in cur.description], row))
        else:
            # Return defaults
            return {
                "channel_id": channel_id,
                "mini_digest_threshold": 10,
                "high_priority_threshold": 5.0,
                "surge_threshold": 200.0,
                "show_summaries": True,
            }

    def cleanup_old_signals(self, days_old: int = 30) -> int:
        """Clean up old signals"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cutoff_time = (
            datetime.now(timezone.utc) - timedelta(days=days_old)
        ).isoformat()

        cur.execute(
            """
            DELETE FROM signals_v2
            WHERE timestamp < ?
        """,
            (cutoff_time,),
        )

        deleted_count = cur.rowcount
        conn.commit()
        conn.close()

        return deleted_count

    def get_signal_stats(self) -> Dict[str, Any]:
        """Get signal statistics"""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Total signals
        cur.execute("SELECT COUNT(*) FROM signals_v2")
        total_signals = cur.fetchone()[0]

        # Signals by source
        cur.execute(
            """
            SELECT source, COUNT(*) FROM signals_v2
            GROUP BY source
        """
        )
        by_source = dict(cur.fetchall())

        # Signals by urgency
        cur.execute(
            """
            SELECT urgency, COUNT(*) FROM signals_v2
            WHERE urgency IS NOT NULL
            GROUP BY urgency
        """
        )
        by_urgency = dict(cur.fetchall())

        # Signals by industry
        cur.execute(
            """
            SELECT industry_tag, COUNT(*) FROM signals_v2
            WHERE industry_tag IS NOT NULL
            GROUP BY industry_tag
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """
        )
        by_industry = dict(cur.fetchall())

        # High priority signals
        cur.execute("SELECT COUNT(*) FROM signals_v2 WHERE priority_score >= 5.0")
        high_priority = cur.fetchone()[0]

        # Watchlist hits
        cur.execute("SELECT COUNT(*) FROM signals_v2 WHERE watchlist_hit = 1")
        watchlist_hits = cur.fetchone()[0]

        conn.close()

        return {
            "total_signals": total_signals,
            "by_source": by_source,
            "by_urgency": by_urgency,
            "by_industry": by_industry,
            "high_priority": high_priority,
            "watchlist_hits": watchlist_hits,
        }
