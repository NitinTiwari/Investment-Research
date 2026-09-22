from agno.agent import Agent
from agno.tools.duckduckgo import DuckDuckGoTools
from agno.tools.yfinance import YFinanceTools
from agno.models.groq import Groq 
from investment_research.settings import settings

llm = Groq(id=settings.model_name)

web_agent = Agent(
    model=llm,
    tools=[DuckDuckGoTools()],
    instructions="always include sources",
    markdown=True
)

finance_agent = Agent(
    model=llm,
    tools=[
        YFinanceTools(
            enable_stock_price=True, 
            enable_company_news=True, 
            enable_analyst_recommendations=True, 
            enable_income_statements=True
        )
    ],
    instructions="use table to display data",
    markdown=True
)

agent_team = Agent(
    model=llm,
    tools=[web_agent, finance_agent],
    markdown=True,
    instructions=["always include sources", "use table to display data", "write a detailed research report on the company"],
)

input_data = input("Enter ticker symbol: ")
agent_team.print_response(f"what is the current stock price of {input_data} ", stream=True)
