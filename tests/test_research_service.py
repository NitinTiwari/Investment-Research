import os

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "true"
os.environ["LITELLM_TELEMETRY"] = "false"

from investment_research import research_service
from investment_research.settings import Settings


def test_all_agents_have_a_finite_tool_call_limit(monkeypatch, tmp_path) -> None:
    agent_configs = []

    def fake_agent(**kwargs):
        agent_configs.append(kwargs)
        return object()

    monkeypatch.setattr(research_service, "Agent", fake_agent)
    monkeypatch.setattr(research_service, "Groq", lambda **_: object())
    monkeypatch.setattr(research_service, "DuckDuckGoTools", lambda: object())
    monkeypatch.setattr(research_service, "YFinanceTools", lambda **_: object())

    configured = Settings(
        cache_file=str(tmp_path / "responses.json"),
        log_file=str(tmp_path / "app.log"),
        agent_tool_call_limit=3,
    )
    service = research_service.ResearchService(configured)

    service._get_stock_price_agent()
    service._get_detailed_agent()

    assert len(agent_configs) == 4
    assert all(config["tool_call_limit"] == 3 for config in agent_configs)


def test_research_service_populates_telemetry(monkeypatch, tmp_path) -> None:
    class FakeMetrics:
        duration = 0.42

    class FakeToolExecution:
        tool_name = "get_current_stock_price"
        tool_args = {"symbol": "AAPL"}
        tool_call_error = False
        metrics = FakeMetrics()

    class FakeRunOutput:
        content = "AAPL is $245.50"
        tools = [FakeToolExecution()]
        metrics = {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}

    class FakeAgent:
        def __init__(self, **kwargs):
            pass

        def run(self, query):
            return FakeRunOutput()

    monkeypatch.setattr(research_service, "Agent", FakeAgent)
    monkeypatch.setattr(research_service, "DuckDuckGoTools", lambda **_: object())
    monkeypatch.setattr(research_service, "YFinanceTools", lambda **_: object())

    configured = Settings(
        cache_file=str(tmp_path / "responses.json"),
        log_file=str(tmp_path / "app.log"),
        cache_enabled=True,
        cache_ttl_seconds=60,
    )
    service = research_service.ResearchService(configured)

    # 1. First run: Cache MISS
    result_miss = service.run("AAPL", "stock_price")
    assert not result_miss.cache_hit
    telemetry_miss = result_miss.telemetry
    assert telemetry_miss["cache"]["status"] == "MISS"
    assert telemetry_miss["tokens"]["total_tokens"] == 150
    assert len(telemetry_miss["tools"]) == 1
    assert telemetry_miss["tools"][0]["name"] == "get_current_stock_price"
    assert telemetry_miss["tools"][0]["duration_ms"] == 420.0
    assert len(telemetry_miss["steps"]) >= 4

    # 2. Second run: Cache HIT
    result_hit = service.run("AAPL", "stock_price")
    assert result_hit.cache_hit
    telemetry_hit = result_hit.telemetry
    assert telemetry_hit["cache"]["status"] == "HIT"
    assert telemetry_hit["tokens"]["total_tokens"] == 0
    assert len(telemetry_hit["tools"]) == 0
    assert len(telemetry_hit["steps"]) >= 4
