#!/usr/bin/env python3
"""Set up Railway PostgreSQL for LDA V1."""

import os
import sys

import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))


def setup_railway() -> None:
    """Set up Railway PostgreSQL database for LDA V1."""
    print("🚂 Setting up Railway PostgreSQL for LDA V1")
    print("=" * 60)

    try:
        # Connect to Railway PostgreSQL
        # Get DATABASE_URL from environment variable
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise ValueError(
                "DATABASE_URL environment variable not set. "
                "Set it to your PostgreSQL connection string."
            )

        print("1. 🔌 Connecting to Railway PostgreSQL...")
        conn = psycopg2.connect(database_url)
        print("   ✅ Connected successfully")

        # Create enhanced schema
        print("\n2. 🏗️  Creating Enhanced Schema...")
        with conn.cursor() as cursor:
            # Create entity table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS entity (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(normalized_name, type)
                )
            """
            )

            # Create issue table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS issue (
                    id SERIAL PRIMARY KEY,
                    code TEXT NOT NULL UNIQUE,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create filing table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS filing (
                    id SERIAL PRIMARY KEY,
                    filing_uid TEXT NOT NULL UNIQUE,
                    client_id INTEGER,
                    registrant_id INTEGER,
                    filing_date TIMESTAMP,
                    quarter TEXT,
                    year INTEGER,
                    amount INTEGER,
                    url TEXT,
                    summary TEXT,
                    filing_type TEXT,
                    filing_status TEXT DEFAULT 'original',
                    is_amendment BOOLEAN DEFAULT FALSE,
                    source_system TEXT DEFAULT 'senate',
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (client_id) REFERENCES entity(id),
                    FOREIGN KEY (registrant_id) REFERENCES entity(id)
                )
            """
            )

            # Create filing_issue table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS filing_issue (
                    filing_id INTEGER,
                    issue_id INTEGER,
                    PRIMARY KEY (filing_id, issue_id),
                    FOREIGN KEY (filing_id) REFERENCES filing(id) ON DELETE CASCADE,
                    FOREIGN KEY (issue_id) REFERENCES issue(id)
                )
            """
            )

            # Create meta table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create channel digest settings table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS channel_digest_settings (
                    channel_id TEXT PRIMARY KEY,
                    min_amount INTEGER DEFAULT 10000,
                    max_lines_main INTEGER DEFAULT 15,
                    last_lda_digest_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create ingest_log table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ingest_log (
                    id SERIAL PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    added INTEGER DEFAULT 0,
                    updated INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    message TEXT
                )
            """
            )

            # Create indexes
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_filing_uid ON filing(filing_uid)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_filing_quarter ON filing(year, quarter)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_filing_ingested_at ON filing(ingested_at)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_filing_amount ON filing(amount)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_filing_client ON filing(client_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_filing_registrant ON filing(registrant_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_filing_issue_issue ON filing_issue(issue_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_entity_normalized ON entity(normalized_name, type)"
            )

            conn.commit()

        print("   ✅ Schema created successfully")

        # Seed issue codes
        print("\n3. 🏷️  Seeding Issue Codes...")

        # Official LDA issue codes (subset for quick setup)
        issue_codes = [
            ("TEC", "Technology"),
            ("HCR", "Health Care"),
            ("DEF", "Defense"),
            ("EDU", "Education"),
            ("BUD", "Budget/Appropriations"),
            ("TAX", "Taxation/Internal Revenue Code"),
            ("FIN", "Financial Institutions/Investments/Securities"),
            ("ENV", "Environment/Superfund"),
            ("TRD", "Trade"),
            ("INT", "Intelligence"),
        ]

        with conn.cursor() as cursor:
            for code, description in issue_codes:
                cursor.execute(
                    """
                    INSERT INTO issue (code, description) VALUES (%s, %s)
                    ON CONFLICT (code) DO UPDATE SET description = EXCLUDED.description
                """,
                    (code, description),
                )

            conn.commit()

        print(f"   ✅ Seeded {len(issue_codes)} issue codes")

        # Create test data
        print("\n4. 📊 Creating Test Data...")
        with conn.cursor() as cursor:
            # Create entities
            cursor.execute(
                """
                INSERT INTO entity (name, type, normalized_name) VALUES
                ('Akin Gump Strauss Hauer & Feld', 'registrant', 'akin gump strauss hauer feld'),
                ('Meta Platforms Inc', 'client', 'meta platforms')
                ON CONFLICT (normalized_name, type) DO NOTHING
            """
            )

            # Get entity IDs
            cursor.execute(
                "SELECT id FROM entity WHERE normalized_name = 'akin gump strauss hauer feld'"
            )
            result = cursor.fetchone()
            registrant_id = result[0] if result else None

            cursor.execute(
                "SELECT id FROM entity WHERE normalized_name = 'meta platforms'"
            )
            result = cursor.fetchone()
            client_id = result[0] if result else None

            # Create a filing
            cursor.execute(
                """
                INSERT INTO filing (
                    filing_uid, client_id, registrant_id, filing_date, quarter, year, amount,
                    filing_type, filing_status, is_amendment, source_system, url
                ) VALUES (
                    'railway-test-001', %s, %s, '2024-09-15', '2024Q3', 2024, 500000,
                    'Q3', 'original', FALSE, 'senate', 'https://example.com/filing'
                ) ON CONFLICT (filing_uid) DO NOTHING
            """,
                (client_id, registrant_id),
            )

            # Get filing ID and TEC issue ID
            cursor.execute(
                "SELECT id FROM filing WHERE filing_uid = 'railway-test-001'"
            )
            result = cursor.fetchone()
            filing_id = result[0] if result else None

            cursor.execute("SELECT id FROM issue WHERE code = 'TEC'")
            result = cursor.fetchone()
            tec_id = result[0] if result else None

            # Create filing-issue relationship
            cursor.execute(
                """
                INSERT INTO filing_issue (filing_id, issue_id) VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """,
                (filing_id, tec_id),
            )

            conn.commit()

        print("   ✅ Test data created")

        # Verify setup
        print("\n5. ✅ Verifying Setup...")
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM entity")
            result = cursor.fetchone()
            entity_count = result[0] if result else None

            cursor.execute("SELECT COUNT(*) FROM issue")
            result = cursor.fetchone()
            issue_count = result[0] if result else None

            cursor.execute("SELECT COUNT(*) FROM filing")
            result = cursor.fetchone()
            filing_count = result[0] if result else None

            print(f"   Entities: {entity_count}")
            print(f"   Issues: {issue_count}")
            print(f"   Filings: {filing_count}")

        conn.close()

        print("\n🎉 Railway PostgreSQL Setup Complete!")
        print("   ✅ Database: railway")
        print("   ✅ Host: switchback.proxy.rlwy.net:37990")
        print("   ✅ Schema: Enhanced LDA schema created")
        print("   ✅ Data: Test data populated")
        print("   ✅ Ready: For LDA front page digest")
        print("\n   🔗 Your DATABASE_URL is already configured in .env")
        print("   🚀 Run: python scripts/lda-cli.py status")

    except Exception as e:
        print(f"\n❌ Railway Setup FAILED: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    setup_railway()
