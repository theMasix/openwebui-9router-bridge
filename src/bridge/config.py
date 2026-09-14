"""Configuration management for OpenWebUI-9Router bridge."""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Bridge runtime settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_prefix="BRIDGE_",
        case_sensitive=False,
        extra="ignore",
    )

    # Server binding
    host: str = Field(
        default="0.0.0.0",
        description="Host interface to bind server to",
        validation_alias=AliasChoices("BRIDGE_HOST", "HOST"),
    )
    port: int = Field(
        default=8000,
        description="Port to listen on",
        validation_alias=AliasChoices("BRIDGE_PORT", "PORT"),
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
        validation_alias=AliasChoices("BRIDGE_LOG_LEVEL", "LOG_LEVEL"),
    )

    # Inbound security (from OpenWebUI)
    inbound_api_key: str | None = Field(
        default=None,
        description="Required Bearer token from OpenWebUI if authentication enabled",
        validation_alias=AliasChoices(
            "BRIDGE_INBOUND_API_KEY", "BRIDGE_API_KEY", "INBOUND_API_KEY"
        ),
    )

    # Upstream 9Router settings
    ninerouter_url: str = Field(
        default="http://localhost:20128",
        description="Base URL for 9Router instance",
        validation_alias=AliasChoices("BRIDGE_NINEROUTER_URL", "NINEROUTER_URL"),
    )
    ninerouter_api_key: str | None = Field(
        default=None,
        description="Bearer token for 9Router instance if auth required",
        validation_alias=AliasChoices(
            "BRIDGE_NINEROUTER_API_KEY", "NINEROUTER_KEY", "NINEROUTER_API_KEY"
        ),
    )
    search_model: str = Field(
        default="tavily",
        description="Search model / provider ID in 9Router (e.g. tavily, brave, searxng, search-combo)",
        validation_alias=AliasChoices(
            "BRIDGE_SEARCH_MODEL", "SEARCH_MODEL", "BRIDGE_NINEROUTER_MODEL"
        ),
    )
    timeout_seconds: float = Field(
        default=15.0,
        description="HTTP request timeout for upstream 9Router calls",
        validation_alias=AliasChoices("BRIDGE_TIMEOUT_SECONDS", "TIMEOUT_SECONDS"),
    )
    max_retries: int = Field(
        default=2,
        description="Maximum retry attempts for transient upstream failures",
        validation_alias=AliasChoices("BRIDGE_MAX_RETRIES", "MAX_RETRIES"),
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
