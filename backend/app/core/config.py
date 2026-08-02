from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "银发独游协同平台"
    app_version: str = "0.1.0"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"

    secret_key: str = Field(
        default="local-development-only-change-me",
        min_length=16,
    )
    access_token_expire_minutes: int = 120
    refresh_token_expire_days: int = 30
    refresh_cookie_name: str = "silver_safe_refresh"
    jwt_issuer: str = "silver-safe-platform"
    jwt_audience: str = "silver-safe-api"
    database_url: str = "sqlite:///./data/silver_safe.db"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    audit_retention_days: int = 180

    @property
    def secure_cookies(self) -> bool:
        return self.app_env.lower() == "production"

    @model_validator(mode="after")
    def reject_default_production_secret(self) -> "Settings":
        if self.app_env.lower() != "production":
            return self
        weak_prefixes = ("local-", "development-", "replace-")
        if self.secret_key.startswith(weak_prefixes):
            raise ValueError("生产环境必须通过 SECRET_KEY 配置独立随机密钥")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
