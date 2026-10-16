import anthropic
from anthropic import beta_tool

import agent as day3  # yesterday's file: we reuse its tool functions instead of copying them

MODEL = "claude-sonnet-5-5"


# Each tool is now a function with a "@beta_tool" label on top.
# The runner reads the function's name, inputs and description (the text in triple quotes)
# and builds the tool menu for Claude automatically. No more hand-written TOOLS list.

@beta_tool
def get_current_time() -> str:
    """Returns the current local date and time."""
    return day3.get_current_time()


@beta_tool
def calculate(expression: str) -> str:
    """Evaluates an arithmetic expression exactly. Supports + - * / ** (power) and % (remainder).

    Args:
        expression: The arithmetic to work out, e.g. '(1250 * 18) / 100'.
    """
    return day3.calculate(expression)


@beta_tool
def get_weather(city: str) -> str:
    """Gets the current weather for a city: temperature in Celsius, humidity, wind and rain.

    Args:
        city: City name, e.g. 'Mumbai' or 'Paris'.
    """
    return day3.get_weather(city)


@beta_tool
def fetch_web_page(url: str) -> str:
    """Downloads a web page and returns its readable text. Use it when the user gives a link.

    Args:
        url: The full address, starting with https://
    """
    return day3.fetch_web_page(url)


TOOLS = [get_current_time, calculate, get_weather, fetch_web_page]


def main():
    client = anthropic.Anthropic()
    history = []  # we keep our own copy of the conversation so follow-up questions work
    print("Agent v2 (tool runner). Type 'quit' to stop.\n")

    while True:
        question = input("You: ").strip()
        if question.lower() in {"quit", "exit", "q"}:
            break
        if not question:
            continue
        history.append({"role": "user", "content": question})

        # The runner IS the agent loop from Day 3: call Claude, run tools, repeat until done.
        runner = client.beta.messages.tool_runner(
            model=MODEL,
            max_tokens=4000,
            system=day3.SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history,
            max_iterations=10,  # same safety limit as MAX_STEPS yesterday
        )

        final = None
        for message in runner:  # one pass per call to Claude
            final = message
            history.append({"role": "assistant", "content": message.content})
            for block in message.content:
                if block.type == "tool_use":
                    print(f"  [tool] {block.name} {block.input}")
            tool_results = runner.generate_tool_call_response()  # runs the tools (only once)
            if tool_results is not None:
                history.append(tool_results)

        if final is None or final.stop_reason == "refusal":
            print("\nAssistant: (no answer)\n")
            continue
        answer = "".join(b.text for b in final.content if b.type == "text")
        print(f"\nAssistant: {answer}\n")


if __name__ == "__main__":
    main()