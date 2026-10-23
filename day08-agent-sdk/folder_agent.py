"""Day 8: an agent that works inside a folder.

It reads every .txt file in the "practice" folder and writes
summary.md with a short summary of each file and all the to-do items.
It can only use three tools: Glob (find files), Read and Write.
"""

import asyncio
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultError,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

WORK_FOLDER = Path(__file__).parent / "practice"

TASK = """Read every .txt file in this folder.
Then create a file called summary.md that has:
- a heading for each file, with a 1 or 2 sentence summary of it
- at the end, a section "## All to-do items" listing every task
  mentioned in any file, as a checklist (- [ ] ...)
Use simple words. Don't change or delete any other file."""

OPTIONS = ClaudeAgentOptions(
    model="claude-opus-5-5",
    effort="medium",
    cwd=WORK_FOLDER,
    tools=["Glob", "Read", "Write"],
    allowed_tools=["Glob", "Read", "Write"],
    max_turns=15,
    max_budget_usd=0.50,
)


def describe(tool_name, tool_input):
    """Turn a tool request into a short, readable line."""
    if tool_name == "Glob":
        return f"Looking for files matching {tool_input.get('pattern')}"
    if tool_name == "Read":
        return f"Reading {Path(tool_input.get('file_path', '')).name}"
    if tool_name == "Write":
        return f"Writing {Path(tool_input.get('file_path', '')).name}"
    return f"Using {tool_name}"


async def main():
    print(f"Working in: {WORK_FOLDER}\n")
    try:
        async for message in query(prompt=TASK, options=OPTIONS):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        print(f"[{describe(block.name, block.input)}]")
                    elif isinstance(block, TextBlock):
                        print(block.text)
            elif isinstance(message, ResultMessage):
                print("\n--- Done ---")
                print(f"Finished: {message.subtype}")
                print(f"Turns: {message.num_turns}")
                print(f"Time: {message.duration_ms / 1000:.1f} seconds")
                print(f"Cost: about ${message.total_cost_usd or 0:.4f}")
    except ResultError as error:
        print(f"\nThe agent stopped before finishing. Reason: {error.subtype}")


asyncio.run(main())