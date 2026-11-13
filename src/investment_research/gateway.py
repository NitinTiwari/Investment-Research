"""LLM Gateway powered by LiteLLM for routing, caching, and tool call policies."""

import os
from typing import Any

import litellm
from agno.agent import Agent
from agno.models.litellm import LiteLLM

from investment_research.cache import ResponseCache, response_text
from investment_research.observability import extract_response_metrics
from investment_research.settings import Settings, settings

# Ensure LiteLLM runs with local cost map and without telemetry calls
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "true")
os.environ.setdefault("LITELLM_TELEMETRY", "false")


class LLMGateway:
    """Centralized LLM Gateway managing model routing, caching, and tool policies."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings
        self._cache = ResponseCache(
            path=app_settings.cache_file,
            ttl_seconds=app_settings.cache_ttl_seconds,
        )
        self._configure_litellm()

    def _configure_litellm(self) -> None:
        """Configure LiteLLM runtime settings and native caching."""
        litellm.drop_params = True
        litellm.num_retries = 2

        # Ensure API key is set in environment for LiteLLM if available
        api_key = os.getenv("GROQ_API_KEY") or os.getenv("LITELLM_API_KEY")
        if api_key and not os.getenv("GROQ_API_KEY"):
            os.environ["GROQ_API_KEY"] = api_key

        # Configure LiteLLM in-memory cache if caching is enabled
        if self.settings.cache_enabled and self.settings.cache_ttl_seconds > 0:
            try:
                from litellm.caching.caching import Cache

                litellm.cache = Cache(type="local", ttl=self.settings.cache_ttl_seconds)
            except Exception:
                pass

    def format_model_id(self, model_id: str | None = None) -> str:
        """Ensure model ID contains provider prefix required by LiteLLM."""
        raw_id = (model_id or self.settings.model_name).strip()
        known_prefixes = ("groq/", "openai/", "anthropic/", "ollama/", "bedrock/", "gemini/")
        if any(raw_id.lower().startswith(p) for p in known_prefixes):
            return raw_id
        return f"groq/{raw_id}"

    def get_model(
        self,
        max_tokens: int | None = None,
        model_id: str | None = None,
    ) -> LiteLLM:
        """Create and return an Agno LiteLLM model adapter."""
        formatted_id = self.format_model_id(model_id)
        api_key = os.getenv("GROQ_API_KEY") or os.getenv("LITELLM_API_KEY")
        return LiteLLM(
            id=formatted_id,
            max_tokens=max_tokens,
            api_key=api_key,
        )

    def create_agent(
        self,
        tools: list[Any] | None = None,
        instructions: list[str] | str | None = None,
        max_tokens: int | None = None,
        model_id: str | None = None,
        agent_cls: type = Agent,
        **kwargs: Any,
    ) -> Any:
        """Factory method creating an Agent governed by gateway tool limits and retries."""
        model = self.get_model(max_tokens=max_tokens, model_id=model_id)
        agent_kwargs = {
            "model": model,
            "tool_call_limit": self.settings.agent_tool_call_limit,
            "retries": 2,
            "delay_between_retries": 1,
            "tools": tools or [],
            "instructions": instructions,
            **kwargs,
        }
        return agent_cls(**agent_kwargs)

    def get_cached(self, namespace: str, query: str, model_id: str | None = None) -> str | None:
        """Retrieve a cached response if caching is enabled."""
        if not self.settings.cache_enabled:
            return None
        model_name = self.format_model_id(model_id)
        return self._cache.get(namespace, query, model_name)

    def set_cached(
        self,
        namespace: str,
        query: str,
        response: str,
        model_id: str | None = None,
    ) -> None:
        """Store a response in the cache if caching is enabled."""
        if not self.settings.cache_enabled:
            return
        model_name = self.format_model_id(model_id)
        self._cache.set(namespace, query, model_name, response)

    def extract_metrics(self, response: Any) -> dict[str, Any]:
        """Extract usage and performance metrics from agent or LLM response."""
        return extract_response_metrics(response)


gateway = LLMGateway()

