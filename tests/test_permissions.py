"""Tests for bot/permissions.py - Permission management."""

from typing import Any
from unittest.mock import Mock, patch

import pytest
import requests

from bot.permissions import PermissionManager


class TestPermissionManager:
    """Tests for PermissionManager class."""

    @pytest.fixture
    def permission_manager(self) -> PermissionManager:
        """Create PermissionManager instance."""
        return PermissionManager(slack_token="xoxb-test-token")

    def test_init_with_token(self) -> None:
        """Test PermissionManager initialization with token."""
        manager = PermissionManager(slack_token="xoxb-test-token")
        assert manager.slack_token == "xoxb-test-token"
        assert manager._admin_cache == {}
        assert manager._cache_ttl == 300

    def test_init_without_token(self) -> None:
        """Test PermissionManager initialization without token."""
        with patch.dict("os.environ", {}, clear=True):
            manager = PermissionManager()
            assert manager.slack_token is None

    @patch("bot.permissions.requests.get")
    def test_is_channel_admin_success(
        self, mock_get: Mock, permission_manager: PermissionManager
    ) -> None:
        """Test successful channel admin check."""
        # Mock channel info response
        info_response = Mock()
        info_response.ok = True
        info_response.json.return_value = {
            "ok": True,
            "channel": {"id": "C123", "creator": "U123"},
        }

        # Mock members response
        members_response = Mock()
        members_response.ok = True
        members_response.json.return_value = {
            "ok": True,
            "members": ["U123", "U456"],
        }

        # Mock users.list response (workspace admins)
        users_response = Mock()
        users_response.ok = True
        users_response.json.return_value = {
            "ok": True,
            "members": [
                {"id": "U123", "is_admin": True},
                {"id": "U456", "is_admin": False},
            ],
        }

        mock_get.side_effect = [info_response, members_response, users_response]

        # Test admin user (channel creator)
        assert permission_manager.is_channel_admin("C123", "U123") is True

        # Test non-admin user
        assert permission_manager.is_channel_admin("C123", "U456") is False

    @patch("bot.permissions.requests.get")
    @patch("time.time")
    def test_is_channel_admin_api_error(
        self, mock_time: Mock, mock_get: Mock, permission_manager: PermissionManager
    ) -> None:
        """Test channel admin check with API error (fail open)."""
        # Mock time.time to control cache
        mock_time.return_value = 1000.0
        # API call raises exception - this will be caught by _fetch_channel_admins
        # which returns empty set, so user won't be in admins
        mock_get.side_effect = requests.RequestException("API Error")

        # _fetch_channel_admins catches exception and returns empty set
        # So user_id won't be in empty set, returns False
        # But if there's an exception in is_channel_admin itself (not in _fetch),
        # it would return True (fail open)
        result = permission_manager.is_channel_admin("C123", "U123")
        # When _fetch_channel_admins catches exception, it returns empty set
        # So result is False (user not in empty set)
        # The fail-open only happens if exception is in is_channel_admin itself
        assert result is False

    def test_is_channel_admin_no_token(self) -> None:
        """Test channel admin check without token."""
        manager = PermissionManager(slack_token=None)
        # When no token, _fetch_channel_admins returns empty set (no exception)
        # So user_id won't be in empty set, returns False
        result = manager.is_channel_admin("C123", "U123")
        # Actual behavior: returns False when no token (empty admin set)
        assert result is False

    @patch("bot.permissions.requests.get")
    def test_is_channel_admin_cache(
        self, mock_get: Mock, permission_manager: PermissionManager
    ) -> None:
        """Test that channel admin check uses cache."""
        # Mock successful response
        info_response = Mock()
        info_response.ok = True
        info_response.json.return_value = {
            "ok": True,
            "channel": {"id": "C123", "creator": "U123"},
        }

        members_response = Mock()
        members_response.ok = True
        members_response.json.return_value = {
            "ok": True,
            "members": ["U123"],
        }

        users_response = Mock()
        users_response.ok = True
        users_response.json.return_value = {
            "ok": True,
            "members": [{"id": "U123", "is_admin": True}],
        }

        mock_get.side_effect = [info_response, members_response, users_response]

        # First call - should fetch from API
        result1 = permission_manager.is_channel_admin("C123", "U123")
        assert result1 is True
        assert mock_get.call_count == 3  # info, members, users.list

        # Second call - should use cache
        result2 = permission_manager.is_channel_admin("C123", "U123")
        assert result2 is True
        # Should not make additional API calls
        assert mock_get.call_count == 3

    @patch("bot.permissions.requests.get")
    def test_fetch_channel_admins_success(
        self, mock_get: Mock, permission_manager: PermissionManager
    ) -> None:
        """Test fetching channel admins successfully."""
        info_response = Mock()
        info_response.ok = True
        info_response.json.return_value = {
            "ok": True,
            "channel": {"id": "C123", "creator": "U123"},
        }

        members_response = Mock()
        members_response.ok = True
        members_response.json.return_value = {
            "ok": True,
            "members": ["U123", "U456"],
        }

        # Mock users.list response (workspace admins)
        users_response = Mock()
        users_response.ok = True
        users_response.json.return_value = {
            "ok": True,
            "members": [
                {"id": "U123", "is_admin": True},
                {"id": "U456", "is_admin": False},
            ],
        }

        mock_get.side_effect = [info_response, members_response, users_response]

        admins = permission_manager._fetch_channel_admins("C123")
        # Should include channel creator and workspace admin
        assert "U123" in admins
        assert "U456" not in admins

    @patch("bot.permissions.requests.get")
    def test_fetch_channel_admins_api_error(
        self, mock_get: Mock, permission_manager: PermissionManager
    ) -> None:
        """Test fetching channel admins with API error."""
        mock_get.side_effect = requests.RequestException("API Error")

        admins = permission_manager._fetch_channel_admins("C123")
        assert admins == set()

    @patch("bot.permissions.requests.get")
    def test_fetch_channel_admins_slack_error(
        self, mock_get: Mock, permission_manager: PermissionManager
    ) -> None:
        """Test fetching channel admins with Slack API error."""
        info_response = Mock()
        info_response.ok = True
        info_response.json.return_value = {
            "ok": False,
            "error": "channel_not_found",
        }

        mock_get.return_value = info_response

        admins = permission_manager._fetch_channel_admins("C123")
        assert admins == set()
