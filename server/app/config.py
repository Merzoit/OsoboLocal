from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ososbo"
    app_version: str = "0.1.0"
    debug: bool = False

    database_url: str = "sqlite:///./data/ososbo.db"
    auto_migrate: bool = True

    register_rate_limit: int = 10
    register_rate_window_seconds: int = 60

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
