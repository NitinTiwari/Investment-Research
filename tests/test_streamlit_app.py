from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_dashboard_renders_research_actions() -> None:
    app_path = Path(__file__).parents[1] / "streamlit_app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=10)

    assert not app.exception
    assert len(app.button) == 2
    assert app.button[0].label == "Get stock price"
    assert app.button[1].label == "Generate detailed research"