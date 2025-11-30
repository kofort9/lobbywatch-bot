"""Targeted tests for SlackApp command and event handlers."""

import hashlib
import hmac

from bot import slack_app as slack_mod


class DummyDB:
    """Minimal DB stub for SlackApp."""

    def __init__(self) -> None:
        self.settings = {
            "threshold_filings": 1,
            "threshold_amount": 1000,
            "show_descriptions": True,
        }
        self.watchlist: list[dict[str, object]] = []

    def get_channel_watchlist(
        self, channel_id: str
    ) -> list[dict[str, object]]:  # noqa: ARG002
        return self.watchlist

    def get_channel_settings(
        self, channel_id: str
    ) -> dict[str, object]:  # noqa: ARG002
        return self.settings


class DummyMatching:
    """Predictable matching service responses."""

    def __init__(self, db_manager: object) -> None:  # noqa: ARG002
        self.candidates = [
            {"entity_type": "client", "id": 1, "name": "Acme", "score": 95}
        ]

    def process_watchlist_add(
        self, channel_id: str, search_term: str
    ) -> dict[str, object]:  # noqa: ARG002
        return {
            "status": "confirmation_needed",
            "message": "choose",
            "candidates": self.candidates,
            "search_term": search_term,
        }

    def process_confirmation_response(self, **_: object) -> dict[str, str]:
        return {"status": "success", "message": "added"}


class DummyDigest:
    """Digest stub that echoes type."""

    def __init__(self, db_manager: object) -> None:  # noqa: ARG002
        pass

    def compute_enhanced_digest(
        self, channel_id: str, digest_type: str = "daily"
    ) -> str:
        return f"{digest_type}-digest for {channel_id}"


def _build_app(monkeypatch: object) -> slack_mod.SlackApp:
    """Helper to create SlackApp with stubbed dependencies."""
    monkeypatch.setattr(slack_mod, "MatchingService", DummyMatching)
    monkeypatch.setattr(slack_mod, "EnhancedDigestComputer", DummyDigest)
    return slack_mod.SlackApp(DummyDB())


def test_watchlist_command_records_confirmation(monkeypatch: object) -> None:
    """Watchlist add should emit confirmation flow and cache the key."""
    monkeypatch.setattr(slack_mod.time, "time", lambda: 1700.0)
    app = _build_app(monkeypatch)

    response = app.handle_slash_command(
        {
            "command": "/watchlist",
            "text": "add MegaCorp",
            "channel_id": "C1",
            "user_id": "U1",
        }
    )

    confirmation_key = "C1:U1:1700"
    assert confirmation_key in app.pending_confirmations
    assert response["response_type"] == "ephemeral"
    assert "Confirmation key" in response["text"]


def test_handle_message_event_processes_confirmation(monkeypatch: object) -> None:
    """Confirmation messages should be routed to the matching service."""
    monkeypatch.setattr(slack_mod.time, "time", lambda: 2000.0)
    app = _build_app(monkeypatch)
    key = "C9:U9:2000"
    app.pending_confirmations[key] = {
        "search_term": "Acme",
        "candidates": [{"name": "Acme", "entity_type": "client", "id": 1, "score": 99}],
        "channel_id": "C9",
        "user_id": "U9",
        "timestamp": 1950.0,
    }

    posted: list[tuple[str, str]] = []
    app.post_message = lambda channel, text, thread_ts=None: posted.append(
        (channel, text)
    ) or {  # type: ignore[assignment]
        "ok": True
    }

    result = app.handle_message_event(
        {"type": "message", "text": f"1 {key}", "channel": "C9", "user": "U9"}
    )

    assert result == {"status": "success", "message": "added"}
    assert posted == [("C9", "added")]
    assert key not in app.pending_confirmations


def test_lobbypulse_command_posts_digest(monkeypatch: object) -> None:
    """Manual digest command should trigger posting via Slack API wrapper."""
    app = _build_app(monkeypatch)

    posted: list[tuple[str, str]] = []
    app.post_message = lambda channel, text, thread_ts=None: posted.append(
        (channel, text)
    ) or {  # type: ignore[assignment]
        "ok": True
    }

    response = app.handle_slash_command(
        {
            "command": "/lobbypulse",
            "text": "mini",
            "channel_id": "C55",
            "user_id": "U55",
        }
    )

    assert response["response_type"] == "in_channel"
    assert posted == [("C55", "mini-digest for C55")]


def test_verify_slack_request_dev_mode_without_secret(monkeypatch: object) -> None:
    """Missing signing secret in dev should skip verification."""
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
    app = _build_app(monkeypatch)

    assert app.verify_slack_request({}, "body") is True


def test_verify_slack_request_valid_signature(monkeypatch: object) -> None:
    """Valid signature should pass verification when secret is set."""
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret")
    monkeypatch.setattr(slack_mod.time, "time", lambda: 1000.0)
    app = _build_app(monkeypatch)

    body = "payload"
    timestamp = "995"
    sig_basestring = f"v0:{timestamp}:{body}"
    signature = (
        "v0=" + hmac.new(b"secret", sig_basestring.encode(), hashlib.sha256).hexdigest()
    )

    assert app.verify_slack_request(
        {"X-Slack-Request-Timestamp": timestamp, "X-Slack-Signature": signature},
        body,
    )


def test_verify_slack_request_missing_signature(monkeypatch: object) -> None:
    """Missing signature headers should fail verification when secret exists."""
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "secret")
    app = _build_app(monkeypatch)

    assert app.verify_slack_request({"X-Slack-Request-Timestamp": "1"}, "x") is False


def test_lobbylens_lda_digest_posts(monkeypatch: object) -> None:
    """LDA digest subcommand should post digest content."""
    monkeypatch.setenv(
        "SLACK_SIGNING_SECRET", "secret"
    )  # ensure production branch not used
    monkeypatch.setattr("bot.utils.is_lda_enabled", lambda: True)

    class DummyPermission:
        def can_post_digest(
            self, channel_id: str, user_id: str
        ) -> bool:  # noqa: ARG002
            return True

        def get_permission_error_message(self, *_: object) -> str:
            return "nope"

    class DummyLDA:
        def __init__(self, db_manager: object) -> None:  # noqa: ARG002
            pass

        def generate_digest(
            self, channel_id: str, quarter: str | None = None
        ) -> str:  # noqa: ARG002
            return "lda digest"

    posted: list[tuple[str, str]] = []

    monkeypatch.setattr("bot.lda_front_page_digest.LDAFrontPageDigest", DummyLDA)
    monkeypatch.setattr(
        "bot.permissions.get_permission_manager", lambda: DummyPermission()
    )

    app = _build_app(monkeypatch)
    app.post_message = lambda channel, text, thread_ts=None: posted.append(
        (channel, text)
    ) or {  # type: ignore[assignment]
        "ok": True
    }

    response = app.handle_slash_command(
        {
            "command": "/lobbylens",
            "text": "lda digest q=2024Q4",
            "channel_id": "C123",
            "user_id": "U1",
        }
    )

    assert response["response_type"] == "ephemeral"
    assert posted == [("C123", "lda digest")]


def test_lobbylens_lda_top_clients(monkeypatch: object) -> None:
    """Top clients command should format ranking."""
    monkeypatch.setattr("bot.utils.is_lda_enabled", lambda: True)

    class DummyLDA:
        def __init__(self, db_manager: object) -> None:  # noqa: ARG002
            pass

        def get_top_clients(
            self, quarter: str | None, limit: int
        ) -> list[dict[str, object]]:  # noqa: ARG002
            return [
                {"name": "Client A", "total_amount": 1000, "filing_count": 2},
                {"name": "Client B", "total_amount": 500, "filing_count": 1},
            ]

    monkeypatch.setattr("bot.lda_front_page_digest.LDAFrontPageDigest", DummyLDA)
    monkeypatch.setattr("bot.permissions.get_permission_manager", lambda: object())

    app = _build_app(monkeypatch)
    response = app.handle_slash_command(
        {
            "command": "/lobbylens",
            "text": "lda top clients q=2025Q1 n=2",
            "channel_id": "C1",
            "user_id": "U1",
        }
    )

    assert "Top Clients" in response["text"]
    assert "Client A" in response["text"]


def test_lobbylens_lda_issues_empty(monkeypatch: object) -> None:
    """Issues command should handle empty result set."""
    monkeypatch.setattr("bot.utils.is_lda_enabled", lambda: True)

    class DummyLDA:
        def __init__(self, db_manager: object) -> None:  # noqa: ARG002
            pass

        def get_issues_summary(
            self, quarter: str | None
        ) -> list[dict[str, object]]:  # noqa: ARG002
            return []

    monkeypatch.setattr("bot.lda_front_page_digest.LDAFrontPageDigest", DummyLDA)
    monkeypatch.setattr("bot.permissions.get_permission_manager", lambda: object())

    app = _build_app(monkeypatch)
    response = app.handle_slash_command(
        {
            "command": "/lobbylens",
            "text": "lda issues q=2025Q1",
            "channel_id": "C1",
            "user_id": "U1",
        }
    )

    assert "No issues" in response["text"]


def test_lobbylens_lda_entity(monkeypatch: object) -> None:
    """Entity search should format entity details."""
    monkeypatch.setattr("bot.utils.is_lda_enabled", lambda: True)

    class DummyLDA:
        def __init__(self, db_manager: object) -> None:  # noqa: ARG002
            pass

        def search_entity(self, name: str) -> dict[str, object]:  # noqa: ARG002
            return {
                "entity": {"name": "Acme", "type": "client"},
                "total_amount": 123000,
                "filing_count": 3,
                "quarter": "2025Q1",
                "filings": [
                    {"client_name": "Acme", "registrant_name": "Reg A", "amount": 1000}
                ],
            }

    monkeypatch.setattr("bot.lda_front_page_digest.LDAFrontPageDigest", DummyLDA)
    monkeypatch.setattr("bot.permissions.get_permission_manager", lambda: object())

    app = _build_app(monkeypatch)
    response = app.handle_slash_command(
        {
            "command": "/lobbylens",
            "text": "lda entity Acme",
            "channel_id": "C1",
            "user_id": "U1",
        }
    )

    assert "Acme" in response["text"]
    assert "Quarter" in response["text"]


def test_lobbylens_lda_watchlist_list(monkeypatch: object) -> None:
    """Watchlist list should enumerate items when present."""
    monkeypatch.setattr("bot.utils.is_lda_enabled", lambda: True)

    class DummyLDA:
        def __init__(self, db_manager: object) -> None:  # noqa: ARG002
            pass

    monkeypatch.setattr("bot.lda_front_page_digest.LDAFrontPageDigest", DummyLDA)
    monkeypatch.setattr("bot.permissions.get_permission_manager", lambda: object())

    app = _build_app(monkeypatch)
    app.db_manager.watchlist = [
        {"display_name": "Acme", "entity_type": "client"},
        {"display_name": "Reg A", "entity_type": "registrant"},
    ]
    response = app.handle_slash_command(
        {
            "command": "/lobbylens",
            "text": "lda watchlist list",
            "channel_id": "C1",
            "user_id": "U1",
        }
    )

    assert "LDA Watchlist" in response["text"]
    assert "Acme" in response["text"]
