import re
from datetime import datetime
from pathlib import Path

import anthropic

MODEL = "claude-opus-5-5"
MAX_SEARCHES = 5
REPORTS_DIR = Path(__file__).parent / "reports"

# Prices in US dollars
PRICE_PER_INPUT_TOKEN = 4.00 / 1_000_000
PRICE_PER_OUTPUT_TOKEN = 20.00 / 1_000_000
PRICE_PER_SEARCH = 10.00 / 1_000

INSTRUCTIONS = """You are a careful research assistant.

Today's date is {today}. Your own knowledge is older than that, so search
the web for anything that may have changed.

How to work:
1. Search the web for the user's question. Use a few different searches
   if one is not enough.
2. Prefer official and well-known sources.
3. Then write the report.

How to write the report:
- Start with a title line that begins with "# ".
- Then a section "## Short answer" with 2 or 3 sentences.
- Then a section "## Details" with 3 to 6 bullet points.
- Use simple, everyday words.
- Only say things your sources support. If sources disagree, or you
  could not find something, say so plainly.
- Do not write your own list of sources. The program adds it.
"""


def research(client, question):
    """Ask Claude to research the question. Show the answer as it is written.

    Returns all the pieces Claude produced, and how many tokens and
    searches were used.
    """
    today = datetime.now().strftime("%d %B %Y")
    messages = [{"role": "user", "content": question}]
    pieces = []
    used = {"input": 0, "output": 0, "searches": 0}

    for round_number in range(1, 6):
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=64000,
            system=INSTRUCTIONS.format(today=today),
            tools=[{"type": "web_search_20260209", "name": "web_search",
                    "max_uses": MAX_SEARCHES}],
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=messages,
        ) as stream:
            for event in stream:
                if (event.type == "content_block_start"
                        and event.content_block.type == "server_tool_use"):
                    print("\n[Searching the web...]", flush=True)
                elif (event.type == "content_block_delta"
                        and event.delta.type == "text_delta"):
                    print(event.delta.text, end="", flush=True)
            message = stream.get_final_message()

        pieces.extend(message.content)
        used["input"] += message.usage.input_tokens
        used["output"] += message.usage.output_tokens
        if message.usage.server_tool_use:
            used["searches"] += message.usage.server_tool_use.web_search_requests or 0

        if message.stop_reason == "refusal":
            print("\n\nClaude declined to research this question.")
            break
        if message.stop_reason != "pause_turn":
            break
        # "pause_turn" means Claude paused in the middle of its searching.
        # We send back what it has done so far, and it carries on.
        messages = [
            {"role": "user", "content": question},
            {"role": "assistant", "content": message.content},
        ]

    print()
    return pieces, used


def collect_sources(pieces):
    """Make a list of the web pages Claude quoted, without repeats."""
    sources = []
    seen_urls = set()
    for piece in pieces:
        if piece.type == "text" and piece.citations:
            for citation in piece.citations:
                if citation.url not in seen_urls:
                    seen_urls.add(citation.url)
                    sources.append((citation.title, citation.url))
    return sources


def collect_searches(pieces):
    """Make a list of the searches Claude typed into the search engine."""
    return [piece.input.get("query", "") for piece in pieces
            if piece.type == "server_tool_use" and piece.name == "web_search"]


def save_report(question, pieces, sources):
    """Write the report and its sources to a Markdown file. Return the file path."""
    report_text = "".join(piece.text for piece in pieces if piece.type == "text")

    lines = [report_text.strip(), "", "## Sources", ""]
    if sources:
        for number, (title, url) in enumerate(sources, start=1):
            lines.append(f"{number}. [{title}]({url})")
    else:
        lines.append("No sources were quoted.")
    lines += ["", f"*Question: {question}*",
              f"*Researched on {datetime.now().strftime('%Y-%m-%d %H:%M')}*"]

    short_name = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")[:50]
    file_name = f"{datetime.now().strftime('%Y-%m-%d')}-{short_name or 'report'}.md"
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / file_name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main():
    client = anthropic.Anthropic()
    question = input("What should I research? ").strip()
    if not question:
        print("You didn't type a question. Bye!")
        return

    pieces, used = research(client, question)
    sources = collect_sources(pieces)
    searches = collect_searches(pieces)
    path = save_report(question, pieces, sources)

    cost = (used["input"] * PRICE_PER_INPUT_TOKEN
            + used["output"] * PRICE_PER_OUTPUT_TOKEN
            + used["searches"] * PRICE_PER_SEARCH)

    print("\n--- Done ---")
    print(f"Searches Claude made: {len(searches)}")
    for query in searches:
        print(f"  - {query}")
    print(f"Sources quoted: {len(sources)}")
    print(f"Report saved to: {path}")
    print(f"Tokens: {used['input']:,} in, {used['output']:,} out. "
          f"Searches billed: {used['searches']}. Cost: about ${cost:.3f}")


if __name__ == "__main__":
    main()