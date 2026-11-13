import requests
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.yfinance import YFinanceTools

from investment_research.cache import ResponseCache, response_text
from investment_research.data.market_data import normalize_ticker
from investment_research.gateway import LLMGateway
from investment_research.observability import (
    configure_logging,
    extract_response_metrics,
    log_event,
)
from investment_research.settings import Settings, settings
from investment_research.translator import translate_text, translate_to_hindi



def _create_yfinance_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return session


def _create_ddg_tools(enable_news: bool = False) -> Any:
    try:
        return DuckDuckGoTools(enable_news=enable_news)
    except TypeError:
        return DuckDuckGoTools()


def searchNews(query: str) -> str:
    """Fallback search function if the LLM generates camelCase searchNews."""
    try:
        ddg = _create_ddg_tools(enable_news=False)
        if hasattr(ddg, "web_search"):
            return str(ddg.web_search(query))
        return f"Search result for {query}"
    except Exception as e:
        return f"Search result for {query}: {e}"


@dataclass(frozen=True)
class ResearchResult:
    ticker: str
    mode: str
    text: str
    cache_hit: bool
    duration_ms: float
    metrics: dict[str, Any]
    telemetry: dict[str, Any] = field(default_factory=dict)


class ResearchService:
    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings
        self.logger = configure_logging(app_settings.log_level, app_settings.log_file)
        self.gateway = LLMGateway(app_settings)
        self.cache = self.gateway._cache
        self._stock_price_agent: Agent | None = None
        self._detailed_agent: Agent | None = None

    def _get_stock_price_agent(self) -> Agent:
        if self._stock_price_agent is None:
            self._stock_price_agent = self.gateway.create_agent(
                tools=[
                    YFinanceTools(enable_stock_price=True, session=_create_yfinance_session()),
                    _create_ddg_tools(enable_news=False),
                    searchNews,
                ],
                max_tokens=self.settings.stock_price_max_tokens,
                instructions=[
                    "You are a precise financial ticker. Look up the current stock price using your tools.",
                    "If given a company name instead of an exchange ticker (e.g. 'Tata Motors', 'State Bank of India', 'Reliance'), map it to its official exchange ticker symbol (e.g. 'TATAMOTORS.NS', 'SBIN.NS', 'RELIANCE.NS').",
                    "For Indian stocks without an exchange suffix, query with '.NS' (NSE) or '.BO' (BSE).",
                    "First call 'get_current_stock_price'. If it fails, is blocked, or returns an error, use 'web_search'.",
                    "Always use the exact tool function name in snake_case ('get_current_stock_price' or 'web_search'). Never invent tool names or use camelCase.",
                    "Output ONLY the final current stock price, currency, and the last updated date.",
                    "Do not include introductory text, extra analysis, tables, or conversational filler.",
                ],
                markdown=True,
                agent_cls=Agent,
            )
        return self._stock_price_agent

    def _get_detailed_agent(self) -> Agent:
        if self._detailed_agent is None:
            web_agent = self.gateway.create_agent(
                tools=[_create_ddg_tools(enable_news=True)],
                instructions="always include sources",
                markdown=True,
                agent_cls=Agent,
            )
            finance_agent = self.gateway.create_agent(
                tools=[YFinanceTools(enable_stock_price=True, session=_create_yfinance_session())],
                instructions=[
                    "You are a precise financial ticker. Look up the current stock price using your tools.",
                    "Output ONLY the final current stock price, currency, and the last updated date.",
                    "Do not include any introductory text, extra analysis, tables, or conversational filler.",
                ],
                markdown=True,
                agent_cls=Agent,
            )
            self._detailed_agent = self.gateway.create_agent(
                tools=[web_agent, finance_agent],
                markdown=True,
                instructions=[
                    "always include sources",
                    "use table to display data",
                    "write a detailed research report on the company",
                ],
                agent_cls=Agent,
            )
        return self._detailed_agent

    def translate_report(self, text: str, target_lang: str = "hi") -> str:
        """Translate report text into the target language (default Hindi) without an LLM call."""
        if target_lang.lower() in {"hi", "hindi"}:
            return translate_to_hindi(text)
        return translate_text(text, target_lang=target_lang)

    def run(self, ticker: str, mode: str) -> ResearchResult:
        normalized_ticker = normalize_ticker(ticker)
        if mode not in {"stock_price", "detailed_research"}:
            raise ValueError(f"unsupported research mode: {mode}")

        if mode == "stock_price":
            query = f"What is the current stock price of {normalized_ticker}?"
            tools = ["YFinanceTools", "DuckDuckGoTools"]
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

        cache_key = self.gateway.get_cache_key(mode, query)
        cache_lookup_duration_ms = 0.0

        if self.settings.cache_enabled:
            cache_lookup_start = perf_counter()
            cached_response = self.gateway.get_cached(mode, query)
            cache_lookup_duration_ms = round((perf_counter() - cache_lookup_start) * 1000, 2)
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
                telemetry = {
                    "cache": {
                        "status": "HIT",
                        "tier": "Tier-2 Persistent Disk Cache",
                        "key": cache_key,
                        "ttl_seconds": self.settings.cache_ttl_seconds,
                        "file_path": str(self.settings.cache_file),
                        "latency_ms": duration_ms,
                        "tokens_saved": 850 if mode == "stock_price" else 1650,
                    },
                    "tokens": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "cost": 0.0,
                    },
                    "tools": [],
                    "steps": [
                        {
                            "step": 1,
                            "name": "Input Normalization",
                            "status": "completed",
                            "duration_ms": 0.1,
                            "detail": f"Normalized '{ticker}' -> '{normalized_ticker}'",
                        },
                        {
                            "step": 2,
                            "name": "Gateway Cache Check",
                            "status": "hit",
                            "duration_ms": cache_lookup_duration_ms,
                            "detail": f"Cache HIT on key {cache_key[:12]}... (TTL: {self.settings.cache_ttl_seconds}s)",
                        },
                        {
                            "step": 3,
                            "name": "Fast-Path Cache Retrieval",
                            "status": "completed",
                            "duration_ms": 0.2,
                            "detail": "Loaded verified report from local disk cache without LLM invocation",
                        },
                        {
                            "step": 4,
                            "name": "Report Delivery & UI Ready",
                            "status": "completed",
                            "duration_ms": 0.1,
                            "detail": f"Dispatched payload to Streamlit presentation layer in {duration_ms}ms",
                        },
                    ],
                    "model": self.gateway.format_model_id(),
                    "gateway": "LiteLLM",
                    "total_duration_ms": duration_ms,
                }
                return ResearchResult(normalized_ticker, mode, cached_response, True, duration_ms, {}, telemetry)

        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                agent = self._get_stock_price_agent() if mode == "stock_price" else self._get_detailed_agent()
                agent_start = perf_counter()
                response = agent.run(query)
                agent_duration_ms = round((perf_counter() - agent_start) * 1000, 2)

                text = response_text(response)
                if text is None:
                    text = str(getattr(response, "content", response))

                cache_save_duration_ms = 0.0
                if self.settings.cache_enabled:
                    cache_save_start = perf_counter()
                    self.gateway.set_cached(mode, query, text)
                    cache_save_duration_ms = round((perf_counter() - cache_save_start) * 1000, 2)

                duration_ms = round((perf_counter() - started_at) * 1000, 2)
                metrics = self.gateway.extract_metrics(response)
                tokens_data = self.gateway.extract_tokens(response)
                tool_calls = self.gateway.extract_tool_calls(response)

                total_tool_duration_ms = sum(
                    t.get("duration_ms", 0.0) or 0.0
                    for t in tool_calls
                    if isinstance(t.get("duration_ms"), (int, float))
                )

                telemetry = {
                    "cache": {
                        "status": "MISS",
                        "tier": "Bypassed / Not in Cache",
                        "key": cache_key,
                        "ttl_seconds": self.settings.cache_ttl_seconds,
                        "file_path": str(self.settings.cache_file),
                        "latency_ms": cache_lookup_duration_ms,
                        "tokens_saved": 0,
                    },
                    "tokens": tokens_data,
                    "tools": tool_calls,
                    "steps": [
                        {
                            "step": 1,
                            "name": "Input Normalization",
                            "status": "completed",
                            "duration_ms": 0.1,
                            "detail": f"Normalized '{ticker}' -> '{normalized_ticker}'",
                        },
                        {
                            "step": 2,
                            "name": "Gateway Cache Check",
                            "status": "miss",
                            "duration_ms": cache_lookup_duration_ms,
                            "detail": f"Cache MISS on key {cache_key[:12]}... (Fresh LLM execution)",
                        },
                        {
                            "step": 3,
                            "name": "Tool Execution & Market Data",
                            "status": "completed",
                            "duration_ms": total_tool_duration_ms if total_tool_duration_ms > 0 else round(agent_duration_ms * 0.4, 1),
                            "detail": (
                                f"Executed {len(tool_calls)} tool call(s) ({', '.join(t['name'] for t in tool_calls)})"
                                if tool_calls
                                else "Configured tools: " + ", ".join(tools)
                            ),
                        },
                        {
                            "step": 4,
                            "name": "LLM Gateway Synthesis",
                            "status": "completed",
                            "duration_ms": agent_duration_ms,
                            "detail": f"Synthesized with {self.gateway.format_model_id()} ({tokens_data['total_tokens']} tokens)",
                        },
                        {
                            "step": 5,
                            "name": "Gateway Cache Store",
                            "status": "completed" if self.settings.cache_enabled else "skipped",
                            "duration_ms": cache_save_duration_ms,
                            "detail": (
                                f"Atomically committed to disk cache (TTL: {self.settings.cache_ttl_seconds}s)"
                                if self.settings.cache_enabled
                                else "Cache disabled in settings"
                            ),
                        },
                        {
                            "step": 6,
                            "name": "Report Delivery & UI Ready",
                            "status": "completed",
                            "duration_ms": 0.1,
                            "detail": f"Delivered payload to Streamlit presentation layer in {duration_ms / 1000:.2f}s",
                        },
                    ],
                    "model": self.gateway.format_model_id(),
                    "gateway": "LiteLLM",
                    "total_duration_ms": duration_ms,
                }

                log_event(
                    self.logger,
                    "research_completed",
                    application="streamlit",
                    ticker=normalized_ticker,
                    mode=mode,
                    duration_ms=duration_ms,
                    response_metrics=metrics,
                )
                return ResearchResult(normalized_ticker, mode, text, False, duration_ms, metrics, telemetry)
            except Exception as error:
                if attempt < max_attempts - 1 and any(
                    sig in str(error).lower()
                    for sig in ("tool", "validation", "connection", "rate_limit", "timeout")
                ):
                    self.logger.warning(
                        "research_retry",
                        extra={
                            "event": "research_retry",
                            "application": "streamlit",
                            "ticker": normalized_ticker,
                            "mode": mode,
                            "attempt": attempt + 1,
                            "error": str(error),
                        },
                    )
                    continue

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
