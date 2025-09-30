#!/usr/bin/env python3
"""Copy recent Railway (PostgreSQL) signals into the local SQLite cache.

Example:

    python scripts/sync_signals_from_postgres.py \
        --postgres "$DATABASE_URL" --sqlite signals.db --hours 72

The script reuses the formatter loading utilities so the resulting
`signals.db` is compatible with `scripts/preview_local_digest.py` and tests.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from bot.signals_database import SignalsDatabaseV2
    from scripts.preview_local_digest import load_signals_postgres
except ModuleNotFoundError:  # pragma: no cover - allow direct script invocation
    ROOT_DIR = Path(__file__).resolve().parent.parent
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))

    from bot.signals_database import SignalsDatabaseV2
    from scripts.preview_local_digest import load_signals_postgres


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch SignalV2 records from a Railway PostgreSQL instance and "
            "persist them into a local SQLite database for offline digest previews."
        )
    )
    parser.add_argument(
        "--postgres",
        required=True,
        help="PostgreSQL connection string (e.g. postgresql://user:pass@host:port/railway)",
    )
    parser.add_argument(
        "--sqlite",
        default="signals.db",
        help="Destination SQLite file to update (default: signals.db)",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=48,
        help="Number of hours back to copy (default: 48)",
    )
    parser.add_argument(
        "--min-priority",
        type=float,
        default=0.0,
        help="Minimum priority score filter before copying (default: 0.0)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Optional maximum number of signals to copy after filtering",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-step status output",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.quiet:
        print("🚂 Fetching recent signals from Railway…")

    try:
        signals = load_signals_postgres(args.postgres, args.hours, args.min_priority)
    except Exception as exc:  # pragma: no cover - surface errors to caller
        print(f"❌ Failed to load signals: {exc}")
        return 1

    if args.limit:
        signals = signals[: args.limit]

    if not signals:
        if not args.quiet:
            print(
                f"⚠️ No signals found in the last {args.hours}h with priority ≥ {args.min_priority}."
            )
        return 0

    sqlite_path = Path(args.sqlite).expanduser()
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    database = SignalsDatabaseV2(db_path=str(sqlite_path))
    saved = database.save_signals(signals)

    if not args.quiet:
        print(
            f"✅ Copied {saved} signals into {sqlite_path} "
            f"({len(signals)} fetched, hours_back={args.hours})."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
