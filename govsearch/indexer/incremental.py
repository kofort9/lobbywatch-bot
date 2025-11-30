"""Incremental update entrypoint for GovSearch indexer."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from govsearch.db import ensure_schema
from govsearch.indexer.core import GovSearchIndexer

logger = logging.getLogger(__name__)


def run_incremental_update(
    database_url: str, hours_back: int = 24
) -> None:
    """Process the most recent window of documents."""

    ensure_schema(database_url)

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=hours_back)

    start = time.perf_counter()
    indexer = GovSearchIndexer(database_url)
    try:
        docs, edges = indexer.run(since=since, until=now)
    finally:
        indexer.close()
    duration = time.perf_counter() - start

    logger.info(
        "Incremental update completed",
        extra={
            "documents": docs,
            "edges": edges,
            "duration_seconds": round(duration, 2),
            "since": since.isoformat(),
            "until": now.isoformat(),
        },
    )


__all__ = ["run_incremental_update"]
