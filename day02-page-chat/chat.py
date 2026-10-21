import sys
import urllib.request
from html.parser import HTMLParser

import anthropic
from dotenv import load_dotenv

load_dotenv()  # reads ANTHROPIC_API_KEY from the repo's .env file

MODEL = "claude-sonnet-5-5"

# US dollars per 1 million tokens. Check current prices before relying on them.
#   input        = normal input tokens
#   cache_write  = input tokens saved into the cache (costs a bit MORE than normal, once)
#   cache_read   = input tokens re-used from the cache (costs much LESS)
#   output       = tokens Claude writes
PRICES = {
    "claude-opus-5-5":   {"input": 4.00, "cache_write": 5.00,  "cache_read": 0.20,  "output": 20.00},
    "claude-sonnet-5-5": {"input": 2.00, "cache_write": 2.50,  "cache_read": 0.20,  "output": 10.00},
    "claude-haiku-5-5":  {"input": 0.10, "cache_write": 0.125, "cache_read": 0.01,  "output": 0.50},
}

INSTRUCTIONS = """You are a careful research assistant. The user is reading the web page below and will ask you questions about it.

How to answer:
- Answer only from the page. If the page does not contain the answer, say "The page doesn't say." and stop. Do not guess or use outside knowledge.
- Keep answers short: 2 to 4 sentences, or up to 5 bullets for lists.
- When you state a fact, quote the key words from the page in "double quotes" so the reader can find them.
- Write in plain English for a non-technical reader. Explain any jargon in a few words.

<example>
Question: Who wrote this article?
Answer: The page doesn't say who wrote it. It is published on "Engineering at Anthropic".
</example>"""


class TextExtractor(HTMLParser):
    """Keeps visible text and skips scripts, styles and other non-content tags."""

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


def fetch_page_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", errors="replace")
    extractor = TextExtractor()
    extractor.feed(html)
    return "\n".join(extractor.parts)


def cost_of(usage) -> float:
    p = PRICES[MODEL]
    return (
        usage.input_tokens / 1e6 * p["input"]
        + (usage.cache_creation_input_tokens or 0) / 1e6 * p["cache_write"]
        + (usage.cache_read_input_tokens or 0) / 1e6 * p["cache_read"]
        + usage.output_tokens / 1e6 * p["output"]
    )


def cost_without_cache(usage) -> float:
    """What the same call would have cost if every input token was billed at the normal price."""
    p = PRICES[MODEL]
    all_input = usage.input_tokens + (usage.cache_creation_input_tokens or 0) + (usage.cache_read_input_tokens or 0)
    return all_input / 1e6 * p["input"] + usage.output_tokens / 1e6 * p["output"]


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run chat.py <url>")
        sys.exit(1)
    url = sys.argv[1]

    print(f"Fetching {url} ...")
    page_text = fetch_page_text(url)
    print(f"Got {len(page_text):,} characters. Ask questions about the page. Type 'quit' to stop.\n")

    # The system prompt has two parts. The page is the big part, so we mark it for caching.
    system = [
        {"type": "text", "text": INSTRUCTIONS},
        {
            "type": "text",
            "text": f"<page url=\"{url}\">\n{page_text}\n</page>",
            "cache_control": {"type": "ephemeral"},  # "remember this part for the next 5 minutes"
        },
    ]

    client = anthropic.Anthropic()
    history = []  # the conversation so far: Claude has no memory, so we resend it every time
    total_cost = 0.0
    total_without_cache = 0.0

    while True:
        question = input("You: ").strip()
        if question.lower() in {"quit", "exit", "q"}:
            break
        if not question:
            continue

        history.append({"role": "user", "content": question})
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=system,
            messages=history,
        )

        if response.stop_reason == "refusal":
            print("Claude: (declined to answer)\n")
            history.pop()  # drop the question so the conversation stays valid
            continue

        answer = "".join(block.text for block in response.content if block.type == "text")
        print(f"\nClaude: {answer}\n")
        history.append({"role": "assistant", "content": response.content})

        u = response.usage
        cost = cost_of(u)
        total_cost += cost
        total_without_cache += cost_without_cache(u)
        print(
            f"  [tokens] new input: {u.input_tokens:,} | written to cache: {u.cache_creation_input_tokens or 0:,}"
            f" | read from cache: {u.cache_read_input_tokens or 0:,} | output: {u.output_tokens:,}"
        )
        print(f"  [cost] this question: ${cost:.5f} | session so far: ${total_cost:.5f}\n")

    if total_without_cache:
        saved = total_without_cache - total_cost
        print(f"Session cost: ${total_cost:.5f}. Without caching it would have been ${total_without_cache:.5f}.")
        print(f"Caching saved ${saved:.5f} ({saved / total_without_cache:.0%}).")


if __name__ == "__main__":
    main()