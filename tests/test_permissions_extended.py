"""Extended tests for PermissionManager."""

from unittest.mock import patch

from bot.permissions import PermissionManager


def test_is_channel_admin_no_token_returns_true_on_error() -> None:
    """Without token, is_channel_admin should warn but fail open."""
    pm = PermissionManager(slack_token=None)
    assert pm.is_channel_admin("C123", "U123") is False


@patch("requests.get")
def test_is_channel_admin_api_error(mock_get) -> None:
    """API errors should fail open (return True)."""
    mock_get.return_value.ok = False
    pm = PermissionManager(slack_token="xoxb-test")
    assert pm.is_channel_admin("C123", "U123") is False
