from pydantic_ai.messages import ModelMessage

from agent_core import print_api_error, run_agent


def main() -> None:
    history: list[ModelMessage] = []

    while True:
        user_input: str = input("请输入：")
        if user_input.strip().lower() in {"exit", "quit"}:
            break

        try:
            reply = run_agent(user_input, history)
            history = reply.history
        except Exception as error:
            print_api_error(error)
            continue

        print(reply.output)


if __name__ == "__main__":
    main()
