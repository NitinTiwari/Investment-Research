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


def test_gateway_extract_tool_calls() -> None:
    gateway = LLMGateway()

    class FakeMetrics:
        duration = 0.234

    class FakeToolExecution:
        tool_name = "get_current_stock_price"
        tool_args = {"symbol": "TATAMOTORS.NS"}
        tool_call_error = False
        metrics = FakeMetrics()

    class FakeResponse:
        tools = [FakeToolExecution()]

    tools = gateway.extract_tool_calls(FakeResponse())
    assert len(tools) == 1
    assert tools[0]["name"] == "get_current_stock_price"
    assert tools[0]["args"] == {"symbol": "TATAMOTORS.NS"}
    assert tools[0]["duration_s"] == 0.234
    assert tools[0]["duration_ms"] == 234.0
    assert not tools[0]["error"]


def test_gateway_extract_tokens() -> None:
    gateway = LLMGateway()

    class FakeResponse:
        metrics = {"input_tokens": 120, "output_tokens": 45, "total_tokens": 165, "cost": 0.00012}

    tokens = gateway.extract_tokens(FakeResponse())
    assert tokens["prompt_tokens"] == 120
    assert tokens["completion_tokens"] == 45
    assert tokens["total_tokens"] == 165
    assert tokens["cost"] == 0.00012


def test_gateway_get_cache_key() -> None:
    gateway = LLMGateway()
    key = gateway.get_cache_key("stock_price", "What is AAPL price?")
    assert isinstance(key, str)
    assert len(key) == 64
