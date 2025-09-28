"""Tests for configuration management."""

import os
import pytest
from unittest.mock import patch

from bot.config import Settings


def test_settings_defaults():
    """Test default settings values."""
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
        "DRY_RUN": "true"
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
    settings = Settings()
    assert settings.notifier_type is None
    
    # Slack configured
    settings = Settings(slack_webhook_url="https://hooks.slack.com/test")
    assert settings.notifier_type == "slack"


def test_validate_notifier_config():
    """Test notifier configuration validation."""
    # No notifier configured - should raise error
    settings = Settings()
    with pytest.raises(ValueError, match="No Slack notifier configured"):
        settings.validate_notifier_config()
    
    # Slack configured - should not raise
    settings = Settings(slack_webhook_url="https://hooks.slack.com/test")
    settings.validate_notifier_config()  # Should not raise
