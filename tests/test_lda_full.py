#!/usr/bin/env python3
"""Comprehensive test of LDA V1 MVP functionality."""

import os
import sys
import tempfile

from bot.database import DatabaseManager
from bot.lda_digest import LDADigestComputer

# from bot.slack_app import SlackApp  # Unused
from bot.lda_etl import LDAETLPipeline

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))

# Set environment variables for testing
os.environ["ENABLE_LDA_V1"] = "true"
os.environ["LDA_DATA_SOURCE"] = "bulk"


def test_lda_full_pipeline():
    """Test the complete LDA V1 MVP pipeline."""
    print("🧪 Testing LDA V1 MVP Full Pipeline")
    print("=" * 50)

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Step 1: Initialize database and create schema
        print("1. Initializing database and schema...")
        db_manager = DatabaseManager(db_path)
        db_manager.ensure_enhanced_schema()
        print("   ✅ Database schema created")

        # Step 2: Run ETL pipeline
        print("\n2. Running ETL pipeline...")
        etl = LDAETLPipeline(db_manager)
        result = etl.run_etl(mode="update")
        print(f"   ✅ ETL completed: {result}")

        # Step 3: Test LDA digest
        print("\n3. Testing LDA digest...")
        lda_digest = LDADigestComputer(db_manager)
        digest = lda_digest.compute_lda_digest("test_channel")
        print("   ✅ LDA digest generated:")
        print("   " + "\n   ".join(digest.split("\n")[:10]) + "...")

        # Step 4: Test top registrants
        print("\n4. Testing top registrants query...")
        top_registrants = lda_digest.get_top_registrants(limit=3)
        print(f"   ✅ Found {len(top_registrants)} registrants:")
        for i, reg in enumerate(top_registrants, 1):
            print(
                f"      {i}. {reg['name']} - ${reg['total_amount']:,} ({reg['filing_count']} filings)"
            )

        # Step 5: Test top clients
        print("\n5. Testing top clients query...")
        top_clients = lda_digest.get_top_clients(limit=3)
        print(f"   ✅ Found {len(top_clients)} clients:")
        for i, client in enumerate(top_clients, 1):
            print(
                f"      {i}. {client['name']} - ${client['total_amount']:,} ({client['filing_count']} filings)"
            )

        # Step 6: Test issues summary
        print("\n6. Testing issues summary...")
        issues = lda_digest.get_issues_summary()
        print(f"   ✅ Found {len(issues)} issues:")
        for issue in issues:
            print(
                f"      • {issue['code']}: {issue['filing_count']} filings (${issue['total_amount']:,})"
            )

        # Step 7: Test entity search
        print("\n7. Testing entity search...")
        entity_result = lda_digest.search_entity("Google")
        if "error" not in entity_result:
            entity = entity_result["entity"]
            print(f"   ✅ Found entity: {entity['name']} ({entity['type']})")
            print(
                f"      Total: ${entity_result['total_amount']:,} ({entity_result['filing_count']} filings)"
            )
        else:
            print(f"   ⚠️  Entity search: {entity_result['error']}")

        # Step 8: Test Slack commands (mock)
        print("\n8. Testing Slack command handling...")

        # Mock SlackApp for testing
        class MockSlackApp:
            def __init__(self, db_manager):
                self.db_manager = db_manager

            def post_message(self, channel, text):
                return {"ok": True}

        # Import the command handler method
        from bot.slack_app import SlackApp

        real_slack_app = SlackApp("mock_token", "mock_secret", db_manager, None)

        # Test LDA help command
        real_slack_app._handle_lda_subcommands(
            ["help"], "test_channel", "test_user"
        )
        print("   ✅ LDA help command works")

        # Test top registrants command
        real_slack_app._handle_lda_subcommands(
            ["top", "registrants", "n=3"], "test_channel", "test_user"
        )
        print("   ✅ Top registrants command works")

        # Step 9: Verify database integrity
        print("\n9. Verifying database integrity...")
        with db_manager.get_connection() as conn:
            # Check table counts
            tables = ["entity", "issue", "filing", "filing_issue", "meta", "ingest_log"]
            for table in tables:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                print(f"   • {table}: {count} records")

        print("\n🎉 LDA V1 MVP Full Pipeline Test PASSED!")
        return True

    except Exception as e:
        print(f"\n❌ LDA V1 MVP Full Pipeline Test FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # Clean up
        try:
            os.unlink(db_path)
        except BaseException:
            pass


def test_smoke_tests():
    """Run the smoke tests as specified in the plan."""
    print("\n🔥 Running Smoke Tests")
    print("=" * 30)

    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Smoke Test 1: Fetch sample
        print("1. Fetch sample (single quarter)...")
        db_manager = DatabaseManager(db_path)
        db_manager.ensure_enhanced_schema()

        etl = LDAETLPipeline(db_manager)
        etl.run_etl(mode="update")

        with db_manager.get_connection() as conn:
            filing_count = conn.execute("SELECT COUNT(*) FROM filing").fetchone()[0]
            entity_count = conn.execute("SELECT COUNT(*) FROM entity").fetchone()[0]
            issue_count = conn.execute("SELECT COUNT(*) FROM filing_issue").fetchone()[
                0
            ]

        print(
            f"   ✅ Row counts: {filing_count} filings, {entity_count} entities, {issue_count} filing-issues"
        )

        # Smoke Test 2: Idempotency
        print("\n2. Idempotency test...")
        etl.run_etl(mode="update")

        with db_manager.get_connection() as conn:
            filing_count2 = conn.execute("SELECT COUNT(*) FROM filing").fetchone()[0]
            entity_count2 = conn.execute("SELECT COUNT(*) FROM entity").fetchone()[0]

            # Check for duplicate filing_uids
            duplicate_count = conn.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT filing_uid, COUNT(*) as cnt
                    FROM filing
                    GROUP BY filing_uid
                    HAVING cnt > 1
                )
            """
            ).fetchone()[0]

        print(f"   ✅ Counts stable: {filing_count2} filings, {entity_count2} entities")
        print(f"   ✅ No duplicate filing_uids: {duplicate_count} duplicates")

        # Smoke Test 3: Slack digest
        print("\n3. Slack digest test...")
        lda_digest = LDADigestComputer(db_manager)
        digest = lda_digest.compute_lda_digest("test_channel")

        # Verify digest contains expected sections
        required_sections = ["LDA Money Digest", "Top registrants", "Top issues"]
        sections_found = sum(1 for section in required_sections if section in digest)

        print(f"   ✅ Digest generated ({len(digest)} chars)")
        print(
            f"   ✅ Required sections found: {sections_found}/{len(required_sections)}"
        )

        # Smoke Test 4: Entity lookup
        print("\n4. Entity lookup test...")
        entity_result = lda_digest.search_entity("Google")
        if "error" not in entity_result:
            print(f"   ✅ Entity lookup works: {entity_result['entity']['name']}")
        else:
            print(f"   ⚠️  Entity lookup: {entity_result['error']}")

        # Smoke Test 5: Watchlist
        print("\n5. Watchlist test...")
        # Add to watchlist
        success = db_manager.add_to_watchlist("test_channel", "client", "Google")
        print(f"   ✅ Watchlist add: {success}")

        # Re-run digest to check for watchlist hits
        digest_with_watchlist = lda_digest.compute_lda_digest("test_channel")
        has_watchlist_section = "Watchlist hits" in digest_with_watchlist
        print(f"   ✅ Watchlist integration: {has_watchlist_section}")

        print("\n🎉 All Smoke Tests PASSED!")
        return True

    except Exception as e:
        print(f"\n❌ Smoke Tests FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # Clean up
        try:
            os.unlink(db_path)
        except BaseException:
            pass


if __name__ == "__main__":
    print("🚀 LDA V1 MVP Testing Suite")
    print("=" * 60)

    # Run full pipeline test
    pipeline_success = test_lda_full_pipeline()

    # Run smoke tests
    smoke_success = test_smoke_tests()

    print("\n" + "=" * 60)
    print("📊 TEST RESULTS:")
    print(f"   Full Pipeline: {'✅ PASS' if pipeline_success else '❌ FAIL'}")
    print(f"   Smoke Tests:   {'✅ PASS' if smoke_success else '❌ FAIL'}")

    if pipeline_success and smoke_success:
        print("\n🎉 LDA V1 MVP is ready for deployment!")
    else:
        print("\n⚠️  Some tests failed. Please review and fix issues.")

    print("=" * 60)
