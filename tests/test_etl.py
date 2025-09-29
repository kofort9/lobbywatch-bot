#!/usr/bin/env python3
"""Quick test of LDA ETL pipeline."""

import os
import sys
import tempfile

from bot.database import DatabaseManager
from bot.lda_etl import LDAETLPipeline

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))


def test_etl_pipeline():
    """Test the LDA ETL pipeline with sample data."""
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # Initialize database manager and create schema
        db_manager = DatabaseManager(db_path)
        db_manager.ensure_enhanced_schema()

        # Initialize ETL pipeline
        etl = LDAETLPipeline(db_manager)

        # Run ETL with sample data
        print("Running LDA ETL pipeline...")
        result = etl.run_etl(mode="update")

        print(f"ETL Results: {result}")

        # Verify data was inserted
        with db_manager.get_connection() as conn:
            # Check entities
            entities = conn.execute("SELECT * FROM entity").fetchall()
            print(f"\nEntities created: {len(entities)}")
            for entity in entities:
                print(f"  - {entity['name']} ({entity['type']})")

            # Check issues
            issues = conn.execute("SELECT * FROM issue").fetchall()
            print(f"\nIssues created: {len(issues)}")
            for issue in issues:
                print(f"  - {issue['code']}")

            # Check filings
            filings = conn.execute(
                """
                SELECT f.*, c.name as client_name, r.name as registrant_name
                FROM filing f
                LEFT JOIN entity c ON f.client_id = c.id
                LEFT JOIN entity r ON f.registrant_id = r.id
            """
            ).fetchall()
            print(f"\nFilings created: {len(filings)}")
            for filing in filings:
                print(
                    f"  - {filing['client_name']} → {filing['registrant_name']} (${filing['amount']:,})"
                )

        print("\n✅ ETL pipeline test completed successfully!")
        return True

    except Exception as e:
        print(f"❌ ETL pipeline test failed: {e}")
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
    test_etl_pipeline()
