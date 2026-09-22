import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
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


settings = Settings()