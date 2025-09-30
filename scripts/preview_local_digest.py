#!/usr/bin/env python3
"""Preview the daily digest using locally stored signals.

This helper is intended for development workflows where engineers want to see
exactly what the formatter will emit without hitting external APIs.

Example usage:

    python scripts/preview_local_digest.py --db signals_v2.db --hours 48

"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, cast

import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from bot.digest import DigestFormatter
    from bot.signals import SignalType, SignalV2, Urgency
    from bot.signals_database import SignalsDatabaseV2
except ModuleNotFoundError:  # pragma: no cover - allow direct script invocation
    ROOT_DIR = Path(__file__).resolve().parent.parent
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    from bot.digest import DigestFormatter
    from bot.signals import SignalType, SignalV2, Urgency
    from bot.signals_database import SignalsDatabaseV2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render the LobbyLens daily digest using signals stored in a local "
            "SQLite database or a remote Railway PostgreSQL instance."
        )
    )
    parser.add_argument(
        "--db",
        default="signals.db",
        help=(
            "Path to a SQLite database (default: signals.db) or a PostgreSQL "
            "connection string, e.g. postgresql://user:pass@host:port/railway"
        ),
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Number of hours to look back when selecting signals (default: 24)",
    )
    parser.add_argument(
        "--min-priority",
        type=float,
        default=0.0,
        help="Minimum priority score to include in the preview (default: 0.0)",
    )
    parser.add_argument(
        "--watch",
        action="append",
        default=None,
        help="Watchlist term to inject when formatting (repeat for multiple terms)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the digest preview instead of printing to stdout",
    )
    parser.add_argument(
        "--silent",
        action="store_true",
        help="Suppress the digest body and only print the summary line",
    )
    return parser.parse_args()


def load_signals_sqlite(
    db_path: Path, hours: int, minimum_priority: float
) -> List[SignalV2]:
    database = SignalsDatabaseV2(db_path=str(db_path))
    return cast(
        List[SignalV2],
        database.get_recent_signals(hours_back=hours, min_priority=minimum_priority),
    )


def _ensure_tz(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _coerce_issue_codes(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(item) for item in data]
        except json.JSONDecodeError:
            return [value.strip() for value in raw.split(",") if value.strip()]
    return []


def _coerce_metrics(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    return {}


def _coerce_watchlist(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(item) for item in raw]
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(item) for item in data]
        except json.JSONDecodeError:
            return [value.strip() for value in raw.split(",") if value.strip()]
    return []


def _map_row_to_signal(row: Dict[str, Any]) -> SignalV2:
    timestamp = row.get("ts")
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp)
        except ValueError:
            timestamp = datetime.now(timezone.utc)
    timestamp = _ensure_tz(timestamp)

    signal_type_raw = row.get("signal_type")
    signal_type = None
    if signal_type_raw:
        try:
            signal_type = SignalType(signal_type_raw)
        except ValueError:
            signal_type = None

    urgency_raw = row.get("urgency")
    urgency = None
    if urgency_raw:
        try:
            urgency = Urgency(urgency_raw)
        except ValueError:
            urgency = None

    source = cast(str, row.get("source") or "")
    source_id = cast(str, row.get("source_id") or "")

    return SignalV2(
        source=source,
        source_id=source_id,
        timestamp=timestamp,
        title=row.get("title", ""),
        link=row.get("link", ""),
        agency=row.get("agency"),
        committee=row.get("committee"),
        bill_id=row.get("bill_id"),
        rin=row.get("rin"),
        docket_id=row.get("docket_id"),
        issue_codes=_coerce_issue_codes(row.get("issue_codes")),
        metrics=_coerce_metrics(row.get("metric_json") or row.get("metrics")),
        priority_score=row.get("priority_score") or 0.0,
        signal_type=signal_type,
        urgency=urgency,
        watchlist_matches=_coerce_watchlist(row.get("watchlist_matches")),
    )


def load_signals_postgres(
    dsn: str, hours: int, minimum_priority: float
) -> List[SignalV2]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    with psycopg2.connect(dsn) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT source, source_id, ts, title, link, agency, committee,
                       bill_id, rin, docket_id, issue_codes, metric_json,
                       priority_score, signal_type, urgency, watchlist_matches
                FROM signal_event
                WHERE ts >= %s AND priority_score >= %s
                ORDER BY priority_score DESC, ts DESC
                """,
                (cutoff, minimum_priority),
            )
            rows = cur.fetchall()

    return [_map_row_to_signal(row) for row in rows]


def summarize(signals: Iterable[SignalV2]) -> str:
    signal_list = list(signals)
    counts = Counter(signal.source for signal in signal_list)
    parts = [f"total {len(signal_list)}"]
    parts.extend(f"{source} {count}" for source, count in sorted(counts.items()))
    return ", ".join(parts)


def main() -> int:
    args = parse_args()
    db_argument = args.db

    if "://" in db_argument:
        try:
            signals = load_signals_postgres(db_argument, args.hours, args.min_priority)
        except psycopg2.Error as exc:
            print(f"❌ PostgreSQL error: {exc}")
            return 1
    else:
        db_path = Path(db_argument).expanduser()

        if not db_path.exists():
            print(f"❌ Database not found: {db_path}")
            return 1

        signals = load_signals_sqlite(db_path, args.hours, args.min_priority)
    if not signals:
        print(
            f"⚠️ No signals found in {db_path} within the last {args.hours} hours "
            f"(priority ≥ {args.min_priority})."
        )
        return 0

    watchlist = args.watch or []
    formatter = DigestFormatter(watchlist=watchlist)
    digest = formatter.format_daily_digest(signals, hours_back=args.hours)

    summary = summarize(signals)
    print(f"✅ Digest ready ({summary})")

    if args.output:
        args.output.write_text(digest, encoding="utf-8")
        print(f"📝 Preview written to {args.output}")
    elif not args.silent:
        print("\n=== Daily Digest Preview ===")
        print(digest)
        print("=== End Preview ===")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
