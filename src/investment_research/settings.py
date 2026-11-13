import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Configure LiteLLM defaults
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")
os.environ.setdefault("LITELLM_TELEMETRY", "false")


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_positive_int(name: str, default: int) -> int:
    value = _get_int(name, default)
    return value if value > 0 else default


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Market Research")
    model_name: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    stock_price_max_tokens: int = _get_int("STOCK_PRICE_MAX_TOKENS", 200)
    agent_tool_call_limit: int = _get_positive_int("AGENT_TOOL_CALL_LIMIT", 5)
    default_ticker: str = os.getenv("DEFAULT_TICKER", "BHEL")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_file: str = os.getenv("LOG_FILE", "logs/app.log")
    cache_enabled: bool = _get_bool("CACHE_ENABLED", True)
    cache_file: str = os.getenv("CACHE_FILE", "cache/responses.json")
    cache_ttl_seconds: int = _get_int("CACHE_TTL_SECONDS", 30)


settings = Settings()