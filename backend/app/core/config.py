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
    admin_session_hours: int = Field(default=8, ge=1)

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
