from collections.abc import Mapping, Sequence


REQUIRED_SECTIONS = (
    "Executive Summary",
    "Key Metrics",
    "Risks",
    "Sources",
)


def format_research_report(
    ticker: str,
    summary: str,
    metrics: Mapping[str, object],
    risks: Sequence[str],
    sources: Sequence[str],
) -> str:
    metric_lines = "\n".join(f"- **{name}:** {value}" for name, value in metrics.items())
    risk_lines = "\n".join(f"- {risk}" for risk in risks) or "- No risks provided."
    source_lines = "\n".join(f"- {source}" for source in sources) or "- No sources provided."
    return (
        f"# {ticker} Research Report\n\n"
        f"## Executive Summary\n{summary}\n\n"
        f"## Key Metrics\n{metric_lines}\n\n"
        f"## Risks\n{risk_lines}\n\n"
        f"## Sources\n{source_lines}\n"
    )