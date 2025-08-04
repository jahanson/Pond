"""Configuration management for Pond."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
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
    port: int = 8000
    api_key: str | None = None

    # External services
    ollama_url: str = "http://localhost:11434"
    embedding_timeout: int = 60

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Time handling
    pond_timezone: str | None = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Parse database URL if individual components not provided
        if not any([self.db_host, self.db_port, self.db_user, self.db_password, self.db_name]):
            from urllib.parse import urlparse
            parsed = urlparse(self.database_url)
            self.db_host = self.db_host or parsed.hostname
            self.db_port = self.db_port or parsed.port
            self.db_user = self.db_user or parsed.username
            self.db_password = self.db_password or parsed.password
            self.db_name = self.db_name or parsed.path.lstrip('/')


settings = Settings()
