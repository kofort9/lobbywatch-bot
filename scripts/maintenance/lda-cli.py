#!/usr/bin/env python3
"""LDA CLI for manual operations."""

import argparse
import os
import sys
from pathlib import Path

from bot.database_postgres import create_database_manager
from bot.lda_digest import LDADigestComputer
from bot.lda_scheduler import LDAScheduler
from bot.utils import is_lda_enabled

# Add the project root to the Python path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))


def main() -> None:
    parser = argparse.ArgumentParser(description="LDA CLI for manual operations")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Update command
    subparsers.add_parser("update", help="Run quarterly update")

    # Backfill command
    backfill_parser = subparsers.add_parser("backfill", help="Run historical backfill")
    backfill_parser.add_argument("start_year", type=int, help="Start year")
    backfill_parser.add_argument("end_year", type=int, help="End year")

    # Digest command
    digest_parser = subparsers.add_parser("digest", help="Generate LDA digest")
    digest_parser.add_argument("--quarter", help="Quarter (e.g., 2024Q3)")
    digest_parser.add_argument("--channel", default="cli", help="Channel ID")

    # Status command
    subparsers.add_parser("status", help="Show LDA status")

    # Test command
    test_parser = subparsers.add_parser("test", help="Test API connection")
    test_parser.add_argument(
        "--pages", type=int, default=1, help="Number of pages to fetch"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Check if LDA is enabled
    if not is_lda_enabled():
        print("❌ LDA features are disabled. Set ENABLE_LDA_V1=true to enable.")
        return

    scheduler = LDAScheduler()

    if args.command == "update":
        print("🔄 Running quarterly LDA update...")
        result = scheduler.run_quarterly_update()

        if result["status"] == "success":
            print("✅ Update completed successfully!")
            print(f"   Added: {result.get('added', 0)} filings")
            print(f"   Updated: {result.get('updated', 0)} filings")
            print(f"   Errors: {result.get('errors', 0)}")
        else:
            print(f"❌ Update failed: {result.get('error', 'Unknown error')}")

    elif args.command == "backfill":
        print(f"🔄 Running LDA backfill from {args.start_year} to {args.end_year}...")
        result = scheduler.run_backfill(args.start_year, args.end_year)

        if result["status"] == "success":
            print("✅ Backfill completed successfully!")
            print(f"   Years: {args.start_year}-{args.end_year}")
            print(f"   Added: {result.get('added', 0)} filings")
            print(f"   Updated: {result.get('updated', 0)} filings")
            print(f"   Errors: {result.get('errors', 0)}")
        else:
            print(f"❌ Backfill failed: {result.get('error', 'Unknown error')}")

    elif args.command == "digest":
        print("📊 Generating LDA digest...")
        db_manager = create_database_manager()
        lda_digest = LDADigestComputer(db_manager)

        digest = lda_digest.compute_lda_digest(args.channel, args.quarter)
        print("\n" + "=" * 60)
        print(digest)
        print("=" * 60)

    elif args.command == "status":
        print("📊 LDA Status:")
        print(f"   Enabled: {is_lda_enabled()}")
        print(f"   Data Source: {os.getenv('LDA_DATA_SOURCE', 'bulk')}")
        print(f"   API Key: {'✅ Set' if os.getenv('LDA_API_KEY') else '❌ Missing'}")

        # Check database
        try:
            db_manager = create_database_manager()
            with db_manager.get_connection() as conn:
                if hasattr(conn, "cursor"):
                    # PostgreSQL
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM filing")
                    filing_count = cursor.fetchone()[0]
                    cursor.execute("SELECT COUNT(*) FROM entity")
                    entity_count = cursor.fetchone()[0]
                else:
                    # SQLite
                    filing_count = conn.execute(
                        "SELECT COUNT(*) FROM filing"
                    ).fetchone()[0]
                    entity_count = conn.execute(
                        "SELECT COUNT(*) FROM entity"
                    ).fetchone()[0]

                print("   Database: ✅ Connected")
                print(f"   Filings: {filing_count:,}")
                print(f"   Entities: {entity_count:,}")
        except Exception as e:
            print(f"   Database: ❌ Error - {e}")

    elif args.command == "test":
        print(f"🧪 Testing API connection (fetching {args.pages} pages)...")
        try:
            filings = scheduler.etl._fetch_filings_by_type(
                2024, "Q3", max_pages=args.pages
            )
            print(f"✅ Successfully fetched {len(filings)} filings")

            if filings:
                print("\n📄 Sample filings:")
                for i, filing in enumerate(filings[:3], 1):
                    client = filing.get("client_name", "N/A")[:40]
                    registrant = filing.get("registrant_name", "N/A")[:40]
                    amount = filing.get("amount", 0)
                    print(f"   {i}. {client} → {registrant} (${amount:,})")
        except Exception as e:
            print(f"❌ API test failed: {e}")


if __name__ == "__main__":
    main()
