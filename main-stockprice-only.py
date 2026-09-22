from agno.agent import Agent
from agno.tools.yfinance import YFinanceTools
from agno.models.groq import Groq 
from investment_research.cache import ResponseCache, response_text
from investment_research.data.market_data import normalize_ticker
from investment_research.observability import (
    configure_logging,
    extract_response_metrics,
    log_event,
)
from investment_research.settings import settings
from time import perf_counter

logger = configure_logging(settings.log_level, settings.log_file)
cache = ResponseCache(settings.cache_file, settings.cache_ttl_seconds)

llm = Groq(id=settings.model_name, max_tokens=settings.stock_price_max_tokens)

# 1. ISOLATE FINANCE AGENT & ADD STRICT INSTRUCTIONS
finance_agent = Agent(
    model=llm,
    tools=[YFinanceTools(enable_stock_price=True)], # Turned off news, analyst recs, and income statements
    instructions=[
        "You are a precise financial ticker. Look up the current stock price using your tools.",
        "Output ONLY the final current stock price, currency, and the last updated date.",
        "Do not include any introductory text, extra analysis, tables, or conversational filler."
    ],
    markdown=True
)

# 2. CAPTURE INPUT AND RUN THE TARGETED AGENT
try:
    input_data = normalize_ticker(input("Enter ticker symbol (e.g., AAPL, TSLA): "))
except (EOFError, KeyboardInterrupt):
    log_event(logger, "session_ended", application="stock_price", reason="input_closed")
    print("\nGoodbye.")
    raise SystemExit(0)
except ValueError as error:
    log_event(logger, "invalid_ticker", application="stock_price", error=str(error))
    print(f"Invalid ticker: {error}")
    raise SystemExit(2)

print(f"\nFetching price for {input_data}...")
query = f"What is the current stock price of {input_data}?"
started_at = perf_counter()
log_event(
    logger,
    "research_started",
    application="stock_price",
    ticker=input_data,
    query=query,
    model=settings.model_name,
    configured_tools=["YFinanceTools"],
)

cached_response = cache.get("stock_price", query, settings.model_name) if settings.cache_enabled else None
if cached_response is not None:
    print(cached_response)
    log_event(
        logger,
        "research_cache_hit",
        application="stock_price",
        ticker=input_data,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
    )
    raise SystemExit(0)

try:
    response = finance_agent.print_response(query, stream=True)
    generated_text = response_text(response)
    if generated_text is not None and settings.cache_enabled:
        cache.set("stock_price", query, settings.model_name, generated_text)
    log_event(
        logger,
        "research_completed",
        application="stock_price",
        ticker=input_data,
        duration_ms=round((perf_counter() - started_at) * 1000, 2),
        response_metrics=extract_response_metrics(response),
    )

except Exception as error:
    logger.exception(
        "research_failed",
        extra={
            "event": "research_failed",
            "application": "stock_price",
            "ticker": input_data,
            "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            "error_type": type(error).__name__,
        },
    )
    print(f"Research failed for {input_data}: {error}")
