import os

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "true"
os.environ["LITELLM_TELEMETRY"] = "false"

from unittest.mock import MagicMock

from investment_research.gateway import LLMGateway
from investment_research.settings import Settings


def test_format_model_id_prefixes_groq() -> None:
    gateway = LLMGateway()
    assert gateway.format_model_id("llama-3.3-70b-versatile") == "groq/llama-3.3-70b-versatile"
    assert gateway.format_model_id("groq/llama-3.3-70b-versatile") == "groq/llama-3.3-70b-versatile"
    assert gateway.format_model_id("openai/gpt-4o") == "openai/gpt-4o"
    assert gateway.format_model_id("anthropic/claude-3-5-sonnet") == "anthropic/claude-3-5-sonnet"


def test_gateway_enforces_agent_tool_call_limit(tmp_path) -> None:
    created_configs = []

    def mock_agent_cls(**kwargs):
        created_configs.append(kwargs)
        return MagicMock()

    configured = Settings(
        cache_file=str(tmp_path / "responses.json"),
        log_file=str(tmp_path / "app.log"),
        agent_tool_call_limit=7,
    )
    gateway = LLMGateway(configured)
    gateway.create_agent(agent_cls=mock_agent_cls)

    assert len(created_configs) == 1
    assert created_configs[0]["tool_call_limit"] == 7
    assert created_configs[0]["retries"] == 2


def test_gateway_caching_roundtrip(tmp_path) -> None:
    configured = Settings(
        cache_enabled=True,
        cache_file=str(tmp_path / "gateway_cache.json"),
        cache_ttl_seconds=60,
    )
    gateway = LLMGateway(configured)

    assert gateway.get_cached("stock_price", "AAPL query") is None
    gateway.set_cached("stock_price", "AAPL query", "AAPL is $240")
    assert gateway.get_cached("stock_price", "AAPL query") == "AAPL is $240"


def test_gateway_caching_disabled(tmp_path) -> None:
    configured = Settings(
        cache_enabled=False,
        cache_file=str(tmp_path / "disabled_cache.json"),
        cache_ttl_seconds=60,
    )
    gateway = LLMGateway(configured)

    gateway.set_cached("stock_price", "AAPL query", "AAPL is $240")
    assert gateway.get_cached("stock_price", "AAPL query") is None
    assert not (tmp_path / "disabled_cache.json").exists()


def test_gateway_extract_metrics() -> None:
    gateway = LLMGateway()

    class FakeResponse:
        metrics = {"input_tokens": 100, "output_tokens": 50}

    metrics = gateway.extract_metrics(FakeResponse())
    assert metrics == {"input_tokens": 100, "output_tokens": 50}
