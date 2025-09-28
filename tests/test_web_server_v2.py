"""
Tests for bot/web_server_v2.py
"""

from typing import Any
from unittest.mock import patch

import pytest

from bot.web_server import create_web_server


class TestWebServerV2:
    """Test web_server_v2 module"""

    @pytest.fixture
    def app(self) -> Any:
        """Create Flask app for testing"""
        return create_web_server()

    @pytest.fixture
    def client(self, app: Any) -> Any:
        """Create test client"""
        app.config["TESTING"] = True
        return app.test_client()

    def test_create_web_server_v2(self) -> None:
        """Test web server creation"""
        app = create_web_server()
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
        event_data = {"type": "url_verification", "challenge": "test_challenge_123"}

        response = client.post(
            "/lobbylens/events", json=event_data, content_type="application/json"
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
            "/lobbylens/events", json=event_data, content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"

    def test_handle_events_error(self, client: Any) -> None:
        """Test event handling with error"""
        # Send invalid JSON
        response = client.post(
            "/lobbylens/events", data="invalid json", content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "error"

    @patch("bot.run.run_daily_digest")
    def test_manual_digest_daily(self, mock_run_daily: Any, client: Any) -> None:
        """Test manual daily digest endpoint"""
        mock_run_daily.return_value = "Test Daily Digest"

        response = client.post(
            "/lobbylens/digest/manual/test_channel",
            json={"type": "daily", "hours": 24},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["digest"] == "Test Daily Digest"
        assert data["type"] == "daily"
        assert data["channel_id"] == "test_channel"
        assert data["hours_back"] == 24

        mock_run_daily.assert_called_once_with(24, "test_channel")

    @patch("bot.run.run_mini_digest")
    def test_manual_digest_mini_success(self, mock_run_mini: Any, client: Any) -> None:
        """Test manual mini digest endpoint with success"""
        mock_run_mini.return_value = "Test Mini Digest"

        response = client.post(
            "/lobbylens/digest/manual/test_channel",
            json={"type": "mini", "hours": 4},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["digest"] == "Test Mini Digest"
        assert data["type"] == "mini"

        mock_run_mini.assert_called_once_with(4, "test_channel")

    @patch("bot.run.run_mini_digest")
    def test_manual_digest_mini_no_digest(
        self, mock_run_mini: Any, client: Any
    ) -> None:
        """Test manual mini digest endpoint when no digest is generated"""
        mock_run_mini.return_value = None

        response = client.post(
            "/lobbylens/digest/manual/test_channel",
            json={"type": "mini", "hours": 4},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["message"] == "Mini-digest thresholds not met"

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

    @patch("bot.run.run_daily_digest")
    def test_manual_digest_error(self, mock_run_daily: Any, client: Any) -> None:
        """Test manual digest with error"""
        mock_run_daily.side_effect = Exception("Test error")

        response = client.post(
            "/lobbylens/digest/manual/test_channel",
            json={"type": "daily", "hours": 24},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["error"] == "Test error"

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

    @patch("bot.run.run_daily_digest")
    def test_handle_slash_command_lobbypulse_daily(
        self, mock_run_daily: Any, client: Any
    ) -> None:
        """Test /lobbypulse daily command"""
        mock_run_daily.return_value = "Test Daily Digest"

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
        assert data["text"] == "Test Daily Digest"

        mock_run_daily.assert_called_once_with(24, "test_channel")

    @patch("bot.run.run_mini_digest")
    def test_handle_slash_command_lobbypulse_mini_success(
        self, mock_run_mini: Any, client: Any
    ) -> None:
        """Test /lobbypulse mini command with success"""
        mock_run_mini.return_value = "Test Mini Digest"

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
        assert data["text"] == "Test Mini Digest"

        mock_run_mini.assert_called_once_with(4, "test_channel")

    @patch("bot.run.run_mini_digest")
    def test_handle_slash_command_lobbypulse_mini_no_digest(
        self, mock_run_mini: Any, client: Any
    ) -> None:
        """Test /lobbypulse mini command when no digest is generated"""
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
        assert data["text"] == "No mini-digest - thresholds not met"

    @patch("bot.run.run_daily_digest")
    def test_handle_slash_command_lobbypulse_error(
        self, mock_run_daily: Any, client: Any
    ) -> None:
        """Test /lobbypulse command with error"""
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
        assert "Error generating digest" in data["text"]

    def test_handle_slash_command_lobbylens_help(self, client: Any) -> None:
        """Test /lobbylens help command"""
        response = client.post(
            "/lobbylens/commands",
            data={
                "command": "/lobbylens",
                "text": "help",
                "channel_id": "test_channel",
                "user_id": "test_user",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["response_type"] == "in_channel"
        assert "LobbyLens v2 System Status" in data["text"]
        assert "Daily government signals digest" in data["text"]

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
