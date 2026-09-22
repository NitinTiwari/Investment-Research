from dataclasses import dataclass
from time import perf_counter
from typing import Any

from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.yfinance import YFinanceTools

from investment_research.cache import ResponseCache, response_text
from investment_research.data.market_data import normalize_ticker
from investment_research.observability import (
    configure_logging,
    extract_response_metrics,
    log_event,
)
from investment_research.settings import Settings, settings


@dataclass(frozen=True)
class ResearchResult:
    ticker: str
    mode: str
    text: str
    cache_hit: bool
    duration_ms: float
    metrics: dict[str, Any]


class ResearchService:
    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings
        self.logger = configure_logging(app_settings.log_level, app_settings.log_file)
        self.cache = ResponseCache(app_settings.cache_file, app_settings.cache_ttl_seconds)
        self._stock_price_agent: Agent | None = None
        self._detailed_agent: Agent | None = None

    def _get_stock_price_agent(self) -> Agent:
        if self._stock_price_agent is None:
            model = Groq(
                id=self.settings.model_name,
                max_tokens=self.settings.stock_price_max_tokens,
            )
            self._stock_price_agent = Agent(
                model=model,
                tools=[YFinanceTools(enable_stock_price=True)],
                instructions=[
                    "You are a precise financial ticker. Look up the current stock price using your tools.",
                    "Output ONLY the final current stock price, currency, and the last updated date.",
                    "Do not include introductory text, extra analysis, tables, or conversational filler.",
                ],
                markdown=True,
            )
        return self._stock_price_agent

    def _get_detailed_agent(self) -> Agent:
        if self._detailed_agent is None:
            model = Groq(id=self.settings.model_name)
            web_agent = Agent(
                model=model,
                tools=[DuckDuckGoTools()],
                instructions="always include sources",
                markdown=True,
            )
            finance_agent = Agent(
                model=model,
                tools=[YFinanceTools(enable_stock_price=True)],
                instructions=[
                        "You are a precise financial ticker. Look up the current stock price using your tools.",
                        "Output ONLY the final current stock price, currency, and the last updated date.",
                        "Do not include any introductory text, extra analysis, tables, or conversational filler."
                    ],
                markdown=True,
            )
            self._detailed_agent = Agent(
                model=model,
                tools=[web_agent, finance_agent],
                markdown=True,
                instructions=[
                    "always include sources",
                    "use table to display data",
                    "write a detailed research report on the company",
                ],
            )
        return self._detailed_agent

    def run(self, ticker: str, mode: str) -> ResearchResult:
        normalized_ticker = normalize_ticker(ticker)
        if mode not in {"stock_price", "detailed_research"}:
            raise ValueError(f"unsupported research mode: {mode}")

        if mode == "stock_price":
            query = f"What is the current stock price of {normalized_ticker}?"
            tools = ["YFinanceTools"]
        else:
            query = f"Research {normalized_ticker} and provide a detailed equity research report."
            tools = ["DuckDuckGoTools", "YFinanceTools"]

        started_at = perf_counter()
        self.logger.info(
            "research_started",
            extra={
                "event": "research_started",
                "application": "streamlit",
                "ticker": normalized_ticker,
                "query": query,
                "model": self.settings.model_name,
                "configured_tools": tools,
            },
        )

        if self.settings.cache_enabled:
            cached_response = self.cache.get(mode, query, self.settings.model_name)
            if cached_response is not None:
                duration_ms = round((perf_counter() - started_at) * 1000, 2)
                log_event(
                    self.logger,
                    "research_cache_hit",
                    application="streamlit",
                    ticker=normalized_ticker,
                    mode=mode,
                    duration_ms=duration_ms,
                )
                return ResearchResult(normalized_ticker, mode, cached_response, True, duration_ms, {})

        try:
            agent = self._get_stock_price_agent() if mode == "stock_price" else self._get_detailed_agent()
            response = agent.run(query)
            text = response_text(response)
            if text is None:
                text = str(getattr(response, "content", response))
            if self.settings.cache_enabled:
                self.cache.set(mode, query, self.settings.model_name, text)

            duration_ms = round((perf_counter() - started_at) * 1000, 2)
            metrics = extract_response_metrics(response)
            log_event(
                self.logger,
                "research_completed",
                application="streamlit",
                ticker=normalized_ticker,
                mode=mode,
                duration_ms=duration_ms,
                response_metrics=metrics,
            )
            return ResearchResult(normalized_ticker, mode, text, False, duration_ms, metrics)
        except Exception as error:
            self.logger.exception(
                "research_failed",
                extra={
                    "event": "research_failed",
                    "application": "streamlit",
                    "ticker": normalized_ticker,
                    "mode": mode,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    "error_type": type(error).__name__,
                },
            )
            raise RuntimeError(f"Research failed for {normalized_ticker}: {error}") from error
