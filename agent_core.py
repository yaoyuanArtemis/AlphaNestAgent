from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAIError
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic_ai.run import AgentRunResult

from tools import company_overview, earnings_calendar, economic_indicator, alpha_vantage_stock_history

load_dotenv()


model = OpenAIChatModel("deepseek-chat", provider=DeepSeekProvider(api_key=os.environ.get("DEEPSEEK_API_KEY")))

agent = Agent(
    model,
    tools=[alpha_vantage_stock_history, company_overview, earnings_calendar, economic_indicator],
    system_prompt=(
        "You are AlphaNestAgent, a US stock market research assistant. "
        "When the user asks about stock prices, trends, or historical performance, "
        "use the alpha_vantage_stock_history tool to fetch market data before answering. "
        "Use company_overview for fundamental context, earnings_calendar for upcoming earnings, "
        "and economic_indicator for macro data such as CPI, unemployment, nonfarm payrolls, "
        "retail sales, inflation, and federal funds rates. "
        "Do not present outputs as financial advice."
    ),
)


@dataclass
class AgentReply:
    output: str
    history: list[ModelMessage]


def format_api_error(error: Exception) -> dict[str, object]:
    details: dict[str, object] = {
        "error_type": type(error).__name__,
        "message": str(error),
    }

    if isinstance(error, ModelHTTPError):
        details.update(
            {
                "status_code": error.status_code,
                "model_name": error.model_name,
                "body": error.body,
            }
        )
    elif isinstance(error, ModelAPIError):
        details["model_name"] = error.model_name
    elif isinstance(error, UnexpectedModelBehavior):
        if error.body:
            details["body"] = error.body
    elif isinstance(error, APIStatusError):
        details.update(
            {
                "status_code": error.status_code,
                "response": error.response.text,
            }
        )
    elif isinstance(error, APIConnectionError):
        details["message"] = str(error)
    elif isinstance(error, OpenAIError):
        details["message"] = str(error)

    return details

def print_api_error(error: Exception) -> None:
    details = format_api_error(error)

    print("\n接口调用失败：")
    for key, value in details.items():
        print(f"  {key}: {value}")

def run_agent(message: str, history: list[ModelMessage] | None = None) -> AgentReply:
    resp: AgentRunResult[str] = agent.run_sync(message, message_history=history or [])
    return AgentReply(output=resp.output, history=resp.all_messages())
