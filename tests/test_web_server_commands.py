"""Tests for web_server slash command handling with mocked dependencies."""

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


@patch("bot.web_server.run_daily_digest", return_value="digest")
@patch("bot.web_server.create_signals_database")
def test_lobbypulse_command(mock_db: object, mock_run: object, client: object) -> None:
    mock_db.return_value = None  # not used in handler
    resp = client.post(
        "/lobbylens/commands",
        data={"command": "/lobbypulse", "text": "", "channel_id": "ch"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["response_type"] == "in_channel"
    assert "digest" in data["text"]


@patch("bot.web_server.run_mini_digest", return_value="mini-digest")
@patch("bot.web_server.create_signals_database")
def test_lobbypulse_mini_command(
    mock_db: object, mock_run: object, client: object
) -> None:
    mock_db.return_value = None
    resp = client.post(
        "/lobbylens/commands",
        data={"command": "/lobbypulse", "text": "mini", "channel_id": "ch"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["text"] == "mini-digest"


@patch("bot.web_server.create_signals_database")
def test_threshold_show_settings(mock_db: object, client: object) -> None:
    # Mock DB with simple settings
    mock_db.return_value.get_channel_settings.return_value = {
        "mini_digest_threshold": 5,
        "high_priority_threshold": 2.0,
        "surge_threshold": 100.0,
    }
    resp = client.post(
        "/lobbylens/commands",
        data={"command": "/threshold", "text": "", "channel_id": "ch"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert "Threshold Settings" in data["text"]
    assert "5" in data["text"]
