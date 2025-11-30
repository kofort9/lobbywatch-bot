"""Database utilities for GovSearch."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator, Iterable

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

logger = logging.getLogger(__name__)


DOCUMENTS_DDL: Iterable[str] = (
    """
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        source TEXT NOT NULL,
        origin_id TEXT,
        title TEXT NOT NULL,
        summary TEXT,
        agency TEXT,
        document_type TEXT NOT NULL,
        posted_at TIMESTAMPTZ,
        effective_date TIMESTAMPTZ,
        comment_end_date TIMESTAMPTZ,
        url TEXT,
        docket_id TEXT,
        rin TEXT,
        issue_codes TEXT[] DEFAULT ARRAY[]::TEXT[],
        money_amount NUMERIC,
        comments_24h INTEGER DEFAULT 0,
        surge BOOLEAN DEFAULT FALSE,
        priority_score DOUBLE PRECISION DEFAULT 0,
        features JSONB DEFAULT '{}'::jsonb,
        tsv tsvector
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS documents_source_idx
        ON documents (source)
    """,
    """
    CREATE INDEX IF NOT EXISTS documents_document_type_idx
        ON documents (document_type)
    """,
    """
    CREATE INDEX IF NOT EXISTS documents_agency_idx
        ON documents (agency)
    """,
    """
    CREATE INDEX IF NOT EXISTS documents_posted_at_idx
        ON documents (posted_at DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS documents_comment_end_idx
        ON documents (comment_end_date DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS documents_priority_idx
        ON documents (priority_score DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS documents_issue_codes_idx
        ON documents USING GIN(issue_codes)
    """,
    """
    CREATE INDEX IF NOT EXISTS documents_tsv_idx
        ON documents USING GIN(tsv)
    """,
)

EDGES_DDL: Iterable[str] = (
    """
    CREATE TABLE IF NOT EXISTS edges (
        src_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        dst_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        relation TEXT NOT NULL,
        PRIMARY KEY (src_id, dst_id, relation)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS edges_src_idx ON edges (src_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS edges_dst_idx ON edges (dst_id)
    """,
)

TSV_FUNCTION = """
CREATE OR REPLACE FUNCTION govsearch_documents_tsv_trigger()
RETURNS trigger AS $$
BEGIN
    NEW.tsv := to_tsvector(
        'english',
        coalesce(NEW.title, '') || ' ' ||
        coalesce(NEW.summary, '') || ' ' ||
        coalesce(NEW.agency, '') || ' ' ||
        coalesce(array_to_string(NEW.issue_codes, ' '), '')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

TSV_TRIGGER = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgname = 'documents_tsv_update'
    ) THEN
        CREATE TRIGGER documents_tsv_update
        BEFORE INSERT OR UPDATE ON documents
        FOR EACH ROW EXECUTE FUNCTION govsearch_documents_tsv_trigger();
    END IF;
END $$;
"""


class GovSearchDatabase:
    """Connection helper and schema manager for GovSearch."""

    def __init__(self, dsn: str, minconn: int = 1, maxconn: int = 10):
        self.dsn = dsn
        self.pool = SimpleConnectionPool(
            minconn,
            maxconn,
            dsn,
            cursor_factory=psycopg2.extras.RealDictCursor,
        )

    @contextmanager
    def connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """Context manager yielding a pooled connection."""

        conn = self.pool.getconn()
        try:
            yield conn
        finally:
            self.pool.putconn(conn)

    def close(self) -> None:
        """Close all connections."""

        self.pool.closeall()

    def ensure_schema(self) -> None:
        """Create tables, indexes, and triggers if they do not exist."""

        with self.connection() as conn:
            with conn.cursor() as cur:
                logger.info("Ensuring GovSearch documents table")
                for statement in DOCUMENTS_DDL:
                    cur.execute(statement)

                logger.info("Ensuring GovSearch edges table")
                for statement in EDGES_DDL:
                    cur.execute(statement)

                logger.info("Creating GovSearch TSV trigger")
                cur.execute(TSV_FUNCTION)
                cur.execute(TSV_TRIGGER)

            conn.commit()


def ensure_schema(database_url: str) -> None:
    """Convenience function to run schema migrations once."""

    db = GovSearchDatabase(database_url, minconn=1, maxconn=1)
    try:
        db.ensure_schema()
    finally:
        db.close()
