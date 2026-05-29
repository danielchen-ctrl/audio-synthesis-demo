"""集中配置：所有环境变量在这里读取并校验。"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- 应用 ---
    APP_ENV: Literal["development", "production"] = "development"
    APP_NAME: str = "audio-platform"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # --- 安全 ---
    JWT_SECRET: str = Field(min_length=16)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    # --- Google SSO ---
    GOOGLE_CLIENT_ID: str = ""           # 来自 Google Cloud Console；空则禁用 SSO
    GOOGLE_ALLOWED_DOMAIN: str = "plaud.ai"   # 限制只能这个域的账号登录

    # --- MySQL ---
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_DB: str = "audio_platform"
    MYSQL_USER: str = "app"
    MYSQL_PASSWORD: str

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- MinIO ---
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str = "audio-platform"
    MINIO_USE_SSL: bool = False
    MINIO_PUBLIC_ENDPOINT: str = "http://localhost:9000"

    # --- LLM ---
    LLM_PROVIDER: Literal["deepseek", "openai", "anthropic"] = "deepseek"
    LLM_API_KEY: str
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"
    LLM_TIMEOUT_SEC: int = 60
    LLM_MAX_TOKENS: int = 4096

    # --- CosyVoice ---
    COSYVOICE_BASE_URL: str
    COSYVOICE_MODEL: str = "cosyvoice-v3"
    COSYVOICE_TIMEOUT_SEC: int = 120
    COSYVOICE_MAX_RETRIES: int = 2
    COSYVOICE_MAX_CONCURRENCY: int = 1

    # --- 业务限制 ---
    MAX_UPLOAD_SIZE_MB: int = 500
    MAX_CONCURRENT_TASKS_PER_USER: int = 3
    MAX_PLATFORM_CONCURRENT_TASKS: int = 50

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def database_url(self) -> URL:
        # 用 URL.create 而非字符串拼接：密码含 + / @ / : 等特殊字符时会自动转义
        return URL.create(
            drivername="mysql+pymysql",
            username=self.MYSQL_USER,
            password=self.MYSQL_PASSWORD,
            host=self.MYSQL_HOST,
            port=self.MYSQL_PORT,
            database=self.MYSQL_DB,
            query={"charset": "utf8mb4"},
        )

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """通过 lru_cache 保证全局单例。"""
    return Settings()  # type: ignore[call-arg]
