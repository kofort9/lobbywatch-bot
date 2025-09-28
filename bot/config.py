"""Configuration management for LobbyLens bot."""

import os
from typing import Optional, Literal
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_file: str = Field(default="lobbywatch.db", env="DATABASE_FILE")
    
    # API Keys
    opensecrets_api_key: Optional[str] = Field(default=None, env="OPENSECRETS_API_KEY")
    propublica_api_key: Optional[str] = Field(default=None, env="PROPUBLICA_API_KEY")
    
    # Slack Configuration
    slack_webhook_url: Optional[str] = Field(default=None, env="SLACK_WEBHOOK_URL")  # Legacy webhook support
    slack_bot_token: Optional[str] = Field(default=None, env="SLACK_BOT_TOKEN")     # Enhanced app features
    slack_signing_secret: Optional[str] = Field(default=None, env="SLACK_SIGNING_SECRET")  # Request verification
    
    # Enhanced Features
    lobbylens_channels: Optional[str] = Field(default=None, env="LOBBYLENS_CHANNELS")  # Comma-separated channel IDs
    
    # Bot Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    dry_run: bool = Field(default=False, env="DRY_RUN")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        
    @property
    def notifier_type(self) -> Optional[Literal["slack"]]:
        """Determine which notifier to use based on available configuration."""
        if self.slack_webhook_url:
            return "slack"
        return None
    
    def validate_notifier_config(self) -> None:
        """Validate that Slack notifier is properly configured."""
        if not self.notifier_type and not self.slack_bot_token:
            raise ValueError(
                "No Slack configuration found. Set SLACK_WEBHOOK_URL for basic mode or "
                "SLACK_BOT_TOKEN + SLACK_SIGNING_SECRET for enhanced features"
            )
    
    def has_enhanced_features(self) -> bool:
        """Check if enhanced Slack app features are available."""
        return bool(self.slack_bot_token and self.slack_signing_secret)


# Global settings instance
settings = Settings()
