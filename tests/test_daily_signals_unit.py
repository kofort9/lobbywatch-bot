"""Unit tests for DailySignalsCollector with mocked HTTP calls."""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import Mock, patch

import requests

from bot.daily_signals import DailySignalsCollector
from bot.signals import SignalV2


def _collector() -> DailySignalsCollector:
    config = {
        "CONGRESS_API_KEY": "test",
        "REGULATIONS_GOV_API_KEY": "test",
        "http_timeout_seconds": 1,
        "http_retries": 1,
    }
    return DailySignalsCollector(config)


def _make_response(payload: dict) -> Any:
    resp = Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


def test_collect_congress_signals_success() -> None:
    collector = _collector()
    bill_payload = {
        "bills": [
            {
                "number": "1234",
                "type": "HR",
                "title": "Test Privacy Act",
                "updateDate": datetime.now(timezone.utc).isoformat(),
                "congress": "118",
                "introducedDate": "2024-01-14",
            }
        ]
    }
    resp = _make_response(bill_payload)
    with patch.object(collector, "_get", return_value=resp):
        signals = collector._collect_congress_signals(24)
    assert len(signals) == 1
    assert isinstance(signals[0], SignalV2)


def test_collect_federal_register_handles_400_then_success() -> None:
    collector = _collector()

    bad_response = Mock()
    bad_response.raise_for_status.side_effect = requests.HTTPError(
        response=Mock(status_code=400)
    )
    good_payload = {
        "results": [
            {
                "document_number": "2024-00001",
                "title": "Rule",
                "type": "Notice",
                "agency_names": ["EPA"],
                "publication_date": "2024-01-01",
                "html_url": "https://example.com",
            }
        ]
    }
    good_response = _make_response(good_payload)

    with patch.object(collector, "_get", side_effect=[bad_response, good_response]):
        signals = collector._collect_federal_register_signals(24)
    assert len(signals) == 1


def test_fetch_regulations_gov_comment_metrics_minimal() -> None:
    collector = _collector()
    comment_payload = {"data": [], "links": {"next": None}}
    resp = _make_response(comment_payload)
    with patch.object(collector, "_get", return_value=resp):
        metrics = collector._fetch_regulations_gov_comment_metrics(
            "DOC1", datetime.now(timezone.utc)
        )
    assert metrics["comments_24h"] == 0
    assert metrics["comment_surge"] is False


def test_collect_regulations_gov_signals_minimal() -> None:
    collector = _collector()
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": "DOC1",
        "attributes": {
            "documentType": "Rule",
            "postedDate": now,
            "title": "Test Rule",
            "docketId": "DOCKET-1",
            "documentId": "DOC1",
        },
    }
    doc_payload = {"data": [doc], "links": {"next": None}}
    resp_docs = _make_response(doc_payload)

    with (
        patch.object(collector, "_get", return_value=resp_docs),
        patch.object(collector, "_fetch_regulations_gov_details", return_value={}),
        patch.object(
            collector, "_fetch_regulations_gov_comment_metrics", return_value={}
        ),
        patch.object(
            collector,
            "_build_federal_register_index",
            return_value={"by_docket": {}, "by_document": {}, "titles": []},
        ),
    ):
        signals = collector._collect_regulations_gov_signals(
            24, federal_register_signals=[]
        )
    assert len(signals) == 1
    assert signals[0].source == "regulations_gov"


def test_collect_signals_handles_exceptions() -> None:
    collector = _collector()
    with (
        patch.object(
            collector, "_collect_congress_signals", side_effect=Exception("boom")
        ),
        patch.object(collector, "_collect_federal_register_signals", return_value=[]),
        patch.object(collector, "_collect_regulations_gov_signals", return_value=[]),
        patch.object(collector.rules_engine, "process_signal", side_effect=lambda x: x),
    ):
        signals = collector.collect_signals(24)
    assert signals == []


def test_get_regulations_gov_link_prefers_docket() -> None:
    collector = _collector()
    attrs = {"docketId": "DOCKET-1", "documentId": "DOC-1"}
    link = collector._get_regulations_gov_link(attrs)
    assert link.endswith("DOCKET-1")


def test_collect_federal_register_signals_handles_error() -> None:
    collector = _collector()
    bad_resp = Mock()
    bad_resp.raise_for_status.side_effect = requests.HTTPError("bad")
    with patch.object(collector, "_get", return_value=bad_resp):
        signals = collector._collect_federal_register_signals(24)
    assert signals == []
