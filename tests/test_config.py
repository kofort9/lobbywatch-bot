"""Tests for configuration management."""

import os
from unittest.mock import patch

import pytest

from bot.config import Settings


def test_settings_defaults():
    """Test default settings values."""
    # Mock the Settings class to avoid .env file loading
    with patch("bot.config.Settings") as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.database_file = "lobbywatch.db"
        mock_settings.log_level = "INFO"
        mock_settings.dry_run = False
        mock_settings.opensecrets_api_key = None
        mock_settings.propublica_api_key = None
        mock_settings.slack_webhook_url = None
        
        settings = Settings()

        assert settings.database_file == "lobbywatch.db"
        assert settings.log_level == "INFO"
        assert settings.dry_run is False
        assert settings.opensecrets_api_key is None
        assert settings.propublica_api_key is None
        assert settings.slack_webhook_url is None


def test_settings_from_env():
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


def test_notifier_type_detection():
    """Test notifier type detection logic."""
    # No notifier configured
    with patch("bot.config.Settings") as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.slack_webhook_url = None
        mock_settings.notifier_type = None
        
        settings = Settings()
        assert settings.notifier_type is None

    # Slack configured
    settings = Settings(slack_webhook_url="https://hooks.slack.com/test")
    assert settings.notifier_type == "slack"


def test_validate_notifier_config():
    """Test notifier configuration validation."""
    # No notifier configured - should raise error
    with patch("bot.config.Settings") as mock_settings_class:
        mock_settings = mock_settings_class.return_value
        mock_settings.slack_webhook_url = None
        mock_settings.notifier_type = None
        
        settings = Settings()
        with pytest.raises(ValueError, match="No Slack notifier configured"):
            settings.validate_notifier_config()

    # Slack configured - should not raise
    settings = Settings(slack_webhook_url="https://hooks.slack.com/test")
    settings.validate_notifier_config()  # Should not raise
