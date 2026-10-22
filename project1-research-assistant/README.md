# Personal Research Assistant

Type a question. Claude searches the web, writes a short report with
sources, saves it as a Markdown file, and saves a summary note into my
own notes server (built with MCP), so I can find it later from Claude Code.

Built in Week 1 of my one-month Claude builder program.

## What it does

1. Asks Claude (Opus 5.5) to research the question using web search.
2. Shows the answer live as it is written.
3. Saves a report with a numbered list of sources in `reports/`.
4. Saves a short note through my Day 5 notes MCP server.
5. Prints the searches it made, the tokens used, and the cost.

## How to run it

You need: Python, [uv](https://docs.astral.sh/uv/), and an Anthropic API key
in the `ANTHROPIC_API_KEY` environment variable.

    uv run research.py

The notes server must be in a folder called `day05-notes-mcp` next to this one.

## Example

Question: [your question]

    [paste the "--- Done ---" part of your output here]

## Testing

`evals.py` asks 10 questions with known answers and checks each report has
a short answer, details, sources, and the right answer. One question is about
a made-up place, to check the assistant admits when it can't find something.

    uv run evals.py

Latest score: [10] out of 10, cost about $[0.94] per run.

## Cost

About [10 to 15] US cents per question with Opus 5.5.

## Built with

- Claude API (Anthropic Python SDK) with the web search tool
- MCP (Model Context Protocol) Python SDK
- uv

## Demo

[link to your 2-minute video]