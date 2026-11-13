import os

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "true"
os.environ["LITELLM_TELEMETRY"] = "false"

from unittest.mock import MagicMock
from investment_research.research_service import ResearchResult
from investment_research.telemetry_ui import render_telemetry_panel


def test_render_telemetry_panel_none() -> None:
    container = MagicMock()
    render_telemetry_panel(container, None)


def test_render_telemetry_panel_cache_hit() -> None:
    container = MagicMock()
    result = ResearchResult(
        ticker="AAPL",
        mode="stock_price",
        text="AAPL is $245.50",
        cache_hit=True,
        duration_ms=1.5,
        metrics={},
        telemetry={
            "cache": {"status": "HIT", "tier": "Tier-2 Atomic Disk Cache", "key": "abc12345", "latency_ms": 1.5},
            "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost": 0.0},
            "tools": [],
            "steps": [{"step": 1, "name": "Input Normalization", "status": "completed", "duration_ms": 0.1, "detail": "Normalized"}],
        },
    )
    render_telemetry_panel(container, result)


def test_render_telemetry_panel_cache_miss_with_tools() -> None:
    container = MagicMock()
    result = ResearchResult(
        ticker="TATAMOTORS.NS",
        mode="stock_price",
        text="TATAMOTORS.NS is ₹780",
        cache_hit=False,
        duration_ms=1420.0,
        metrics={"input_tokens": 300, "output_tokens": 50, "total_tokens": 350},
        telemetry={
            "cache": {"status": "MISS", "tier": "Bypassed", "key": "def67890", "latency_ms": 1.2},
            "tokens": {"prompt_tokens": 300, "completion_tokens": 50, "total_tokens": 350, "cost": 0.00015},
            "tools": [{"name": "get_current_stock_price", "args": {"symbol": "TATAMOTORS.NS"}, "duration_ms": 320.0, "duration_s": 0.32, "error": False}],
            "steps": [
                {"step": 1, "name": "Input Normalization", "status": "completed", "duration_ms": 0.1, "detail": "Normalized"},
                {"step": 2, "name": "Tool Execution", "status": "completed", "duration_ms": 320.0, "detail": "Executed get_current_stock_price"},
            ],
        },
    )
    render_telemetry_panel(container, result)
