"""FastAPI application stubs for signals and watchlist queries."""

from datetime import datetime, timezone
from io import StringIO
from typing import List, Optional

from fastapi import FastAPI, Query, Response

from bot.signals_database import SignalsDatabaseV2, create_signals_database


def _filter_signals(
    db: SignalsDatabaseV2,
    min_priority: float,
    source: Optional[str],
    agency: Optional[str],
    issue_codes: Optional[List[str]],
    since_ts: Optional[str],
    watchlist_hit: Optional[bool],
    hours_back: int = 168,
):
    signals = db.get_recent_signals(hours_back=hours_back, min_priority=min_priority)

    if source:
        signals = [s for s in signals if s.source == source]
    if agency:
        needle = agency.lower()
        signals = [s for s in signals if (s.agency or "").lower().find(needle) >= 0]
    if issue_codes:
        issue_set = {code.upper() for code in issue_codes}
        signals = [
            s
            for s in signals
            if issue_set.intersection({c.upper() for c in s.issue_codes})
        ]
    if since_ts:
        try:
            cutoff = datetime.fromisoformat(since_ts)
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
            signals = [s for s in signals if s.timestamp >= cutoff]
        except ValueError:
            signals = []
    if watchlist_hit is not None:
        signals = [s for s in signals if bool(s.watchlist_hit) == watchlist_hit]

    return signals


def create_api_app(
    database: Optional[SignalsDatabaseV2] = None, database_url: Optional[str] = None
) -> FastAPI:
    """Create a FastAPI app exposing read-only signals/watchlist endpoints."""
    db = database or create_signals_database(database_url)
    app = FastAPI(title="LobbyLens API", version="0.1.0")

    @app.get("/api/signals")
    def list_signals(
        page: int = 1,
        page_size: int = 50,
        source: Optional[str] = None,
        agency: Optional[str] = None,
        issue_codes: Optional[List[str]] = Query(default=None),
        min_priority: float = 0.0,
        since_ts: Optional[str] = None,
        watchlist_hit: Optional[bool] = None,
    ) -> dict:
        """Return recent signals with simple filtering and pagination."""
        signals = _filter_signals(
            db,
            min_priority=min_priority,
            source=source,
            agency=agency,
            issue_codes=issue_codes,
            since_ts=since_ts,
            watchlist_hit=watchlist_hit,
        )

        total = len(signals)
        start = max(page - 1, 0) * page_size
        end = start + page_size
        paginated = signals[start:end]

        items = [s.to_dict() for s in paginated]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "export": {
                "csv": "/api/signals/export.csv",
                "parquet": "/api/signals/export.parquet",
            },
        }

    @app.get("/api/signals/export.csv")
    def export_signals_csv(
        source: Optional[str] = None,
        agency: Optional[str] = None,
        issue_codes: Optional[List[str]] = Query(default=None),
        min_priority: float = 0.0,
        since_ts: Optional[str] = None,
        watchlist_hit: Optional[bool] = None,
    ) -> Response:
        """Export signals as CSV."""
        import csv

        signals = _filter_signals(
            db,
            min_priority=min_priority,
            source=source,
            agency=agency,
            issue_codes=issue_codes,
            since_ts=since_ts,
            watchlist_hit=watchlist_hit,
        )

        fieldnames = [
            "source",
            "source_id",
            "timestamp",
            "title",
            "link",
            "agency",
            "committee",
            "priority_score",
            "issue_codes",
            "watchlist_hit",
        ]
        buf = StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        for s in signals:
            data = s.to_dict()
            writer.writerow(
                {
                    "source": data.get("source"),
                    "source_id": data.get("source_id"),
                    "timestamp": data.get("timestamp"),
                    "title": data.get("title"),
                    "link": data.get("link"),
                    "agency": data.get("agency"),
                    "committee": data.get("committee"),
                    "priority_score": data.get("priority_score"),
                    "issue_codes": ",".join(data.get("issue_codes", [])),
                    "watchlist_hit": data.get("watchlist_hit"),
                }
            )

        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=signals.csv"},
        )

    @app.get("/api/signals/export.parquet")
    def export_signals_parquet() -> dict:
        """Placeholder for Parquet export (to be implemented with arrow/pandas)."""
        return {"status": "not_implemented", "message": "Parquet export coming soon"}

    @app.get("/api/watchlist")
    def get_watchlist(channel_id: str = "default") -> dict:
        """Return watchlist entries for a channel."""
        items = db.get_watchlist(channel_id)
        return {
            "channel_id": channel_id,
            "items": [{"term": term, "type": "term"} for term in items],
        }

    @app.get("/health")
    def health() -> dict:
        """Basic health endpoint with database check."""
        db_status = db.health_check()
        return {
            "status": "ok" if db_status.get("database") == "ok" else "degraded",
            "database": db_status,
            "service": "lobbylens-api",
        }

    @app.get("/metrics")
    def metrics() -> Response:
        """Expose minimal Prometheus-style metrics."""
        stats = db.get_database_stats()
        lines = [
            "# HELP lobbylens_signals_total Total signals stored",
            "# TYPE lobbylens_signals_total gauge",
            f"lobbylens_signals_total {stats.get('total_signals', 0)}",
            "# HELP lobbylens_signals_recent Recent signals (24h)",
            "# TYPE lobbylens_signals_recent gauge",
            f"lobbylens_signals_recent {stats.get('recent_signals_24h', 0)}",
            "# HELP lobbylens_signals_high_priority Recent high priority signals (24h)",
            "# TYPE lobbylens_signals_high_priority gauge",
            f"lobbylens_signals_high_priority {stats.get('high_priority_24h', 0)}",
        ]
        by_source = stats.get("by_source", {}) or {}
        for source, count in by_source.items():
            lines.append(f'lobbylens_signals_by_source{{source="{source}"}} {count}')
        body = "\n".join(lines) + "\n"
        return Response(content=body, media_type="text/plain; version=0.0.4")

    return app


app = create_api_app()
