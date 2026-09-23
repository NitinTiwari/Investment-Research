import os
import streamlit as st

# Sync Streamlit Cloud secrets to os.environ so Groq and tools can access them
try:
    for _key, _value in st.secrets.items():
        if isinstance(_value, str) and _key not in os.environ:
            os.environ[_key] = _value
except Exception:
    pass

from investment_research.research_service import ResearchResult, ResearchService
from investment_research.settings import settings

st.set_page_config(
    page_title=settings.app_name,
    page_icon=":material/monitoring:",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_resource
def get_research_service() -> ResearchService:
    return ResearchService()

if "research_result" not in st.session_state:
    st.session_state.research_result = None

if "translated_results" not in st.session_state:
    st.session_state.translated_results = {}

st.title("Market research assistant")
st.caption("Run a focused price check or generate a source-backed equity research report.")

with st.sidebar:
    st.header("Research setup")
    st.caption(f"Model: `{settings.model_name}`")
    st.caption(f"Cache: {'enabled' if settings.cache_enabled else 'disabled'}")
    st.divider()
    st.markdown("**Workflow**")
    st.markdown("1. Enter a ticker\n2. Choose a research action\n3. Review the result and sources\n4. Switch language (English/Hindi) without extra LLM calls")

with st.form("research_form", border=True):
    ticker = st.text_input(
        "Ticker symbol",
        value=settings.default_ticker,
        placeholder="BHEL",
        max_chars=12,
    )
    st.caption("Examples: BHEL, HMA, RPOWER, JKTYRE")
    price_button, details_button = st.columns(2)
    with price_button:
        get_price = st.form_submit_button(
            "Get stock price",
            icon=":material/attach_money:",
            type="secondary",
            width="stretch",
        )
    with details_button:
        get_details = st.form_submit_button(
            "Generate detailed research",
            icon=":material/description:",
            type="primary",
            width="stretch",
        )

selected_mode = "stock_price" if get_price else "detailed_research" if get_details else None
if selected_mode:
    try:
        service = get_research_service()
        with st.status(
            "Running stock-price lookup..." if selected_mode == "stock_price" else "Building detailed research report...",
            expanded=False,
        ) as status:
            result = service.run(ticker, selected_mode)
            st.session_state.research_result = result
            status.update(label="Research complete", state="complete")
    except ValueError as error:
        st.error(f"Invalid ticker: {error}")
    except RuntimeError as error:
        st.error(str(error))
    except Exception:
        st.error("The research service is temporarily unavailable. Check your API key and try again.")

# Language selection dropdown (English / Hindi)
col_spacer, col_lang = st.columns([3, 1])
with col_lang:
    selected_language = st.selectbox(
        "Language / भाषा",
        options=["English", "Hindi"],
        index=0,
        help="Select language. Hindi translation is performed via GoogleTranslator without making an extra LLM call.",
        key="selected_language",
    )

result: ResearchResult | None = st.session_state.research_result
if result is None:
    with st.container(border=True):
        st.subheader("Ready when you are")
        st.write("Choose a research action above to analyze a company.")
else:
    label = "Stock price result" if result.mode == "stock_price" else "Detailed research report"
    with st.container(border=True):
        st.subheader(f"{label}: {result.ticker}")
        if result.cache_hit:
            st.caption("Served from local cache")
        else:
            st.caption(f"Completed in {result.duration_ms / 1000:.1f} seconds")

        display_text = result.text
        if selected_language == "Hindi":
            cache_key = (result.ticker, result.mode, "Hindi")
            if cache_key in st.session_state.translated_results:
                display_text = st.session_state.translated_results[cache_key]
            else:
                service = get_research_service()
                with st.spinner("Translating detailed report to Hindi via GoogleTranslator..."):
                    display_text = service.translate_report(result.text, target_lang="hi")
                    st.session_state.translated_results[cache_key] = display_text

        st.markdown(display_text)

        st.download_button(
            "Download result",
            data=display_text,
            file_name=f"{result.ticker.lower()}-{result.mode}-{selected_language.lower()}.md",
            mime="text/markdown",
            icon=":material/download:",
        )


st.divider()
st.caption("AI-generated research is informational only and is not financial advice.")
