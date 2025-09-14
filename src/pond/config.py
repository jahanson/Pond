"""Configuration management for Pond."""

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql://localhost:5432/pond"
    db_host: str | None = None
    db_port: int | None = None
    db_user: str | None = None
    db_password: str | None = None
    db_name: str | None = None
    db_pool_size: int = 10
    db_pool_min_size: int = 10
    db_pool_max_size: int = 20
    db_pool_timeout: int = 30

    # API
    host: str = "0.0.0.0"
    port: int = Field(
        default=19100,
        validation_alias=AliasChoices("port", "pond_port"),
        description="API port (checks PORT, then POND_PORT, defaults to 19100)",
    )
    debug: bool = False

    # External services
    ollama_url: str = "http://localhost:11434"

    # Embedding configuration
    embedding_provider: str | None = None  # None = unconfigured
    ollama_embedding_model: str | None = None
    ollama_embedding_timeout: int = 60

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Time handling
    pond_timezone: str | None = None
    geoip_url: str | None = "https://ipapi.co/json/"

    @field_validator("embedding_provider")
    @classmethod
    def validate_embedding_provider(cls, v: str | None) -> str | None:
        """Validate embedding provider is one of the supported options."""
        if v is None:
            return None

        valid_providers = {"ollama", "mock"}
        if v.lower() not in valid_providers:
            raise ValueError(
                f"Invalid EMBEDDING_PROVIDER: '{v}'. "
                f"Must be one of: {', '.join(valid_providers)}"
            )
        return v.lower()

    @model_validator(mode="after")
    def validate_provider_config(self) -> "Settings":
        """Validate provider-specific configuration."""
        if self.embedding_provider == "ollama":
            if not self.ollama_embedding_model:
                raise ValueError(
                    "OLLAMA_EMBEDDING_MODEL is required when EMBEDDING_PROVIDER=ollama. "
                    "Example: OLLAMA_EMBEDDING_MODEL=nomic-embed-text"
                )
            # ollama_url has a default, so it's always set
            # ollama_embedding_timeout has a default too
        return self

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Parse database URL if individual components not provided
        if not any(
            [self.db_host, self.db_port, self.db_user, self.db_password, self.db_name]
        ):
            from urllib.parse import urlparse

            parsed = urlparse(self.database_url)
            self.db_host = self.db_host or parsed.hostname
            self.db_port = self.db_port or parsed.port
            self.db_user = self.db_user or parsed.username
            self.db_password = self.db_password or parsed.password
            self.db_name = self.db_name or parsed.path.lstrip("/")


# Lazy settings initialization
_settings = None


def get_settings() -> Settings:
    """Get the settings instance, creating it if needed."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# This will be accessed as a property
class SettingsProxy:
    """Proxy to provide attribute access to settings."""

    def __getattr__(self, name):
        return getattr(get_settings(), name)

    def __setattr__(self, name, value):
        setattr(get_settings(), name, value)


settings = SettingsProxy()
