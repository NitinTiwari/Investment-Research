from investment_research.reports.report_format import (
    REQUIRED_SECTIONS,
    format_research_report,
)


def test_report_contains_required_sections_and_content() -> None:
    report = format_research_report(
        ticker="AAPL",
        summary="Strong product demand.",
        metrics={"P/E": 28.4},
        risks=["Execution risk"],
        sources=["https://example.com/report"],
    )

    for section in REQUIRED_SECTIONS:
        assert f"## {section}" in report
    assert "Strong product demand." in report
    assert "Execution risk" in report
    assert "https://example.com/report" in report