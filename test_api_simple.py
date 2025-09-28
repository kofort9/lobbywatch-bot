#!/usr/bin/env python3
"""Simple test of LDA API integration."""

import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

# Set environment variables for testing
os.environ['ENABLE_LDA_V1'] = 'true'
os.environ['LDA_DATA_SOURCE'] = 'api'
os.environ['LDA_API_KEY'] = '37cdd62e714fd57d6cad079da319c85cc1880e9d'
os.environ['LDA_API_BASE_URL'] = 'https://lda.senate.gov/api/v1/'

from bot.database import DatabaseManager
from bot.lda_etl import LDAETLPipeline

def test_api_simple():
    """Simple test of API integration."""
    print("🌐 Simple LDA API Test")
    print("=" * 30)
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    try:
        # Initialize
        db_manager = DatabaseManager(db_path)
        db_manager.ensure_enhanced_schema()
        etl = LDAETLPipeline(db_manager)
        
        # Test API fetch with just 5 filings
        print("Fetching 5 Q3 2024 filings...")
        filings = etl._fetch_filings_by_type(2024, "Q3")
        
        print(f"✅ Fetched {len(filings)} filings")
        
        if filings:
            filing = filings[0]
            print(f"Sample filing:")
            print(f"  Client: {filing.get('client_name')}")
            print(f"  Registrant: {filing.get('registrant_name')}")
            print(f"  Amount: ${filing.get('amount', 0):,}")
            print(f"  Issues: {filing.get('issue_codes')}")
            
            # Process just this one filing
            print(f"\nProcessing {min(3, len(filings))} filings...")
            test_filings = filings[:3]  # Just first 3
            added, updated, errors = etl._process_filings(test_filings)
            print(f"✅ Processed: {added} added, {updated} updated, {errors} errors")
            
            # Check database
            with db_manager.get_connection() as conn:
                entity_count = conn.execute("SELECT COUNT(*) FROM entity").fetchone()[0]
                filing_count = conn.execute("SELECT COUNT(*) FROM filing").fetchone()[0]
                print(f"✅ Database: {entity_count} entities, {filing_count} filings")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            os.unlink(db_path)
        except:
            pass

if __name__ == "__main__":
    test_api_simple()
