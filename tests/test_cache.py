import json

from investment_research.cache import ResponseCache, response_text


class Response:
    content = "Generated report"


def test_cache_round_trip(tmp_path) -> None:
    cache = ResponseCache(str(tmp_path / "responses.json"), ttl_seconds=60)
    cache.set("stock_price", "What is AAPL worth?", "test-model", "AAPL is $200")

    assert cache.get("stock_price", "What is AAPL worth?", "test-model") == "AAPL is $200"


def test_cache_expires_entries(tmp_path, monkeypatch) -> None:
    current_time = 1000.0
    monkeypatch.setattr("investment_research.cache.time.time", lambda: current_time)
    cache = ResponseCache(str(tmp_path / "responses.json"), ttl_seconds=10)
    cache.set("stock_price", "query", "model", "response")

    monkeypatch.setattr("investment_research.cache.time.time", lambda: current_time + 10)
    assert cache.get("stock_price", "query", "model") is None


def test_cache_recovers_from_malformed_file(tmp_path) -> None:
    cache_path = tmp_path / "responses.json"
    cache_path.write_text("not valid json", encoding="utf-8")
    cache = ResponseCache(str(cache_path), ttl_seconds=60)

    assert cache.get("stock_price", "query", "model") is None
    cache.set("stock_price", "query", "model", "response")
    assert json.loads(cache_path.read_text(encoding="utf-8"))


def test_zero_ttl_disables_cache(tmp_path) -> None:
    cache = ResponseCache(str(tmp_path / "responses.json"), ttl_seconds=0)
    cache.set("stock_price", "query", "model", "response")

    assert cache.get("stock_price", "query", "model") is None
    assert not (tmp_path / "responses.json").exists()


def test_response_text_supports_agno_style_response() -> None:
    assert response_text(Response()) == "Generated report"