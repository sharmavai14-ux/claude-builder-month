import ast
import json
import operator
import urllib.parse
import urllib.request
from datetime import datetime
from html.parser import HTMLParser

import anthropic

MODEL = "claude-sonnet-5-5"
MAX_STEPS = 10  # safety limit: the most tool rounds allowed for one question

SYSTEM_PROMPT = """You are a helpful personal assistant with access to tools.
Use a tool whenever it gives a more accurate answer than your own knowledge:
- the current date or time: use get_current_time
- any arithmetic, even simple: use calculate
- weather: use get_weather
- the content of a specific web page: use fetch_web_page
Answer in plain English, briefly. If a tool returns an error, explain the problem simply."""


# ---------------------------------------------------------------------------
# PART 1: The tools. Each one is an ordinary Python function.
# ---------------------------------------------------------------------------

def get_current_time() -> str:
    return datetime.now().strftime("%A %d %B %Y, %H:%M")


ALLOWED_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def calculate(expression: str) -> str:
    """Safely works out arithmetic like '(1250 * 18) / 100'. Refuses anything else."""
    def evaluate(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_OPERATORS:
            return ALLOWED_OPERATORS[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_OPERATORS:
            return ALLOWED_OPERATORS[type(node.op)](evaluate(node.operand))
        raise ValueError("only numbers and + - * / ** % are allowed")

    return str(evaluate(ast.parse(expression, mode="eval").body))


def get_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def get_weather(city: str) -> str:
    """Current weather from Open-Meteo, a free weather service that needs no API key."""
    place = get_json(
        "https://geocoding-api.open-meteo.com/v1/search?count=1&name=" + urllib.parse.quote(city)
    )
    if not place.get("results"):
        return f"Could not find a place called {city}."
    p = place["results"][0]
    weather = get_json(
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={p['latitude']}&longitude={p['longitude']}"
        "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation"
    )
    c = weather["current"]
    return (
        f"{p['name']}, {p.get('country', '')}: {c['temperature_2m']} C, humidity {c['relative_humidity_2m']}%, "
        f"wind {c['wind_speed_10m']} km/h, precipitation {c['precipitation']} mm"
    )


class TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if not self.skip_depth and data.strip():
            self.parts.append(data.strip())


def fetch_web_page(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")
    extractor = TextExtractor()
    extractor.feed(html)
    return "\n".join(extractor.parts)[:20000]  # cap the length so one page can't cost too much


# ---------------------------------------------------------------------------
# PART 2: The tool "menu" we show Claude. Name, description, and inputs for each tool.
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "get_current_time",
        "description": "Returns the current local date and time.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "calculate",
        "description": "Evaluates an arithmetic expression exactly, e.g. '(1250 * 18) / 100'. "
                       "Supports + - * / ** (power) and % (remainder).",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "The arithmetic to work out"}},
            "required": ["expression"],
        },
    },
    {
        "name": "get_weather",
        "description": "Gets the current weather for a city: temperature in Celsius, humidity, wind and rain.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name, e.g. 'Mumbai' or 'Paris'"}},
            "required": ["city"],
        },
    },
    {
        "name": "fetch_web_page",
        "description": "Downloads a web page and returns its readable text. Use it when the user gives a link.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "The full address, starting with https://"}},
            "required": ["url"],
        },
    },
]

# Connects each tool name Claude might ask for to the Python function that does the work.
TOOL_FUNCTIONS = {
    "get_current_time": get_current_time,
    "calculate": calculate,
    "get_weather": get_weather,
    "fetch_web_page": fetch_web_page,
}


def run_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Runs one tool. Returns (result text, whether it failed)."""
    try:
        return TOOL_FUNCTIONS[name](**tool_input), False
    except Exception as error:  # any problem goes back to Claude as a message, not a crash
        return f"Error: {error}", True


# ---------------------------------------------------------------------------
# PART 3: The agent loop. Ask Claude, run any tools it requests, repeat until it answers.
# ---------------------------------------------------------------------------

def main():
    client = anthropic.Anthropic()
    messages = []
    print("Your assistant has 4 tools: time, calculator, weather and web pages. Type 'quit' to stop.\n")

    while True:
        question = input("You: ").strip()
        if question.lower() in {"quit", "exit", "q"}:
            break
        if not question:
            continue
        messages.append({"role": "user", "content": question})

        for step in range(1, MAX_STEPS + 1):
            response = client.messages.create(
                model=MODEL,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )
            # Always keep Claude's full reply in the history, including its tool requests.
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                break  # Claude has finished: no more tools needed

            # Claude asked for one or more tools. Run each and collect the results.
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [step {step}] Claude uses {block.name} with {block.input}")
                    result, failed = run_tool(block.name, block.input)
                    preview = result if len(result) < 120 else result[:120] + "..."
                    print(f"           result: {preview}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,  # tells Claude which request this answers
                        "content": result,
                        "is_error": failed,
                    })
            # All results go back together, in one "user" message.
            messages.append({"role": "user", "content": tool_results})
        else:
            print("  (stopped: too many tool steps for one question)")

        if response.stop_reason == "refusal":
            print("\nAssistant: (declined to answer)\n")
            continue
        answer = "".join(b.text for b in response.content if b.type == "text")
        print(f"\nAssistant: {answer}\n")


if __name__ == "__main__":
    main()