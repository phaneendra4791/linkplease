import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/linkplease"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@postgres:5432/linkplease"
    REDIS_URL: str = "redis://redis:6379/0"

    PSEUDOGRAM_BASE_URL: str = "https://pseudogram-api.onrender.com"
    PSEUDOGRAM_API_KEY: str = ""

    DM_RATE_LIMIT_PER_MINUTE: int = 10
    MAX_DM_RETRIES: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
