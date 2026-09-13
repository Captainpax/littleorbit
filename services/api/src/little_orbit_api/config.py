"""Typed runtime configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration shared by the HTTP server and background worker."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    little_orbit_env: str = "development"
    public_base_url: str = "http://localhost:8180"
    release_storage_dir: Path = Path("data/releases")
    attachment_storage_dir: Path = Path("data/attachments")
    clamav_host: str = "clamav"
    clamav_port: int = Field(default=3310, ge=1, le=65_535)
    database_url: str = "postgresql+asyncpg://little_orbit:change-me@localhost/little_orbit"
    session_secret: SecretStr = Field(default=SecretStr("development-only-change-this-secret"))
    token_pepper: SecretStr = Field(default=SecretStr("development-only-token-pepper"))
    totp_encryption_key: SecretStr | None = None
    outbox_encryption_key: SecretStr | None = None
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "hello@lil-orb.pax-kun.com"
    smtp_starttls: bool = False
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    trusted_proxy_ip: str = "192.168.50.6"
    registration_open: bool = True
    registration_ip_per_hour: int = 8
    registration_email_per_hour: int = 4
    session_minutes: int = Field(default=43_200, ge=30, le=525_600)
    admin_session_minutes: int = Field(default=30, ge=5, le=1_440)


@lru_cache
def get_settings() -> Settings:
    """Return one immutable settings instance for this process."""

    return Settings()
