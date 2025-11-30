"""Security-focused tests for Slack signature verification in web_server."""

import hashlib
import hmac
from unittest.mock import patch

from bot.config import settings
from bot.web_server import create_web_server
from tests.slack_stubs import StubSlackApp


def _sign(body: str, timestamp: str, secret: str) -> str:
    """Generate Slack-style signature for tests."""
    sig_basestring = f"v0:{timestamp}:{body}"
    return (
        "v0="
        + hmac.new(secret.encode(), sig_basestring.encode(), hashlib.sha256).hexdigest()
    )


@patch("bot.web_server.run_mini_digest", return_value="mini-digest")
@patch("bot.web_server.create_signals_database")
def test_slash_command_accepts_valid_signature(
    mock_db: object, _mock_digest: object, monkeypatch: object
) -> None:
    """Requests signed over the raw body should pass verification."""
    secret = "secret"
    monkeypatch.setattr(settings, "slack_signing_secret", secret)
    monkeypatch.setattr("bot.web_server.time.time", lambda: 1000.0)
    mock_db.return_value = None

    app = create_web_server(slack_app=StubSlackApp())
    client = app.test_client()

    body = "text=mini&command=%2Flobbypulse&channel_id=ch"
    timestamp = "1000"
    signature = _sign(body, timestamp, secret)

    resp = client.post(
        "/lobbylens/commands",
        data=body,
        content_type="application/x-www-form-urlencoded",
        headers={
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        },
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["response_type"] == "in_channel"
    assert payload["text"] == "mini-digest"


@patch("bot.web_server.create_signals_database")
def test_event_accepts_valid_signature(mock_db: object, monkeypatch: object) -> None:
    """Events endpoint should accept a correctly signed request."""
    secret = "secret"
    monkeypatch.setattr(settings, "slack_signing_secret", secret)
    monkeypatch.setattr("bot.web_server.time.time", lambda: 2000.0)
    mock_db.return_value = None

    app = create_web_server(slack_app=StubSlackApp())
    client = app.test_client()

    body = '{"type":"event_callback","event":{"type":"message"}}'
    timestamp = "2000"
    signature = _sign(body, timestamp, secret)

    resp = client.post(
        "/lobbylens/events",
        data=body,
        content_type="application/json",
        headers={
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        },
    )

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "ok"


@patch("bot.web_server.create_signals_database")
def test_slash_command_rejects_invalid_signature(
    mock_db: object, monkeypatch: object
) -> None:
    """Invalid signatures should be rejected with 401."""
    secret = "secret"
    monkeypatch.setattr(settings, "slack_signing_secret", secret)
    monkeypatch.setattr("bot.web_server.time.time", lambda: 1000.0)
    mock_db.return_value = None

    app = create_web_server(slack_app=StubSlackApp())
    client = app.test_client()

    body = "text=&command=%2Flobbypulse&channel_id=ch"
    timestamp = "1000"
    bad_signature = _sign("tampered-body", timestamp, secret)

    resp = client.post(
        "/lobbylens/commands",
        data=body,
        content_type="application/x-www-form-urlencoded",
        headers={
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": bad_signature,
        },
    )

    assert resp.status_code == 401
    payload = resp.get_json()
    assert "Unauthorized" in payload["text"]


@patch("bot.web_server.create_signals_database")
def test_event_rejects_invalid_signature(mock_db: object, monkeypatch: object) -> None:
    """Events endpoint should reject tampered signatures."""
    secret = "secret"
    monkeypatch.setattr(settings, "slack_signing_secret", secret)
    monkeypatch.setattr("bot.web_server.time.time", lambda: 2000.0)
    mock_db.return_value = None

    app = create_web_server(slack_app=StubSlackApp())
    client = app.test_client()

    body = '{"type":"event_callback","event":{"type":"message"}}'
    timestamp = "2000"
    bad_signature = _sign("altered", timestamp, secret)

    resp = client.post(
        "/lobbylens/events",
        data=body,
        content_type="application/json",
        headers={
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": bad_signature,
        },
    )

    assert resp.status_code == 401
    payload = resp.get_json()
    assert payload["status"] == "error"
    assert payload["message"] == "Unauthorized"


@patch("bot.web_server.create_signals_database")
def test_event_rejects_stale_timestamp(mock_db: object, monkeypatch: object) -> None:
    """Events endpoint should reject replayed requests outside the 5-minute window."""
    secret = "secret"
    monkeypatch.setattr(settings, "slack_signing_secret", secret)
    monkeypatch.setattr("bot.web_server.time.time", lambda: 2000.0)
    mock_db.return_value = None

    app = create_web_server()
    client = app.test_client()

    body = '{"type":"event_callback","event":{"type":"message"}}'
    # Timestamp is 1000 seconds old; allowed window is 300.
    timestamp = "1000"
    signature = _sign(body, timestamp, secret)

    resp = client.post(
        "/lobbylens/events",
        data=body,
        content_type="application/json",
        headers={
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        },
    )

    assert resp.status_code == 401
    payload = resp.get_json()
    assert payload["status"] == "error"
    assert payload["message"] == "Unauthorized"
