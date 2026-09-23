from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_renders_research_actions() -> None:
    app_path = Path(__file__).parents[1] / "streamlit_app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=10)

    assert not app.exception
    assert len(app.button) == 2
    assert app.button[0].label == "Get stock price"
    assert app.button[1].label == "Generate detailed research"
    assert len(app.selectbox) == 1
    assert app.selectbox[0].options == ["English", "Hindi"]
    assert app.selectbox[0].value == "English"


def test_dashboard_language_switching_translates_without_llm() -> None:
    from investment_research.research_service import ResearchResult

    app_path = Path(__file__).parents[1] / "streamlit_app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=10)

    # Set mock detailed research result into session state
    app.session_state.research_result = ResearchResult(
        ticker="AAPL",
        mode="detailed_research",
        text="Apple Inc. is a global technology company.",
        cache_hit=False,
        duration_ms=1200.0,
        metrics={},
    )
    # Rerun with the existing result in session state
    app.run(timeout=10)
    assert not app.exception
    assert len(app.markdown) > 0

    # Switch language to Hindi
    app.selectbox[0].select("Hindi").run(timeout=10)
    assert not app.exception
    # Should have cached Hindi translation
    assert ("AAPL", "detailed_research", "Hindi") in app.session_state.translated_results
    hindi_text = app.session_state.translated_results[("AAPL", "detailed_research", "Hindi")]
    assert len(hindi_text) > 0
    assert hindi_text != "Apple Inc. is a global technology company."