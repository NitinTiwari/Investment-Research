from agno.agent import Agent
from agno.tools.yfinance import YFinanceTools
from agno.models.groq import Groq 
from investment_research.settings import settings

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
input_data = input("Enter ticker symbol (e.g., AAPL, TSLA): ")

print(f"\nFetching price for {input_data.upper()}...")
finance_agent.print_response(f"What is the current stock price of {input_data}?", stream=True)
