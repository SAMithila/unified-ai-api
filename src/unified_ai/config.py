"""
Configuration management using Pydantic Settings.

This module provides type-safe configuration loaded from environment variables.
All settings have sensible defaults for development.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================================================
    # API Settings
    # =========================================================================
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, description="API port")
    api_debug: bool = Field(default=False, description="Enable debug mode")
    api_title: str = Field(default="Unified AI API", description="API title")
    api_version: str = Field(default="0.1.0", description="API version")

    # API authentication
    api_key: str = Field(
        default="dev-api-key-change-in-production",
        description="API key for authentication",
    )

    # =========================================================================
    # LLM Provider API Keys
    # =========================================================================
    groq_api_key: str | None = Field(default=None, description="Groq API key")
    google_api_key: str | None = Field(
        default=None, description="Google Gemini API key"
    )
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")

    # =========================================================================
    # Provider Configuration
    # =========================================================================
    llm_provider_order: str = Field(
        default="groq,gemini,openai,anthropic",
        description="Comma-separated list of providers in fallback order",
    )

    # Default models
    groq_model: str = Field(default="llama-3.3-70b-versatile")
    gemini_model: str = Field(default="gemini-1.5-flash")
    openai_model: str = Field(default="gpt-4o-mini")
    anthropic_model: str = Field(default="claude-3-5-sonnet-20241022")

    # =========================================================================
    # Rate Limiting
    # =========================================================================
    rate_limit_requests_per_minute: int = Field(default=60)
    rate_limit_tokens_per_minute: int = Field(default=100000)

    # =========================================================================
    # Storage
    # =========================================================================
    redis_url: str | None = Field(default=None, description="Redis URL for sessions")
    database_url: str | None = Field(default=None, description="PostgreSQL URL")

    # =========================================================================
    # Observability
    # =========================================================================
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_format: Literal["json", "console"] = Field(default="console")
    enable_cost_tracking: bool = Field(default=True)

    # =========================================================================
    # Computed Properties
    # =========================================================================
    @property
    def provider_order(self) -> list[str]:
        """Get provider order as a list."""
        return [p.strip().lower() for p in self.llm_provider_order.split(",")]

    @property
    def available_providers(self) -> list[str]:
        """Get list of providers that have API keys configured."""
        providers = []
        if self.groq_api_key:
            providers.append("groq")
        if self.google_api_key:
            providers.append("gemini")
        if self.openai_api_key:
            providers.append("openai")
        if self.anthropic_api_key:
            providers.append("anthropic")
        return providers

    @field_validator("log_level", mode="before")
    @classmethod
    def uppercase_log_level(cls, v: str) -> str:
        """Ensure log level is uppercase."""
        return v.upper() if isinstance(v, str) else v


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are only loaded once.
    """
    return Settings()


# Convenience function for dependency injection
def get_config() -> Settings:
    """Get settings (alias for get_settings for clarity in FastAPI depends)."""
    return get_settings()
