from time import perf_counter

from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.yfinance import YFinanceTools
from investment_research.cache import response_text
from investment_research.data.market_data import normalize_ticker
from investment_research.gateway import gateway
from investment_research.observability import configure_logging, log_event
from investment_research.settings import settings

logger = configure_logging(settings.log_level, settings.log_file)

# 1. BUILD MULTI-AGENT TEAM THROUGH LITELLM GATEWAY
web_agent = gateway.create_agent(
    tools=[DuckDuckGoTools()],
    instructions="always include sources",
    markdown=True,
)

finance_agent = gateway.create_agent(
    tools=[
        YFinanceTools(
            enable_stock_price=True,
            enable_company_news=True,
            enable_analyst_recommendations=True,
            enable_income_statements=True,
        )
    ],
    instructions="use table to display data",
    markdown=True,
)

agent_team = gateway.create_agent(
    tools=[web_agent, finance_agent],
    markdown=True,
    instructions=["always include sources", "use table to display data", "write a detailed research report on the company"],
)

# 2. INTERACTIVE RESEARCH REPL
while True:
    try:
        input_data = input("Enter ticker symbol: ")
    except (EOFError, KeyboardInterrupt):
        log_event(logger, "session_ended", application="detailed_research", reason="input_closed")
        print("\nGoodbye.")
        break

    if input_data.strip().lower() == "exit":
        log_event(logger, "session_ended", application="detailed_research")
        break

    try:
        input_data = normalize_ticker(input_data)
    except ValueError as error:
        log_event(logger, "invalid_ticker", application="detailed_research", error=str(error))
        print(f"Invalid ticker: {error}")
        continue

    if input_data == "EXIT":
        log_event(logger, "session_ended", application="detailed_research")
        break

    query = f"what is the current stock price of {input_data}"
    started_at = perf_counter()
    log_event(
        logger,
        "research_started",
        application="detailed_research",
        ticker=input_data,
        query=query,
        model=gateway.format_model_id(),
        configured_tools=["DuckDuckGoTools", "YFinanceTools"],
    )

    cached_response = gateway.get_cached("detailed_research", query)
    if cached_response is not None:
        print(cached_response)
        log_event(
            logger,
            "research_cache_hit",
            application="detailed_research",
            ticker=input_data,
            duration_ms=round((perf_counter() - started_at) * 1000, 2),
        )
        continue

    try:
        response = agent_team.print_response(query, stream=True)
        generated_text = response_text(response)
        if generated_text is not None:
            gateway.set_cached("detailed_research", query, generated_text)
        log_event(
            logger,
            "research_completed",
            application="detailed_research",
            ticker=input_data,
            duration_ms=round((perf_counter() - started_at) * 1000, 2),
            response_metrics=gateway.extract_metrics(response),
        )
    except Exception as error:
        logger.exception(
            "research_failed",
            extra={
                "event": "research_failed",
                "application": "detailed_research",
                "ticker": input_data,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                "error_type": type(error).__name__,
            },
        )
        print(f"Research failed for {input_data}: {error}")
