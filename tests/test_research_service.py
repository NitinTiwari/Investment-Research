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
