from functools import lru_cache
from ipaddress import ip_network

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
        min_length=32,
    )
    access_token_expire_minutes: int = 120
    refresh_token_expire_days: int = 30
    refresh_cookie_name: str = "silver_safe_refresh"
    jwt_issuer: str = "silver-safe-platform"
    jwt_audience: str = "silver-safe-api"
    health_info_encryption_key: str = Field(
        default="local-health-info-key-change-me-2026",
        min_length=32,
    )
    database_url: str = "sqlite:///./data/silver_safe.db"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    trusted_proxy_networks: list[str] = Field(default_factory=list)

    login_failure_window_seconds: int = Field(default=300, ge=30, le=3600)
    login_failure_per_username: int = Field(default=5, ge=1, le=100)
    login_failure_per_ip: int = Field(default=20, ge=1, le=1000)
    location_upload_window_seconds: int = Field(default=60, ge=10, le=3600)
    location_upload_per_trip: int = Field(default=120, ge=1, le=10000)
    location_clock_skew_seconds: int = Field(default=300, ge=0, le=3600)
    geofence_trigger_count: int = Field(default=3, ge=2, le=10)
    geofence_max_accuracy_meters: float = Field(default=100, gt=0, le=1000)
    geofence_alert_cooldown_minutes: int = Field(default=10, ge=1, le=1440)
    location_read_audit_window_seconds: int = Field(default=60, ge=10, le=3600)
    sos_duplicate_seconds: int = Field(default=30, ge=5, le=300)
    sos_rate_limit_window_seconds: int = Field(default=60, ge=10, le=3600)
    sos_rate_limit_per_user: int = Field(default=3, ge=1, le=100)
    sos_rate_limit_per_ip: int = Field(default=10, ge=1, le=1000)
    alert_read_audit_window_seconds: int = Field(default=60, ge=10, le=3600)
    audit_retention_days: int = 180

    @property
    def secure_cookies(self) -> bool:
        return self.app_env.lower() == "production"

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        for network in self.trusted_proxy_networks:
            try:
                ip_network(network, strict=False)
            except ValueError as exc:
                raise ValueError(f"无效的可信代理网段：{network}") from exc

        if self.app_env.lower() != "production":
            return self
        if self.debug:
            raise ValueError("生产环境不得启用 DEBUG")
        weak_prefixes = ("local-", "development-", "replace-")
        if self.secret_key.startswith(weak_prefixes):
            raise ValueError("生产环境必须通过 SECRET_KEY 配置独立随机密钥")
        if self.health_info_encryption_key.startswith(weak_prefixes):
            raise ValueError("生产环境必须通过 HEALTH_INFO_ENCRYPTION_KEY 配置独立加密密钥")
        if self.secret_key == self.health_info_encryption_key:
            raise ValueError("JWT 签名密钥与健康信息加密密钥必须相互独立")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
