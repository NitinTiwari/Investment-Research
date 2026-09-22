 # Investment Research

Two small command-line tools for researching companies with Groq, Agno, DuckDuckGo, and Yahoo Finance.

## Setup

Requires Python 3.13 or later. The project uses `uv` for environment and dependency management.

```powershell
uv sync
Copy-Item .env.example .env
```

Add your Groq API key to `.env`:

```dotenv
GROQ_API_KEY=your-groq-api-key
```

Run either application:

```powershell
uv run python main-stockprice-only.py
uv run python main.-with-details.py
```

Enter a ticker symbol when prompted, for example `AAPL` or `TSLA`.

## Configuration

Application-level values are centralized in `src/investment_research/settings.py` and can be overridden in `.env`:

| Variable | Default | Purpose |
| --- | --- | --- |
| `GROQ_API_KEY` | None | Groq authentication key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model ID |
| `STOCK_PRICE_MAX_TOKENS` | `200` | Response limit for the stock-price app |
| `DEFAULT_TICKER` | `AAPL` | Default ticker for future integrations |
| `APP_NAME` | `Investment Research` | Application name |

Never commit `.env` or API keys. Use `.env.example` as the safe template.

## Observability

Each research request emits JSON-lines logs to the console and to `logs/app.log`.
The logs record:

- Selected ticker and query
- Application and model name
- Configured research tools
- Request duration
- Completion metrics when the model provides them
- Exception type and traceback when a request fails

Set `LOG_LEVEL` to `DEBUG`, `INFO`, `WARNING`, or `ERROR` to control verbosity.
Set `LOG_FILE` to change the log destination. Runtime logs are ignored by Git.

## Tests

Run the deterministic test suite with:

```powershell
uv run pytest
```

The tests cover settings, ticker validation, technical calculations, report formatting, and failure cases without calling external financial or AI APIs.
