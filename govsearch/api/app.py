"""FastAPI application for the GovSearch service."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import psycopg2.extras
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from govsearch.config import get_settings
from govsearch.db import GovSearchDatabase, ensure_schema

logger = logging.getLogger(__name__)

app = FastAPI(title="GovSearch API", version="1.0.0")


@app.on_event("startup")
async def startup_event() -> None:
    settings = get_settings()
    ensure_schema(settings.database_url)
    app.state.db = GovSearchDatabase(settings.database_url)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    db: GovSearchDatabase = getattr(app.state, "db", None)
    if db:
        db.close()


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/search")
async def search(
    q: Optional[str] = Query(default=None, description="Full-text search query"),
    sources: Optional[List[str]] = Query(default=None, alias="sources[]"),
    agencies: Optional[List[str]] = Query(default=None, alias="agencies[]"),
    types: Optional[List[str]] = Query(default=None, alias="types[]"),
    days_back: int = Query(default=30, ge=1, le=2000,
                           description="How many days of history to search"),
    closing_soon: bool = Query(default=False),
    surge: bool = Query(default=False),
    min_priority: float = Query(default=0.0, ge=0.0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> JSONResponse:
    db: GovSearchDatabase = getattr(app.state, "db", None)
    if not db:
        raise HTTPException(status_code=500, detail="Database not initialized")

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days_back)
    search_query = (q or "").strip()

    closing_expr = (
        "CASE WHEN comment_end_date IS NOT NULL AND comment_end_date <= "
        "(NOW() AT TIME ZONE 'UTC') + INTERVAL '14 days' THEN 1 ELSE 0 END"
    )

    rank_params: List[object] = []
    rank_expr = "0"
    where_clauses: List[str] = []
    where_params: List[object] = []

    if search_query:
        rank_expr = "ts_rank_cd(tsv, plainto_tsquery('english', %s))"
        rank_params.append(search_query)
        where_clauses.append("tsv @@ plainto_tsquery('english', %s)")
        where_params.append(search_query)

    where_clauses.append("posted_at >= %s")
    where_params.append(since)

    if sources:
        where_clauses.append("source = ANY(%s)")
        where_params.append(sources)

    if agencies:
        patterns = [f"%{agency.strip()}%" for agency in agencies if agency.strip()]
        if patterns:
            where_clauses.append("agency ILIKE ANY(%s)")
            where_params.append(patterns)

    if types:
        where_clauses.append("document_type = ANY(%s)")
        where_params.append(types)

    if closing_soon:
        where_clauses.append(
            "comment_end_date IS NOT NULL AND comment_end_date <= "
            "(NOW() AT TIME ZONE 'UTC') + INTERVAL '14 days'"
        )

    if surge:
        where_clauses.append("surge = TRUE")

    if min_priority > 0:
        where_clauses.append("priority_score >= %s")
        where_params.append(min_priority)

    where_sql = ""
    if where_clauses:
        where_sql = " WHERE " + " AND ".join(where_clauses)

    offset = (page - 1) * page_size

    select_sql = f"""
        SELECT
            id,
            source,
            title,
            agency,
            document_type,
            posted_at,
            comment_end_date,
            url,
            docket_id,
            priority_score,
            surge,
            comments_24h,
            money_amount,
            {rank_expr} AS rank,
            {closing_expr} AS closing_soon
        FROM documents
        {where_sql}
        ORDER BY rank DESC, closing_soon DESC, surge DESC,
                 priority_score DESC, posted_at DESC
        LIMIT %s OFFSET %s
    """

    count_sql = f"SELECT COUNT(*) FROM documents {where_sql}"

    select_params = rank_params + where_params + [page_size, offset]
    count_params = list(where_params)

    start = time.perf_counter()
    with db.connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(count_sql, count_params)
            total = cur.fetchone()["count"]

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(select_sql, select_params)
            rows = cur.fetchall()

    duration_ms = round((time.perf_counter() - start) * 1000, 2)

    results = [
        {
            "id": row["id"],
            "source": row["source"],
            "title": row["title"],
            "agency": row.get("agency"),
            "document_type": row["document_type"],
            "posted_at": _to_iso(row.get("posted_at")),
            "comment_end_date": _to_iso(row.get("comment_end_date")),
            "url": row.get("url"),
            "docket_id": row.get("docket_id"),
            "priority_score": float(row.get("priority_score") or 0.0),
            "surge": bool(row.get("surge")),
            "comments_24h": row.get("comments_24h"),
            "money_amount": float(row.get("money_amount") or 0.0),
            "rank": float(row.get("rank") or 0.0),
            "closing_soon": bool(row.get("closing_soon")),
        }
        for row in rows
    ]

    payload = {
        "query": search_query,
        "page": page,
        "page_size": page_size,
        "total": total,
        "results": results,
        "duration_ms": duration_ms,
    }

    return JSONResponse(payload)


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()
