"""Tests for configuration management."""

import os
from unittest.mock import patch

import pytest

from bot.config import Settings


def test_settings_defaults() -> None:
    """Test default settings values."""
    # Clear environment variables to test defaults
    with patch.dict(os.environ, {}, clear=True):
        # Create Settings instance without .env file loading
        settings = Settings(
            _env_file=None, _env_file_encoding=None, _env_ignore_empty=True
        )

        assert settings.database_file == "lobbywatch.db"
        assert settings.database_url is None
        assert settings.opensecrets_api_key is None
        assert settings.propublica_api_key is None
        assert settings.congress_api_key is None
        assert settings.federal_register_api_key is None
        assert settings.regulations_gov_api_key is None
        assert settings.slack_webhook_url is None
        assert settings.slack_bot_token is None
        assert settings.slack_signing_secret is None
        assert settings.lobbylens_channels is None
        assert settings.environment == "development"
        assert settings.admin_users is None
        assert settings.log_level == "INFO"
        assert settings.dry_run is False


def test_settings_from_env() -> None:
    """Test settings loaded from environment variables."""
    env_vars = {
        "DATABASE_FILE": "/custom/path.db",
        "OPENSECRETS_API_KEY": "test_os_key",
        "PROPUBLICA_API_KEY": "test_pp_key",
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test",
        "LOG_LEVEL": "DEBUG",
        "DRY_RUN": "true",
    }

    with patch.dict(os.environ, env_vars):
        settings = Settings()

        assert settings.database_file == "/custom/path.db"
        assert settings.opensecrets_api_key == "test_os_key"
        assert settings.propublica_api_key == "test_pp_key"
        assert settings.slack_webhook_url == "https://hooks.slack.com/test"
        assert settings.log_level == "DEBUG"
        assert settings.dry_run is True


def test_notifier_type_detection() -> None:
    """Test notifier type detection logic."""
    # Test with webhook URL
    with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}):
        settings = Settings(_env_file=None)
        assert settings.notifier_type == "slack"

    # Test without webhook URL
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
        assert settings.notifier_type is None


def test_validate_notifier_config() -> None:
    """Test notifier configuration validation."""
    # Test with valid webhook configuration
    with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}):
        settings = Settings(_env_file=None)
        # Should not raise an exception
        settings.validate_notifier_config()

    # Test with valid bot token configuration
    with patch.dict(
        os.environ,
        {"SLACK_BOT_TOKEN": "xoxb-test", "SLACK_SIGNING_SECRET": "test-secret"},
    ):
        settings = Settings(_env_file=None)
        # Should not raise an exception
        settings.validate_notifier_config()

    # Test with no configuration (should raise exception)
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(_env_file=None)
        with pytest.raises(ValueError, match="No Slack configuration found"):
            settings.validate_notifier_config()
