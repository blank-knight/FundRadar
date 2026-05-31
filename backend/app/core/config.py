from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://fundradar:fundradar123@localhost:5432/fundradar"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM API
    LLM_API_KEY: str
    LLM_BASE_URL: str = "https://aicoding.0011.ai"
    LLM_MODEL: str = "claude-sonnet-4-20250514"
    LLM_API_FORMAT: str = "anthropic"  # anthropic 或 openai

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_CHAT_ID: str = ""

    # JWT Authentication
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 10080  # 7 days

    # Payment (Xunhupay)
    XUNHUPAY_APPID: str = ""
    XUNHUPAY_APPSECRET: str = ""
    XUNHUPAY_NOTIFY_URL: str = ""

    # Application
    DEBUG: bool = False
    API_PREFIX: str = "/api"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
