"""Tests for notification system."""

from unittest.mock import Mock, patch

import pytest
import requests

from bot.notifiers.base import NotificationError
from bot.notifiers.slack import SlackNotifier


class TestSlackNotifier:
    """Tests for Slack notifier."""

    def test_init(self):
        """Test SlackNotifier initialization."""
        webhook_url = "https://hooks.slack.com/services/TEST/TEST/TEST"
        notifier = SlackNotifier(webhook_url)
        assert notifier.webhook_url == webhook_url

    def test_send_success(self, mock_slack_webhook):
        """Test successful message sending."""
        notifier = SlackNotifier("https://hooks.slack.com/services/TEST/TEST/TEST")

        # Should not raise an exception
        notifier.send("Test message")

        # Verify the request was made correctly
        assert len(mock_slack_webhook.request_history) == 1
        request = mock_slack_webhook.request_history[0]

        assert request.method == "POST"
        assert request.json()["text"] == "Test message"
        assert request.json()["username"] == "LobbyLens"
        assert "icon_emoji" in request.json()

    def test_send_http_error(self, mock_slack_webhook):
        """Test handling of HTTP errors."""
        mock_slack_webhook.post(
            "https://hooks.slack.com/services/TEST/TEST/TEST",
            status_code=404,
            text="Not Found",
        )

        notifier = SlackNotifier("https://hooks.slack.com/services/TEST/TEST/TEST")

        with pytest.raises(NotificationError, match="Slack notification failed"):
            notifier.send("Test message")

    def test_send_slack_error_response(self, mock_slack_webhook):
        """Test handling of Slack error responses."""
        mock_slack_webhook.post(
            "https://hooks.slack.com/services/TEST/TEST/TEST",
            status_code=200,
            text="channel_not_found",
        )

        notifier = SlackNotifier("https://hooks.slack.com/services/TEST/TEST/TEST")

        with pytest.raises(NotificationError, match="Slack webhook returned"):
            notifier.send("Test message")

    @patch("requests.post")
    def test_send_timeout(self, mock_post):
        """Test handling of request timeouts."""
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        notifier = SlackNotifier("https://hooks.slack.com/services/TEST/TEST/TEST")

        with pytest.raises(NotificationError, match="Slack notification failed"):
            notifier.send("Test message")

        # Verify timeout was set correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["timeout"] == 30

    def test_send_with_special_formatting(self, mock_slack_webhook):
        """Test sending messages with Slack formatting."""
        notifier = SlackNotifier("https://hooks.slack.com/services/TEST/TEST/TEST")

        message = "*Bold text* and _italic text_ with <https://example.com|links>"
        notifier.send(message)

        request = mock_slack_webhook.request_history[0]
        assert request.json()["text"] == message
        assert request.json()["unfurl_links"] is True
        assert request.json()["unfurl_media"] is True
