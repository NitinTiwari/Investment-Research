"""Streamlit UI components for rendering LLM Gateway Telemetry."""

from typing import Any
import streamlit as st

from investment_research.research_service import ResearchResult
from investment_research.settings import Settings, settings


def render_telemetry_panel(container: Any, res: ResearchResult | None, app_settings: Settings = settings) -> None:
    """Render LLM Telemetry (Cache details, Token usage, Called tools, Data flow steps)."""
    with container:
        st.divider()
        st.subheader("⚡ LLM Telemetry")
        if res is None:
            st.caption("Live Gateway & execution trace")
            st.info("Run a query to inspect tool calls, token usage, data flow steps, and cache status.", icon=":material/info:")
            return

        st.caption(f"Trace for `{res.ticker}` ({res.mode})")

        telemetry = getattr(res, "telemetry", None) or {}

        # 1. Cache Details
        cache_info = telemetry.get("cache", {})
        cache_status = cache_info.get("status", "HIT" if res.cache_hit else "MISS")
        cache_tier = cache_info.get("tier", "Tier-2 Atomic Disk Cache" if res.cache_hit else "Bypassed")
        cache_key = cache_info.get("key", "")
        latency_ms = cache_info.get("latency_ms", res.duration_ms)

        with st.expander("💾 Cache Details", expanded=True):
            if cache_status == "HIT":
                st.success("**Status:** `HIT` (Instant Response)", icon=":material/check_circle:")
                st.markdown(f"- **Tier:** {cache_tier}")
                st.markdown(f"- **Lookup Latency:** `{latency_ms:.1f} ms`")
                if cache_key:
                    st.markdown(f"- **Key:** `{cache_key[:16]}...`")
                st.markdown("- **Storage:** `data/cache/responses.json`")
                st.caption(f"⚡ Saved ~{res.duration_ms / 1000:.1f}s of LLM inference & external API queries.")
            else:
                st.warning("**Status:** `MISS` (Fresh LLM Run)", icon=":material/sync:")
                st.markdown(f"- **Tier:** {cache_tier}")
                st.markdown(f"- **Lookup Latency:** `{latency_ms:.1f} ms`")
                if cache_key:
                    st.markdown(f"- **Key:** `{cache_key[:16]}...`")
                st.markdown(f"- **Cached:** Atomically saved (`TTL: {app_settings.cache_ttl_seconds}s`)")

        # 2. Used Tokens
        tokens_info = telemetry.get("tokens", {})
        metrics = getattr(res, "metrics", {}) or {}
        prompt_tokens = tokens_info.get("prompt_tokens") or metrics.get("input_tokens") or 0
        completion_tokens = tokens_info.get("completion_tokens") or metrics.get("output_tokens") or 0
        total_tokens = tokens_info.get("total_tokens") or metrics.get("total_tokens") or (prompt_tokens + completion_tokens)
        cost = tokens_info.get("cost", 0.0)

        with st.expander("🪙 Token Usage", expanded=True):
            col_tok1, col_tok2, col_tok3 = st.columns(3)
            col_tok1.metric("Prompt", f"{prompt_tokens:,}")
            col_tok2.metric("Output", f"{completion_tokens:,}")
            col_tok3.metric("Total", f"{total_tokens:,}")
            if cache_status == "HIT":
                st.caption("🟢 **0 API tokens consumed** (Served 100% from cache).")
            else:
                cost_str = f"${cost:.5f}" if cost > 0 else "Free tier / Local rate"
                st.caption(f"Estimated Cost: `{cost_str}` | Gateway: `LiteLLM`")

        # 3. Called Tools (with used time)
        tools = telemetry.get("tools", [])
        with st.expander(f"🔧 Called Tools ({len(tools)})", expanded=True):
            if tools:
                for t in tools:
                    name = t.get("name", "tool")
                    dur_ms = t.get("duration_ms")
                    dur_s = t.get("duration_s")
                    if dur_ms is not None:
                        dur_display = f"{dur_ms:.1f} ms"
                    elif dur_s is not None:
                        dur_display = f"{dur_s:.3f} s"
                    else:
                        dur_display = "<10 ms"

                    args = t.get("args") or {}
                    args_summary = ", ".join(f"{k}='{v}'" for k, v in args.items()) if isinstance(args, dict) and args else ""
                    error = t.get("error", False)
                    status_icon = "❌" if error else "✅"

                    st.markdown(f"- **`{name}`** {status_icon} (`{dur_display}`)")
                    if args_summary:
                        st.caption(f"  └ args: `{args_summary[:60]}`")
            elif cache_status == "HIT":
                st.caption("⚡ **No tools called**: Payload served directly from local cache.")
            else:
                st.caption("0 external tools invoked during response synthesis.")

        # 4. Data Flow Steps
        steps = telemetry.get("steps", [])
        with st.expander(f"🔄 Data Flow Steps ({len(steps)})", expanded=False):
            if steps:
                for s in steps:
                    step_num = s.get("step", 1)
                    name = s.get("name", "Step")
                    status = s.get("status", "completed")
                    dur_ms = s.get("duration_ms", 0.0)
                    detail = s.get("detail", "")
                    icon = "🟢" if status == "completed" else "⚡" if status == "hit" else "🟡" if status == "miss" else "⚪"
                    st.markdown(f"**{icon} {step_num}. {name}** (`{dur_ms:.1f} ms`)")
                    if detail:
                        st.caption(f"   {detail}")
            else:
                st.markdown("1. 🟢 Input Ticker Normalization")
                st.markdown(f"2. {'⚡' if res.cache_hit else '🟡'} Gateway Cache Lookup")
                st.markdown(f"3. {'⚡ Skipped' if res.cache_hit else '🟢 Agentic Execution & Tools'}")
                st.markdown(f"4. 🟢 Report Delivery (`{res.duration_ms:.1f} ms`)")
