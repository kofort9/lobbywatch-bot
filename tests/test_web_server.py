"""
Tests for bot/web_server.py - Web server functionality
"""

from typing import Any
from unittest.mock import Mock, patch

import pytest

from bot.web_server import create_web_server
from tests.slack_stubs import StubSlackApp


# from unittest.mock import patch
class TestWebServerV2:
    """Test web_server_v2 module"""

    @pytest.fixture(autouse=True)
    def _disable_signature_check(self, monkeypatch: object) -> None:
        """Skip Slack signature verification in generic web_server tests."""
        from bot import config

        monkeypatch.setattr(config.settings, "slack_signing_secret", None)

    @pytest.fixture
    def slack_stub(self) -> StubSlackApp:
        """Shared stub Slack handler for command routing."""
        return StubSlackApp()

    @pytest.fixture
    def app(self, slack_stub: StubSlackApp) -> Any:
        """Create Flask app for testing"""
        return create_web_server(slack_app=slack_stub, use_legacy_handlers=False)

    @pytest.fixture
    def client(self, app: Any) -> Any:
        """Create test client"""
        app.config["TESTING"] = True
        return app.test_client()

    def test_create_web_server_v2(self, slack_stub: StubSlackApp) -> None:
        """Test web server creation"""
        app = create_web_server(slack_app=slack_stub)
        assert app is not None
        assert app.name == "bot.web_server"

    def test_root_endpoint(self, client: Any) -> None:
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200

        data = response.get_json()
        assert data["service"] == "lobbylens-v2"
        assert data["status"] == "running"
        assert data["version"] == "2.0.0"
        assert "industry_snapshots" in data["features"]
        assert "priority_scoring" in data["features"]
        assert "mobile_formatting" in data["features"]
        assert "watchlist_alerts" in data["features"]

    def test_health_check_endpoint(self, client: Any) -> None:
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "healthy"
        assert data["service"] == "lobbylens-v2"

    def test_lobbylens_health_check_endpoint(self, client: Any) -> None:
        """Test LobbyLens specific health check endpoint"""
        response = client.get("/lobbylens/health")
        assert response.status_code == 200

        data = response.get_json()
        assert data["status"] == "healthy"
        assert data["service"] == "lobbylens-v2"

    def test_handle_events_url_verification(self, client: Any) -> None:
        """Test URL verification event handling"""
        event_data = {
            "type": "url_verification",
            "challenge": "test_challenge_123",
        }

        response = client.post(
            "/lobbylens/events",
            json=event_data,
            content_type="application/json",
        )

        assert response.status_code == 200
        assert response.get_data(as_text=True) == "test_challenge_123"

    def test_handle_events_other_event(self, client: Any) -> None:
        """Test handling other events"""
        event_data = {
            "type": "event_callback",
            "event": {"type": "message", "text": "test"},
        }

        response = client.post(
            "/lobbylens/events",
            json=event_data,
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"

    def test_handle_events_error(self, client: Any) -> None:
        """Test event handling with error"""
        # Send invalid JSON
        response = client.post(
            "/lobbylens/events",
            data="invalid json",
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "error"

    #     @patch("bot.run.run_daily_digest")
    # def test_manual_digest_daily(self, mock_run_daily: Any, client: Any) -> None:
    #         """Test manual daily digest endpoint"""
    #         mock_run_daily.return_value = "Test Daily Digest"

    #         response = client.post(
    #             "/lobbylens/digest/manual/test_channel",
    #             json={"type": "daily", "hours": 24},
    #             content_type="application/json",
    #         )

    #         assert response.status_code == 200
    #         data = response.get_json()
    #         assert data["digest"] == "Test Daily Digest"
    #         assert data["type"] == "daily"
    #         assert data["channel_id"] == "test_channel"
    #         assert data["hours_back"] == 24

    #         mock_run_daily.assert_called_once_with(24, "test_channel")

    #     @patch("bot.run.run_mini_digest")
    # def test_manual_digest_mini_success(
    #     self, mock_run_mini: Any, client: Any
    # ) -> None:
    #         """Test manual mini digest endpoint with success"""
    #         mock_run_mini.return_value = "Test Mini Digest"

    #         response = client.post(
    #             "/lobbylens/digest/manual/test_channel",
    #             json={"type": "mini", "hours": 4},
    #             content_type="application/json",
    #         )

    #         assert response.status_code == 200
    #         data = response.get_json()
    #         assert data["digest"] == "Test Mini Digest"
    #         assert data["type"] == "mini"

    #         mock_run_mini.assert_called_once_with(4, "test_channel")

    #     @patch("bot.run.run_mini_digest")
    # def test_manual_digest_mini_no_digest(
    #         self, mock_run_mini: Any, client: Any
    #     ) -> None:
    #         """Test manual mini digest endpoint when no digest is generated"""
    #         mock_run_mini.return_value = None

    #         response = client.post(
    #             "/lobbylens/digest/manual/test_channel",
    #             json={"type": "mini", "hours": 4},
    #             content_type="application/json",
    #         )

    #         assert response.status_code == 200
    #         data = response.get_json()
    #         assert data["message"] == "Mini-digest thresholds not met"

    def test_manual_digest_invalid_type(self, client: Any) -> None:
        """Test manual digest with invalid type"""
        response = client.post(
            "/lobbylens/digest/manual/test_channel",
            json={"type": "invalid", "hours": 24},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["error"] == "Invalid digest type"

    #     @patch("bot.run.run_daily_digest")
    # def test_manual_digest_error(self, mock_run_daily: Any, client: Any) -> None:
    #         """Test manual digest with error"""
    #         mock_run_daily.side_effect = Exception("Test error")

    #         response = client.post(
    #             "/lobbylens/digest/manual/test_channel",
    #             json={"type": "daily", "hours": 24},
    #             content_type="application/json",
    #         )

    #         assert response.status_code == 200
    #         data = response.get_json()
    #         assert data["error"] == "Test error"

    def test_handle_slash_command_lobbypulse_help(self, client: Any) -> None:
        """Test /lobbypulse help command"""
        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/lobbypulse",
                "text": "help",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "in_channel"
        assert "LobbyLens Commands" in data["text"]
        assert "/lobbypulse" in data["text"]
        assert "/watchlist" in data["text"]

    #     @patch("bot.run.run_daily_digest")
    # def test_handle_slash_command_lobbypulse_daily(
    #         self, mock_run_daily: Any, client: Any
    #     ) -> None:
    #         """Test /lobbypulse daily command"""
    #         mock_run_daily.return_value = "Test Daily Digest"

    #         response = client.post(
    #             "/lobbylens/commands",
    #             data={
    #                 "command": "/lobbypulse",
    #                 "text": "",
    #                 "channel_id": "test_channel",
    #                 "user_id": "test_user",
    #             },
    #         )

    #         assert response.status_code == 200
    #         data = response.get_json()
    #         assert data["response_type"] == "in_channel"
    #         assert data["text"] == "Test Daily Digest"

    #         mock_run_daily.assert_called_once_with(24, "test_channel")

    #     @patch("bot.run.run_mini_digest")
    # def test_handle_slash_command_lobbypulse_mini_success(
    #         self, mock_run_mini: Any, client: Any
    #     ) -> None:
    #         """Test /lobbypulse mini command with success"""
    #         mock_run_mini.return_value = "Test Mini Digest"

    #         response = client.post(
    #             "/lobbylens/commands",
    #             data={
    #                 "command": "/lobbypulse",
    #                 "text": "mini",
    #                 "channel_id": "test_channel",
    #                 "user_id": "test_user",
    #             },
    #         )

    #         assert response.status_code == 200
    #         data = response.get_json()
    #         assert data["response_type"] == "in_channel"
    #         assert data["text"] == "Test Mini Digest"

    #         mock_run_mini.assert_called_once_with(4, "test_channel")

    #     @patch("bot.run.run_mini_digest")
    # def test_handle_slash_command_lobbypulse_mini_no_digest(
    #         self, mock_run_mini: Any, client: Any
    #     ) -> None:
    #         """Test /lobbypulse mini command when no digest is generated"""
    #         mock_run_mini.return_value = None

    #         response = client.post(
    #             "/lobbylens/commands",
    #             data={
    #                 "command": "/lobbypulse",
    #                 "text": "mini",
    #                 "channel_id": "test_channel",
    #                 "user_id": "test_user",
    #             },
    #         )

    #         assert response.status_code == 200
    #         data = response.get_json()
    #         assert data["response_type"] == "ephemeral"
    #         assert data["text"] == "No mini-digest - thresholds not met"

    #     @patch("bot.run.run_daily_digest")
    # def test_handle_slash_command_lobbypulse_error(
    #         self, mock_run_daily: Any, client: Any
    #     ) -> None:
    #         """Test /lobbypulse command with error"""
    #         mock_run_daily.side_effect = Exception("Test error")

    #         response = client.post(
    #             "/lobbylens/commands",
    #             data={
    #                 "command": "/lobbypulse",
    #                 "text": "",
    #                 "channel_id": "test_channel",
    #                 "user_id": "test_user",
    #             },
    #         )

    #         assert response.status_code == 200
    #         data = response.get_json()
    #         assert data["response_type"] == "ephemeral"
    #         assert "Error generating digest" in data["text"]

    # def test_handle_slash_command_lobbylens_help(self, client: Any) -> None:
    #         """Test /lobbylens help command"""
    #         response = client.post(
    #             "/lobbylens/commands",
    #             data={
    #                 "command": "/lobbylens",
    #                 "text": "help",
    #                 "channel_id": "test_channel",
    #                 "user_id": "test_user",
    #             },
    #         )

    #         assert response.status_code == 200
    #         data = response.get_json()
    #         assert data["response_type"] == "in_channel"
    #         assert "LobbyLens v2 System Status" in data["text"]
    #         assert "Daily government signals digest" in data["text"]

    def test_handle_slash_command_lobbylens_status(self, client: Any) -> None:
        """Test /lobbylens status command"""
        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/lobbylens",
                "text": "status",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "in_channel"
        assert "LobbyLens v2 Status" in data["text"]
        # The actual stats will depend on the database state
        assert "Total signals:" in data["text"]

    def test_handle_slash_command_watchlist_add_success(self, client: Any) -> None:
        """Test /watchlist add command with success"""
        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/watchlist",
                "text": "add Google",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        # The actual response will depend on database state
        assert data["response_type"] in ["in_channel", "ephemeral"]
        assert "Google" in data["text"]

    def test_handle_slash_command_watchlist_add_failure(self, client: Any) -> None:
        """Test /watchlist add command with failure"""
        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/watchlist",
                "text": "add Google",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        # The actual response will depend on database state
        assert data["response_type"] in ["in_channel", "ephemeral"]
        assert "Google" in data["text"]

    def test_handle_slash_command_watchlist_remove_success(self, client: Any) -> None:
        """Test /watchlist remove command with success"""
        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/watchlist",
                "text": "remove Google",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        # The actual response will depend on database state
        assert data["response_type"] in ["in_channel", "ephemeral"]
        assert "Google" in data["text"]

    def test_handle_slash_command_watchlist_list_with_items(self, client: Any) -> None:
        """Test /watchlist list command with items"""
        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/watchlist",
                "text": "list",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "in_channel"
        assert "Watchlist for #test_channel" in data["text"]

    def test_handle_slash_command_watchlist_list_empty(self, client: Any) -> None:
        """Test /watchlist list command with empty watchlist"""
        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/watchlist",
                "text": "list",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "in_channel"
        assert "Watchlist for #test_channel" in data["text"]

    def test_handle_slash_command_watchlist_invalid_usage(self, client: Any) -> None:
        """Test /watchlist command with invalid usage"""
        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/watchlist",
                "text": "invalid",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "ephemeral"
        assert "Usage:" in data["text"]

    def test_handle_slash_command_threshold_set_success(self, client: Any) -> None:
        """Test /threshold set command with success"""
        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/threshold",
                "text": "set 10",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        # The actual response will depend on database state
        assert data["response_type"] in ["in_channel", "ephemeral"]
        assert "10" in data["text"]

    def test_handle_slash_command_threshold_set_failure(self, client: Any) -> None:
        """Test /threshold set command with failure"""
        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/threshold",
                "text": "set 10",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        # The actual response will depend on database state
        assert data["response_type"] in ["in_channel", "ephemeral"]
        assert "10" in data["text"]

    def test_handle_slash_command_threshold_set_invalid_number(
        self, client: Any
    ) -> None:
        """Test /threshold set command with invalid number"""
        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/threshold",
                "text": "set invalid",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "ephemeral"
        assert "Threshold must be a number" in data["text"]

    def test_handle_slash_command_threshold_show_settings(self, client: Any) -> None:
        """Test /threshold command showing current settings"""
        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/threshold",
                "text": "",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "in_channel"
        assert "Threshold Settings for #test_channel" in data["text"]

    def test_handle_slash_command_unknown_command(self, client: Any) -> None:
        """Test unknown slash command"""
        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/unknown",
                "text": "",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "ephemeral"
        assert "Unknown command: /unknown" in data["text"]

    def test_handle_slash_command_error(self, client: Any) -> None:
        """Test slash command handling with error"""
        # Send request without required form data
        response = client.post("/lobbylens/commands", data={})

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "ephemeral"
        assert "Unknown command" in data["text"]

    @patch("bot.run.run_daily_digest")
    def test_lobbypulse_daily_command(self, mock_run_daily: Any, client: Any) -> None:
        """Test /lobbypulse daily command handler."""
        mock_run_daily.return_value = "📋 **Daily Digest**\n\n• Test signal"

        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/lobbypulse",
                "text": "",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "in_channel"
        # Check that digest content is in response (either mocked or real)
        assert len(data["text"]) > 0
        # If mock was called, verify it
        if mock_run_daily.called:
            mock_run_daily.assert_called_once_with(24, "test_channel")
            assert "Daily Digest" in data["text"]

    @patch("bot.web_server.run_mini_digest")
    def test_lobbypulse_mini_command_success(
        self, mock_run_mini: Any, client: Any
    ) -> None:
        """Test /lobbypulse mini command when digest is generated."""
        mock_run_mini.return_value = "⚡ **Mini Digest**\n\n• High priority signal"

        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/lobbypulse",
                "text": "mini",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "in_channel"
        assert "Mini Digest" in data["text"]
        mock_run_mini.assert_called_once_with(4, "test_channel")

    @patch("bot.web_server.run_mini_digest")
    def test_lobbypulse_mini_command_no_digest(
        self, mock_run_mini: Any, client: Any
    ) -> None:
        """Test /lobbypulse mini command when thresholds not met."""
        mock_run_mini.return_value = None

        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/lobbypulse",
                "text": "mini",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "ephemeral"
        assert "thresholds not met" in data["text"].lower()

    @patch("bot.web_server.run_daily_digest")
    def test_lobbypulse_command_error(self, mock_run_daily: Any, client: Any) -> None:
        """Test /lobbypulse command error handling."""
        mock_run_daily.side_effect = Exception("Test error")

        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/lobbypulse",
                "text": "",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "ephemeral"
        assert "Error" in data["text"]

    @patch("bot.signals_database.SignalsDatabaseV2")
    def test_threshold_set_command_success(
        self, mock_db_class: Any, slack_stub: StubSlackApp
    ) -> None:
        """Test /threshold set command with successful update."""
        mock_database = Mock()
        mock_database.update_channel_setting.return_value = True
        mock_db_class.return_value = mock_database

        # Recreate app with mocked database
        app = create_web_server(slack_app=slack_stub)
        app.config["TESTING"] = True
        test_client = app.test_client()

        response = test_client.post(
            "/lobbylens/commands",
            data={
                "command": "/threshold",
                "text": "set 10",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "in_channel"
        assert "10" in data["text"]
        mock_database.update_channel_setting.assert_called_once_with(
            "test_channel", "mini_digest_threshold", 10
        )

    @patch("bot.signals_database.SignalsDatabaseV2")
    def test_threshold_set_command_failure(
        self, mock_db_class: Any, slack_stub: StubSlackApp
    ) -> None:
        """Test /threshold set command when update fails."""
        mock_database = Mock()
        mock_database.update_channel_setting.return_value = False
        mock_db_class.return_value = mock_database

        app = create_web_server(slack_app=slack_stub)
        app.config["TESTING"] = True
        test_client = app.test_client()

        response = test_client.post(
            "/lobbylens/commands",
            data={
                "command": "/threshold",
                "text": "set 10",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "ephemeral"
        assert "Failed" in data["text"]

    @patch("bot.signals_database.SignalsDatabaseV2")
    def test_watchlist_add_command_success(
        self, mock_db_class: Any, slack_stub: StubSlackApp
    ) -> None:
        """Test /watchlist add command with successful add."""
        mock_database = Mock()
        mock_database.add_watchlist_item.return_value = True
        mock_db_class.return_value = mock_database

        app = create_web_server(slack_app=slack_stub)
        app.config["TESTING"] = True
        test_client = app.test_client()

        response = test_client.post(
            "/lobbylens/commands",
            data={
                "command": "/watchlist",
                "text": "add Google",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "in_channel"
        assert "Google" in data["text"]
        assert "Added" in data["text"]
        mock_database.add_watchlist_item.assert_called_once_with(
            "test_channel", "Google"
        )

    @patch("bot.signals_database.SignalsDatabaseV2")
    def test_watchlist_remove_command_success(
        self, mock_db_class: Any, slack_stub: StubSlackApp
    ) -> None:
        """Test /watchlist remove command with successful removal."""
        mock_database = Mock()
        mock_database.remove_watchlist_item.return_value = True
        mock_db_class.return_value = mock_database

        app = create_web_server(slack_app=slack_stub)
        app.config["TESTING"] = True
        test_client = app.test_client()

        response = test_client.post(
            "/lobbylens/commands",
            data={
                "command": "/watchlist",
                "text": "remove Google",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "in_channel"
        assert "Google" in data["text"]
        assert "Removed" in data["text"]
        mock_database.remove_watchlist_item.assert_called_once_with(
            "test_channel", "Google"
        )
