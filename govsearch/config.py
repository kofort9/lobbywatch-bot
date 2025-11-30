"""Configuration helpers for GovSearch service."""

from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, BaseModel, Field
from pydantic_settings import BaseSettings


class GovSearchSettings(BaseSettings):
    """Environment-driven configuration."""

    database_url: str = Field(..., alias="DATABASE_URL")
    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8001, alias="API_PORT")
    api_base: Optional[AnyHttpUrl] = Field(None, alias="API_BASE")
    default_sources: List[str] = Field(
        default_factory=lambda: [
            "federal_register",
            "regulations_gov",
            "congress",
            "lda",
        ]
    )

    class Config:
        env_file = ".env"
        env_prefix = "GOVSEARCH_"
        populate_by_name = True
        extra = "ignore"


class UISettings(BaseModel):
    """UI-specific configuration that is safe to share."""

    api_base: AnyHttpUrl
    default_days_filter: int = 30


@lru_cache()
def get_settings() -> GovSearchSettings:
    """Return cached application settings."""

    return GovSearchSettings()
