"""Tests for FastAPI signals/watchlist endpoints."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi.testclient import TestClient

from bot.api import create_api_app
from bot.signals import SignalV2
from bot.signals_database import SignalsDatabaseV2


def _make_temp_db() -> SignalsDatabaseV2:
    """Create a temporary SignalsDatabaseV2 instance."""
    tmp = NamedTemporaryFile(suffix=".db", delete=False)
    Path(tmp.name).unlink(missing_ok=True)  # removed after close
    return SignalsDatabaseV2(db_path=tmp.name)


def test_list_signals_filters_and_pagination() -> None:
    """Ensure signals endpoint filters by source/issue codes and paginates."""
    db = _make_temp_db()
    now = datetime.now(timezone.utc)
    signals = [
        SignalV2(
            source="federal_register",
            source_id="FR-1",
            timestamp=now,
            title="FR Notice",
            link="https://fr.gov/1",
            agency="EPA",
            issue_codes=["ENV"],
            priority_score=4.0,
        ),
        SignalV2(
            source="congress",
            source_id="HR-1",
            timestamp=now - timedelta(hours=1),
            title="Bill HR-1",
            link="https://congress.gov/hr1",
            agency="Congress",
            issue_codes=["TEC"],
            priority_score=3.0,
        ),
    ]
    db.save_signals(signals)

    app = create_api_app(db)
    client = TestClient(app)

    resp = client.get("/api/signals", params={"source": "federal_register"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["source_id"] == "FR-1"

    resp2 = client.get("/api/signals", params={"issue_codes": ["TEC"]})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total"] == 1
    assert data2["items"][0]["source_id"] == "HR-1"

    resp3 = client.get("/api/signals", params={"page": 1, "page_size": 1})
    assert resp3.status_code == 200
    data3 = resp3.json()
    assert data3["page_size"] == 1
    assert data3["total"] == 2


def test_watchlist_endpoint() -> None:
    """Ensure watchlist endpoint returns stored items."""
    db = _make_temp_db()
    db.add_watchlist_item("C123", "Google")
    db.add_watchlist_item("C123", "AI")

    app = create_api_app(db)
    client = TestClient(app)

    resp = client.get("/api/watchlist", params={"channel_id": "C123"})
    assert resp.status_code == 200
    data = resp.json()
    terms = [item["term"] for item in data["items"]]
    assert "Google" in terms and "AI" in terms


def test_export_signals_csv() -> None:
    """Ensure CSV export returns filtered content."""
    db = _make_temp_db()
    now = datetime.now(timezone.utc)
    sig = SignalV2(
        source="congress",
        source_id="HR-1",
        timestamp=now,
        title="HR 1",
        link="https://congress.gov/hr1",
        priority_score=3.0,
        issue_codes=["TEC"],
    )
    db.save_signals([sig])

    app = create_api_app(db)
    client = TestClient(app)

    resp = client.get("/api/signals/export.csv", params={"source": "congress"})
    assert resp.status_code == 200
    assert "text/csv" in resp.headers.get("content-type", "")
    assert "HR-1" in resp.text


def test_health_endpoint() -> None:
    """Health endpoint reports database status."""
    db = _make_temp_db()
    app = create_api_app(db)
    client = TestClient(app)

    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in {"ok", "degraded"}
    assert "database" in data


def test_metrics_endpoint() -> None:
    """Metrics endpoint returns Prometheus text format."""
    db = _make_temp_db()
    app = create_api_app(db)
    client = TestClient(app)

    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "lobbylens_signals_total" in resp.text
