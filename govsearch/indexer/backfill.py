"""Backfill entrypoint for GovSearch indexer."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from govsearch.db import ensure_schema
from govsearch.indexer.core import GovSearchIndexer, compute_backfill_window

logger = logging.getLogger(__name__)


def backfill_recent_documents(
    database_url: str, days_back: int = 365, quarters_back: int = 8
) -> None:
    """Load a historical window of documents and build the search index."""

    ensure_schema(database_url)

    since, until, lda_since = compute_backfill_window(days_back, quarters_back)

    start = time.perf_counter()
    indexer = GovSearchIndexer(database_url)
    try:
        docs, edges = indexer.run(since=since, until=until, include_lda_from=lda_since)
    finally:
        indexer.close()
    duration = time.perf_counter() - start

    logger.info(
        "Backfill completed",
        extra={
            "documents": docs,
            "edges": edges,
            "duration_seconds": round(duration, 2),
            "since": since.isoformat(),
            "until": until.isoformat(),
            "lda_since": lda_since.isoformat(),
        },
    )


__all__ = ["backfill_recent_documents"]
