"""Day 13: an agent that reads your Gmail and writes a morning brief.

It can only read your email (never send, change or delete), and it can
only write files inside the "output" folder. Every tool it uses is
written into agent-log.txt.
"""

import asyncio
import json
from datetime import date, datetime
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultError,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

from gmail_tools import connect, list_emails, read_email

HERE = Path(__file__).parent
OUTPUT_FOLDER = HERE / "output"
LOG_FILE = HERE / "agent-log.txt"
BRIEF_FILE = OUTPUT_FOLDER / f"brief-{date.today():%Y-%m-%d}.md"

gmail = connect()


@tool(
    "list_emails",
    "List the emails that arrived in the inbox in the last few hours. "
    "For each one you get its id, sender, subject, date, whether it is unread, and a short preview.",
    {"hours": int},
)
async def list_emails_tool(args):
    emails = list_emails(gmail, hours=args["hours"])
    return {"content": [{"type": "text", "text": json.dumps(emails, indent=2)}]}


@tool(
    "read_email",
    "Read the full text of one email. Use the id from list_emails.",
    {"email_id": str},
)
async def read_email_tool(args):
    text = read_email(gmail, args["email_id"])
    return {"content": [{"type": "text", "text": text}]}


inbox = create_sdk_mcp_server(name="inbox", tools=[list_emails_tool, read_email_tool])

TASK = f"""Make my morning brief for today, {date.today():%A %d %B %Y}.

1. Use list_emails to get the emails from the last 24 hours.
2. Read the full text of any email that might need me.
   You don't need to read clear newsletters or adverts.
3. Write the brief to the file {BRIEF_FILE}.
When you finish, say in one or two sentences what you did."""


def write_log(line):
    """Add one line, with the time, to the log file."""
    with LOG_FILE.open("a", encoding="utf-8") as log:
        log.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {line}\n")


async def guard_writes(input_data, tool_use_id, context):
    """Before any Write: block it unless the file is inside the output folder."""
    file_path = Path(input_data["tool_input"].get("file_path", "")).resolve()
    if OUTPUT_FOLDER.resolve() in file_path.parents:
        return {}
    write_log(f"BLOCKED  Write to {file_path}")
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "You may only write files inside the output folder.",
        }
    }


async def log_tool(input_data, tool_use_id, context):
    """After every tool: write what it was and what it worked on."""
    tool_input = input_data["tool_input"]
    detail = (tool_input.get("file_path") or tool_input.get("email_id")
              or tool_input.get("hours") or tool_input.get("skill") or "")
    write_log(f"USED     {input_data['tool_name']}  {detail}")
    return {}


OPTIONS = ClaudeAgentOptions(
    model="claude-opus-5-5",
    effort="medium",
    cwd=HERE,
    setting_sources=["project"],
    skills=["daily-brief"],
    mcp_servers={"inbox": inbox},
    tools=["Write", "Skill"],
    allowed_tools=["Write", "mcp__inbox__list_emails", "mcp__inbox__read_email"],
    hooks={
        "PreToolUse": [HookMatcher(matcher="Write", hooks=[guard_writes])],
        "PostToolUse": [HookMatcher(hooks=[log_tool])],
    },
    max_turns=40,
    max_budget_usd=1.00,
)


async def main():
    OUTPUT_FOLDER.mkdir(exist_ok=True)
    write_log("----- New run -----")
    try:
        async for message in query(prompt=TASK, options=OPTIONS):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        print(f"  [{block.name}]")
                    elif isinstance(block, TextBlock):
                        print(block.text)
            elif isinstance(message, ResultMessage):
                print("\n--- Done ---")
                print(f"Turns: {message.num_turns}")
                print(f"Cost: about ${message.total_cost_usd or 0:.4f}")
    except ResultError as error:
        print(f"\nThe agent stopped before finishing. Reason: {error.subtype}")
    print(f"Your brief: {BRIEF_FILE}")


asyncio.run(main())