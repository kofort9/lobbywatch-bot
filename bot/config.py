"""Configuration management for LobbyLens bot."""

# import os  # Unused for now
from typing import List, Literal, Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_file: str = Field(default="lobbywatch.db")
    database_url: Optional[str] = Field(default=None)  # Postgres for production

    # API Keys (Legacy - no longer available)
    opensecrets_api_key: Optional[str] = Field(default=None)
    propublica_api_key: Optional[str] = Field(default=None)

    # Daily Signals API Keys
    congress_api_key: Optional[str] = Field(default=None)
    federal_register_api_key: Optional[str] = Field(default=None)
    regulations_gov_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("REGULATIONS_GOV_API_KEY", "REGS_GOV_API_KEY"),
    )
    regs_max_detail_docs: int = Field(default=300)
    regs_max_surge_dockets: int = Field(default=25)
    regs_surge_abs_min: int = Field(default=50)
    regs_surge_rel_min: float = Field(default=2.0)

    # Slack Configuration
    slack_webhook_url: Optional[str] = Field(default=None)  # Legacy webhook support
    slack_bot_token: Optional[str] = Field(default=None)  # Enhanced app features
    slack_signing_secret: Optional[str] = Field(default=None)  # Request verification
    notifier_preference: Optional[Literal["slack", "email"]] = Field(
        default=None,
        validation_alias=AliasChoices("NOTIFIER_TYPE", "NOTIFICATION_CHANNEL"),
    )

    # Email Configuration (SMTP provider, e.g., SendGrid/SES/Gmail)
    smtp_host: Optional[str] = Field(default=None)
    smtp_port: int = Field(default=587)
    smtp_username: Optional[str] = Field(default=None)
    smtp_password: Optional[str] = Field(default=None)
    smtp_use_tls: bool = Field(default=True)
    email_from_address: Optional[str] = Field(default=None)
    email_to: Optional[str] = Field(
        default=None,
        description="Comma-separated recipient list for email digests",
    )
    email_subject_prefix: str = Field(default="LobbyLens")

    # Signals storage (V2)
    signals_database_url: Optional[str] = Field(
        default=None,
        description="Postgres URL for V2 signals; falls back to SQLite signals.db",
    )

    # HTTP Client Defaults
    http_timeout_seconds: float = Field(default=15.0)
    http_retries: int = Field(default=3)
    http_backoff: float = Field(default=0.5)

    # Enhanced Features
    lobbylens_channels: Optional[str] = Field(
        default=None
    )  # Comma-separated channel IDs

    # Production Settings
    environment: str = Field(default="development")  # development, staging, production
    admin_users: Optional[str] = Field(default=None)  # Comma-separated Slack user IDs

    # Bot Configuration
    log_level: str = Field(default="INFO")
    dry_run: bool = Field(default=False)
    log_json: bool = Field(default=False, description="Emit logs as JSON lines")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def notifier_type(self) -> Optional[Literal["slack", "email"]]:
        """Determine which notifier to use based on available configuration."""
        # Explicit preference wins if its config is available
        if (
            self.notifier_preference == "email"
            and self.email_from_address
            and self.email_to
            and self.smtp_host
        ):
            return "email"

        if self.notifier_preference == "slack" and self.slack_webhook_url:
            return "slack"

        # Fallback ordering: Slack webhook, then email SMTP
        if self.slack_webhook_url:
            return "slack"

        if self.email_from_address and self.email_to and self.smtp_host:
            return "email"

        return None

    def validate_notifier_config(self) -> None:
        """Validate that Slack notifier is properly configured."""
        if not self.notifier_type and not self.slack_bot_token:
            # Preserve legacy wording for existing tests while expanding guidance.
            raise ValueError(
                "No Slack configuration found. Set SLACK_WEBHOOK_URL for Slack "
                "webhook mode or configure SMTP credentials (SMTP_HOST, SMTP_PORT, "
                "SMTP_USERNAME, SMTP_PASSWORD, EMAIL_FROM_ADDRESS, EMAIL_TO) for email "
                "delivery."
            )

        if self.notifier_type == "email":
            missing = [
                key
                for key, value in {
                    "SMTP_HOST": self.smtp_host,
                    "EMAIL_FROM_ADDRESS": self.email_from_address,
                    "EMAIL_TO": self.email_to,
                }.items()
                if not value
            ]
            if missing:
                raise ValueError(
                    "Email notifier misconfigured; missing: " + ", ".join(missing)
                )

    def has_enhanced_features(self) -> bool:
        """Check if enhanced Slack app features are available."""
        return bool(self.slack_bot_token and self.slack_signing_secret)

    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() == "production"

    def get_admin_users(self) -> List[str]:
        """Get list of admin user IDs."""
        if not self.admin_users:
            return []
        return [user.strip() for user in self.admin_users.split(",") if user.strip()]

    def get_email_recipients(self) -> List[str]:
        """Return parsed recipient list for email notifications."""
        if not self.email_to:
            return []
        return [addr.strip() for addr in self.email_to.split(",") if addr.strip()]


# Global settings instance
settings = Settings()
