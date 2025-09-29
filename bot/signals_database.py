"""
LobbyLens Signals Database - Government activity signal storage and retrieval

This module handles signal database operations for both V1 (basic) and V2 (enhanced) systems.

Architecture:
- V1: Basic signal storage (legacy)
- V2: Enhanced schema with priority scoring, urgency, and industry tagging
"""

# =============================================================================
# V2: Enhanced Signals Database (Current Active System)
# =============================================================================

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from bot.signals import SignalV2


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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source, source_id)
            )
            """
        )

        # Create indexes for performance
        cur.execute("CREATE INDEX IF NOT EXISTS idx_signal_ts ON signal_event(ts)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_signal_priority ON signal_event(priority_score)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_signal_source ON signal_event(source)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_signal_agency ON signal_event(agency)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_signal_created ON signal_event(created_at)")

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
                        priority_score, signal_type, urgency, watchlist_matches
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        signal.signal_type.value if signal.signal_type else None,
                        signal.urgency.value if signal.urgency else None,
                        json.dumps(signal.watchlist_matches),
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
        cur.execute("""
            SELECT source, COUNT(*) as count 
            FROM signal_event 
            GROUP BY source 
            ORDER BY count DESC
        """)
        by_source = dict(cur.fetchall())

        # Recent signals (last 24h)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        cur.execute(
            "SELECT COUNT(*) FROM signal_event WHERE ts >= ?",
            (cutoff_time.isoformat(),)
        )
        recent_signals = cur.fetchone()[0]

        # High priority signals (last 24h)
        cur.execute(
            "SELECT COUNT(*) FROM signal_event WHERE ts >= ? AND priority_score >= 3.0",
            (cutoff_time.isoformat(),)
        )
        high_priority = cur.fetchone()[0]

        # Average priority score
        cur.execute("SELECT AVG(priority_score) FROM signal_event WHERE ts >= ?", 
                   (cutoff_time.isoformat(),))
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

        cur.execute(
            "DELETE FROM signal_event WHERE ts < ?",
            (cutoff_time.isoformat(),)
        )

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
        watchlist_matches = json.loads(row["watchlist_matches"]) if row["watchlist_matches"] else []

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
            signal_type=signal_type,
            urgency=urgency,
            watchlist_matches=watchlist_matches,
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
        logging.warning("Using legacy V1 SignalsDatabase. Consider upgrading to SignalsDatabaseV2.")
    
    def save_signals(self, signals: List[Dict]) -> int:
        """Legacy signal saving (deprecated)."""
        import logging
        logging.warning("Legacy save_signals called. Use V2 SignalsDatabaseV2 instead.")
        return 0
    
    def get_recent_signals(self, hours_back: int = 24) -> List[Dict]:
        """Legacy signal retrieval (deprecated)."""
        import logging
        logging.warning("Legacy get_recent_signals called. Use V2 SignalsDatabaseV2 instead.")
        return []


# =============================================================================
# Public API - Use V2 by default
# =============================================================================

# Export V2 as the default
SignalsDatabase = SignalsDatabaseV2  # For backward compatibility
