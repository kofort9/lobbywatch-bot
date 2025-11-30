#!/usr/bin/env python3
"""Test script to preview the digest with real data from the database."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List

from bot.digest import DigestFormatter
from bot.signals import SignalType, SignalV2


def load_signals_from_db() -> List[SignalV2]:
    """Load signals directly from the SQLite database."""
    fixtures_dir = Path(__file__).resolve().parent / "tests" / "fixtures"
    db_path = fixtures_dir / "signals_v2.db"

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all signals
    cursor.execute(
        """
        SELECT source_id, source, title, link, priority_score, timestamp,
               agency, signal_type, issue_codes, metrics
        FROM signals_v2
        ORDER BY priority_score DESC, timestamp DESC
        LIMIT 20
    """
    )

    signals: List[SignalV2] = []
    for row in cursor.fetchall():
        # Parse issue codes
        issue_codes = []
        if row["issue_codes"]:
            try:
                issue_codes = json.loads(row["issue_codes"])
            except json.JSONDecodeError:
                issue_codes = []

        # Parse metrics
        metrics = {}
        if row["metrics"]:
            try:
                metrics = json.loads(row["metrics"])
            except json.JSONDecodeError:
                metrics = {}

        # Create SignalV2 object
        signal = SignalV2(
            source_id=row["source_id"],
            source=row["source"],
            title=row["title"],
            link=row["link"],
            priority_score=row["priority_score"],
            timestamp=datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
            agency=row["agency"],
            signal_type=(
                SignalType(row["signal_type"])
                if row["signal_type"]
                else SignalType.NOTICE
            ),
            issue_codes=issue_codes,
            metrics=metrics,
        )
        signals.append(signal)

    conn.close()
    return signals


def main() -> None:
    """Preview the digest with real data."""
    print("Loading signals from database...")
    signals = load_signals_from_db()
    print(f"Loaded {len(signals)} signals")

    if not signals:
        print("No signals found!")
        return

    print("\n" + "=" * 60)
    print("DIGEST PREVIEW")
    print("=" * 60)

    formatter = DigestFormatter()
    digest = formatter.format_daily_digest(signals, hours_back=24)

    print(digest)
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
