"""Application settings, loaded from environment variables (and backend/.env in dev).

Secrets are SecretStr so they never show up in repr(), logs or tracebacks.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["dev", "test", "prod"] = "dev"

    database_url: str
    # Only read by the test suite; never used by the running app.
    test_database_url: str | None = None

    internal_token: SecretStr = Field(min_length=32)
    ip_hash_secret: SecretStr = Field(min_length=32)

    rate_limit_ip_per_hour: int = Field(default=5, ge=1)
    rate_limit_email_per_hour: int = Field(default=3, ge=1)
    # More links than this in one message -> 422 too_many_links.
    max_links_per_message: int = Field(default=3, ge=0)
    duplicate_window_hours: int = Field(default=24, ge=1)
    admin_session_hours: int = Field(default=8, ge=1)
    # Per account: this many consecutive failures -> locked for login_lockout_minutes.
    login_max_failures: int = Field(default=5, ge=1)
    login_lockout_minutes: int = Field(default=15, ge=1)
    # Per IP: at most this many login attempts (any outcome) per login_ip_window_minutes.
    login_ip_max_attempts: int = Field(default=10, ge=1)
    login_ip_window_minutes: int = Field(default=15, ge=1)

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
