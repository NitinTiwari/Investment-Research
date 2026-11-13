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

    def get_cache_key(self, namespace: str, query: str, model_id: str | None = None) -> str:
        """Compute the unique cache key for a namespace, query, and model."""
        model_name = self.format_model_id(model_id)
        return self._cache._key(namespace, query, model_name)

    def extract_tool_calls(self, response: Any) -> list[dict[str, Any]]:
        """Extract tool names, arguments, execution duration, and status from a response."""
        extracted: list[dict[str, Any]] = []

        # 1. Primary check: response.tools
        tools = getattr(response, "tools", None) or []
        for t in tools:
            name = (
                getattr(t, "tool_name", None)
                or (t.get("tool_name") if isinstance(t, dict) else None)
                or getattr(t, "name", None)
                or (t.get("name") if isinstance(t, dict) else None)
                or "tool"
            )
            args = (
                getattr(t, "tool_args", None)
                or (t.get("tool_args") if isinstance(t, dict) else None)
                or getattr(t, "args", None)
                or {}
            )
            metrics = getattr(t, "metrics", None) or (t.get("metrics") if isinstance(t, dict) else None)
            duration: float | None = None
            if metrics is not None:
                duration = getattr(metrics, "duration", None) or (
                    metrics.get("duration") if isinstance(metrics, dict) else None
                )

            error = getattr(t, "tool_call_error", False) or (
                t.get("tool_call_error") if isinstance(t, dict) else False
            )

            extracted.append({
                "name": str(name),
                "args": args if isinstance(args, dict) else {},
                "duration_s": round(float(duration), 3) if isinstance(duration, (int, float)) else None,
                "duration_ms": round(float(duration) * 1000, 1) if isinstance(duration, (int, float)) else None,
                "error": bool(error),
            })

        # 2. Secondary check: response.events for ToolCallCompletedEvent
        if not extracted and hasattr(response, "events") and response.events:
            for event in response.events:
                tool_obj = getattr(event, "tool", None)
                if tool_obj is not None:
                    name = getattr(tool_obj, "tool_name", "tool")
                    args = getattr(tool_obj, "tool_args", {})
                    metrics = getattr(tool_obj, "metrics", None)
                    duration = getattr(metrics, "duration", None) if metrics else None
                    extracted.append({
                        "name": str(name),
                        "args": args if isinstance(args, dict) else {},
                        "duration_s": round(float(duration), 3) if isinstance(duration, (int, float)) else None,
                        "duration_ms": round(float(duration) * 1000, 1) if isinstance(duration, (int, float)) else None,
                        "error": bool(getattr(tool_obj, "tool_call_error", False)),
                    })

        # 3. Tertiary check: response.messages for function/tool calls
        if not extracted and hasattr(response, "messages") and response.messages:
            for msg in response.messages:
                msg_tool_calls = getattr(msg, "tool_calls", None) or []
                for tc in msg_tool_calls:
                    func = tc.get("function", {}) if isinstance(tc, dict) else getattr(tc, "function", None)
                    fn_name = func.get("name") if isinstance(func, dict) else getattr(func, "name", "tool")
                    extracted.append({
                        "name": str(fn_name),
                        "args": {},
                        "duration_s": None,
                        "duration_ms": None,
                        "error": False,
                    })

        return extracted

    def extract_tokens(self, response: Any) -> dict[str, Any]:
        """Extract prompt, completion, total token counts, and cost estimates."""
        metrics = self.extract_metrics(response)
        prompt_tokens = (
            metrics.get("prompt_tokens")
            or metrics.get("input_tokens")
            or 0
        )
        completion_tokens = (
            metrics.get("completion_tokens")
            or metrics.get("output_tokens")
            or 0
        )
        total_tokens = (
            metrics.get("total_tokens")
            or (prompt_tokens + completion_tokens)
        )
        cost = metrics.get("cost", 0.0) or 0.0
        return {
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "total_tokens": int(total_tokens),
            "cost": float(cost),
        }


gateway = LLMGateway()

