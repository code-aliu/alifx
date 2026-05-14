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

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
