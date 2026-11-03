from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    session_ttl_minutes: int = 60 * 24 * 7

    cookie_name: str = "chirp_session"
    # Set to true when the site is served over HTTPS.
    cookie_secure: bool = False

    media_dir: str = "/data/media"
    max_upload_mb: int = 5

    rate_limit_enabled: bool = True

    @field_validator("jwt_secret")
    @classmethod
    def secret_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
