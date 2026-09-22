import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Investment Research")
    model_name: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
    stock_price_max_tokens: int = _get_int("STOCK_PRICE_MAX_TOKENS", 200)
    default_ticker: str = os.getenv("DEFAULT_TICKER", "AAPL")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "logs/app.log")
    cache_enabled: bool = _get_bool("CACHE_ENABLED", True)
    cache_file: str = os.getenv("CACHE_FILE", "cache/responses.json")
    cache_ttl_seconds: int = _get_int("CACHE_TTL_SECONDS", 900)


settings = Settings()