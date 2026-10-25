"""Day 9: a chat agent with your own tools.

You chat with it in the terminal. It can:
- read the notes files in your Day 8 practice folder (built-in tools)
- save and find notes in your Day 5 notes server (your MCP server)
- work out how many days until a date (a tool written in this file)
Type "bye" to stop.
"""

import asyncio
from datetime import date
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultError,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    tool,
)

HERE = Path(__file__).parent
PRACTICE_FOLDER = HERE.parent / "day08-agent-sdk" / "practice"
NOTES_SERVER_FOLDER = HERE.parent / "day05-notes-mcp"


@tool(
    "days_until",
    "Count how many days from today until a date. The date must look like 2026-12-25.",
    {"target_date": str},
)
async def days_until(args):
    today = date.today()
    try:
        target = date.fromisoformat(args["target_date"])
    except ValueError:
        return {"content": [{"type": "text",
                             "text": "That date isn't in the form YYYY-MM-DD."}],
                "is_error": True}
    days = (target - today).days
    text = f"Today is {today:%A %d %B %Y}. {target:%A %d %B %Y} is {days} days away."
    return {"content": [{"type": "text", "text": text}]}


my_tools = create_sdk_mcp_server(name="mytools", tools=[days_until])

notes_server = {
    "type": "stdio",
    "command": "uv",
    "args": ["run", "--directory", str(NOTES_SERVER_FOLDER), "notes_server.py"],
}

ALLOWED = [
    "Glob",
    "Read",
    "mcp__notes__add_note",
    "mcp__notes__list_notes",
    "mcp__notes__search_notes",
    "mcp__mytools__days_until",
]

OPTIONS = ClaudeAgentOptions(
    model="claude-opus-5-5",
    effort="medium",
    cwd=PRACTICE_FOLDER,
    system_prompt=(
        "You are a friendly personal assistant. You can read the user's "
        "notes files in this folder, save and search notes in their notebook, "
        "and count days until a date. Keep answers short and simple."
    ),
    mcp_servers={"notes": notes_server, "mytools": my_tools},
    tools=["Glob", "Read"],
    allowed_tools=ALLOWED,
    max_turns=20,
    max_budget_usd=1.00,
)


def describe(tool_name, tool_input):
    """Turn a tool request into a short, readable line."""
    if tool_name == "Glob":
        return f"Looking for files matching {tool_input.get('pattern')}"
    if tool_name == "Read":
        return f"Reading {Path(tool_input.get('file_path', '')).name}"
    if tool_name == "mcp__notes__add_note":
        return f"Saving a note: {tool_input.get('title')}"
    if tool_name == "mcp__notes__list_notes":
        return "Listing your notes"
    if tool_name == "mcp__notes__search_notes":
        return f"Searching your notes for: {tool_input.get('query')}"
    if tool_name == "mcp__mytools__days_until":
        return f"Counting days until {tool_input.get('target_date')}"
    return f"Using {tool_name}"


async def main():
    print("Chat with your agent. Type 'bye' to stop.\n")
    total_cost = 0.0
    async with ClaudeSDKClient(options=OPTIONS) as agent:
        while True:
            request = (await asyncio.to_thread(input, "You: ")).strip()
            if request.lower() in ("bye", "exit", "quit"):
                break
            if not request:
                continue
            await agent.query(request)
            try:
                async for message in agent.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, ToolUseBlock):
                                print(f"  [{describe(block.name, block.input)}]")
                            elif isinstance(block, TextBlock):
                                print(f"Agent: {block.text}")
                    elif isinstance(message, ResultMessage):
                        total_cost = message.total_cost_usd or total_cost
                        if message.subtype != "success":
                            print(f"Agent stopped early. Reason: {message.subtype}")
            except ResultError as error:
                print(f"Agent stopped early. Reason: {error.subtype}")
            print()
    print(f"Bye! This chat cost about ${total_cost:.4f}")


asyncio.run(main())