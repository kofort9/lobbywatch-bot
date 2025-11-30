"""Additional command coverage for web_server."""

from unittest.mock import patch

import pytest

from bot.web_server import create_web_server
from tests.slack_stubs import StubSlackApp


@pytest.fixture(autouse=True)
def _disable_signature_check(monkeypatch: object) -> None:
    """Skip Slack signature verification in legacy command tests."""
    from bot import config

    monkeypatch.setattr(config.settings, "slack_signing_secret", None)


@pytest.fixture
def slack_stub() -> StubSlackApp:
    return StubSlackApp()


@pytest.fixture
def app(slack_stub: StubSlackApp) -> object:
    application = create_web_server(slack_app=slack_stub)
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app: object) -> object:
    return app.test_client()


@patch("bot.web_server.create_signals_database")
def test_watchlist_invalid_usage(mock_db: object, client: object) -> None:
    mock_db.return_value.get_watchlist.return_value = []
    resp = client.post(
        "/lobbylens/commands",
        data={"command": "/watchlist", "text": "invalid", "channel_id": "ch"},
    )
    assert resp.status_code == 200
    assert "Usage" in resp.get_json()["text"]


@patch("bot.web_server.create_signals_database")
def test_threshold_set_success(mock_db: object, client: object) -> None:
    mock_db.return_value.update_channel_setting.return_value = True
    resp = client.post(
        "/lobbylens/commands",
        data={"command": "/threshold", "text": "set 10", "channel_id": "ch"},
    )
    assert resp.status_code == 200
    assert "threshold" in resp.get_json()["text"].lower()


@patch("bot.web_server.create_signals_database")
def test_unknown_command(mock_db: object, client: object) -> None:
    resp = client.post(
        "/lobbylens/commands",
        data={"command": "/unknown", "text": "", "channel_id": "ch"},
    )
    assert resp.status_code == 200
    assert "Unknown command" in resp.get_json()["text"]
