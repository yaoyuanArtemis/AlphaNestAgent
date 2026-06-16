from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError, UnexpectedModelBehavior
from openai import APIConnectionError, APIStatusError, OpenAIError
import os

from dotenv import load_dotenv
from pprint import pprint

load_dotenv()




model = OpenAIChatModel("deepseek-chat", provider=DeepSeekProvider(api_key=os.environ.get("DEEPSEEK_API_KEY")))

agent = Agent(model)


def print_api_error(error: Exception) -> None:
    print("\n接口调用失败：")
    print(f"  error_type: {type(error).__name__}")

    if isinstance(error, ModelHTTPError):
        print(f"  status_code: {error.status_code}")
        print(f"  model_name: {error.model_name}")
        print(f"  body: {error.body}")
    elif isinstance(error, ModelAPIError):
        print(f"  model_name: {error.model_name}")
        print(f"  message: {error}")
    elif isinstance(error, UnexpectedModelBehavior):
        print(f"  message: {error}")
        if error.body:
            print(f"  body: {error.body}")
    elif isinstance(error, APIStatusError):
        print(f"  status_code: {error.status_code}")
        print(f"  response: {error.response.text}")
    elif isinstance(error, APIConnectionError):
        print(f"  message: {error}")
    elif isinstance(error, OpenAIError):
        print(f"  message: {error}")
    else:
        print(f"  message: {error}")


def main():
    history = []
    while True:
        user_input = input("请输入：")
        if user_input.strip().lower() in {"exit", "quit"}:
            break

        try:
            resp = agent.run_sync(user_input,message_history=history)
            print("resp.all_messages",resp.all_messages)
            history = list(resp.all_messages)
        except Exception as error:
            print_api_error(error)
            continue

        print(resp)

if __name__ == "__main__":
    main()

