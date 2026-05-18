from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Database
    database_url: str = Field(..., env="DATABASE_URL")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # API keys
    newsapi_key: str = Field(default="", env="NEWSAPI_KEY")
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", env="ANTHROPIC_API_KEY")
    alpha_vantage_key: str = Field(default="", env="ALPHA_VANTAGE_KEY")

    # External base URLs
    fx_api_base_url: str = Field(default="https://api.frankfurter.app", env="FX_API_BASE_URL")
    binance_base_url: str = Field(default="https://api.binance.com", env="BINANCE_BASE_URL")

    # Polling intervals (seconds)
    market_data_poll_interval: int = Field(default=120, env="MARKET_DATA_POLL_INTERVAL")
    news_poll_interval: int = Field(default=300, env="NEWS_POLL_INTERVAL")
    pipeline_run_interval: int = Field(default=300, env="PIPELINE_RUN_INTERVAL")

    # App
    app_env: str = Field(default="development", env="APP_ENV")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # LLM provider selection: "anthropic" | "openai" | "auto"
    # "auto" tries Anthropic first, then OpenAI, then template fallback.
    llm_provider: str = Field(default="auto", env="LLM_PROVIDER")

    # Auth
    secret_key: str = Field(default="change-me-in-production-32-chars-min", env="SECRET_KEY")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def copilot_enabled(self) -> bool:
        return bool(self.anthropic_api_key or self.openai_api_key)

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
