import sys
import urllib.request
from html.parser import HTMLParser

import anthropic
from dotenv import load_dotenv

load_dotenv()  # reads ANTHROPIC_API_KEY from the repo's .env file

MODEL = "claude-sonnet-5-5"

# US dollars per 1 million tokens: (input, output). Check current prices before relying on them.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}

SYSTEM_PROMPT = """You summarize web pages for a busy reader.
Return:
1. A one-sentence summary.
2. Three to five key points as bullets.
3. One line on who would find this page useful.
Use only what the page says. If the page has little real content, say so."""


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


def main():
    if len(sys.argv) < 2:
        print("Usage: uv run summarize.py <url>")
        sys.exit(1)
    url = sys.argv[1]

    print(f"Fetching {url} ...")
    page_text = fetch_page_text(url)
    print(f"Got {len(page_text):,} characters of text.\n")

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"<page url=\"{url}\">\n{page_text}\n</page>\n\nSummarize this page.",
            }
        ],
    )

    if response.stop_reason == "refusal":
        print("Claude declined to summarize this page.")
        return

    for block in response.content:
        if block.type == "text":
            print(block.text)

    usage = response.usage
    input_price, output_price = PRICES[MODEL]
    cost = usage.input_tokens / 1e6 * input_price + usage.output_tokens / 1e6 * output_price
    print("\n---")
    print(f"Model:         {MODEL}")
    print(f"Stop reason:   {response.stop_reason}")
    print(f"Input tokens:  {usage.input_tokens:,}")
    print(f"Output tokens: {usage.output_tokens:,}")
    print(f"Cost:          ${cost:.5f}")


if __name__ == "__main__":
    main()