"""Day 14: an agent that writes reply drafts for you, with your OK on each one.

It reads your inbox, finds the emails where a person is waiting for you,
and writes a reply for each. Before any draft is saved in Gmail, the
program stops and shows it to you. Nothing is saved without your "y".
It can never send: it has a "save a draft" tool, and no "send" tool.
"""

import asyncio
import json
from datetime import datetime
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

from gmail_tools import connect, create_reply_draft, get_headers, list_emails, read_email

HERE = Path(__file__).parent
LOG_FILE = HERE / "agent-log.txt"

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


@tool(
    "draft_reply",
    "Save a reply to one email as a draft in Gmail. It is not sent. "
    "Vaibhav sees every draft first and can say yes, no, or ask for a change.",
    {"email_id": str, "reply_text": str},
)
async def draft_reply_tool(args):
    draft_id = create_reply_draft(gmail, args["email_id"], args["reply_text"])
    return {"content": [{"type": "text", "text": f"Saved as a draft (id {draft_id}). It was NOT sent."}]}


inbox = create_sdk_mcp_server(
    name="inbox", tools=[list_emails_tool, read_email_tool, draft_reply_tool]
)

TASK = """Help me answer my emails from the last 24 hours.

1. Use list_emails to get the emails.
2. Read the full text of the emails where a real person may be waiting for me.
   Skip newsletters, adverts and automatic notifications.
3. For each email that needs a reply (at most 5), use draft_reply to save a reply.
   I see each draft before it is saved.
   - If I say no, leave that email and go on to the next one.
   - If I ask for a change, write a new version and try draft_reply again.
4. When you finish, tell me in a short list which emails got a draft and which didn't."""


def write_log(line):
    """Add one line, with the time, to the log file."""
    with LOG_FILE.open("a", encoding="utf-8") as log:
        log.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {line}\n")


def decision(choice, reason):
    """Build the answer a PreToolUse hook gives: allow or deny, and why."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": choice,
            "permissionDecisionReason": reason,
        }
    }


async def ask_vaibhav(input_data, tool_use_id, context):
    """Before any draft is saved: show it to Vaibhav and wait for an answer."""
    tool_input = input_data["tool_input"]
    try:
        original = get_headers(gmail, tool_input["email_id"])
    except Exception:
        return decision("deny", "That email id does not exist. Use an id from list_emails.")

    print("\n" + "=" * 60)
    print(f"Reply to: {original['from']}")
    print(f"Subject:  {original['subject']}")
    print("-" * 60)
    print(tool_input["reply_text"])
    print("=" * 60)
    try:
        answer = await asyncio.to_thread(input, "Save this draft? Type y, n, or what to change: ")
    except EOFError:
        answer = ""  # nobody at the keyboard, so the answer is no
    answer = answer.strip()

    if answer.lower() in ("y", "yes"):
        write_log(f"APPROVED draft to {original['from']}")
        return decision("allow", "Vaibhav said yes.")
    if answer.lower() in ("n", "no", ""):
        write_log(f"SKIPPED  draft to {original['from']}")
        return decision("deny", "Vaibhav said no to this draft. Do not draft this email again.")
    write_log(f"CHANGE   draft to {original['from']}: {answer}")
    return decision("deny", f"Vaibhav wants a change: {answer}. Write a new version and try again.")


async def log_tool(input_data, tool_use_id, context):
    """After every tool: write what it was and what it worked on."""
    tool_input = input_data["tool_input"]
    detail = (tool_input.get("email_id") or tool_input.get("hours")
              or tool_input.get("skill") or "")
    write_log(f"USED     {input_data['tool_name']}  {detail}")
    return {}


OPTIONS = ClaudeAgentOptions(
    model="claude-opus-5-5",
    effort="medium",
    cwd=HERE,
    setting_sources=["project"],
    skills=["reply-style"],
    mcp_servers={"inbox": inbox},
    tools=["Skill"],
    allowed_tools=["mcp__inbox__list_emails", "mcp__inbox__read_email"],
    hooks={
        "PreToolUse": [HookMatcher(matcher="mcp__inbox__draft_reply", hooks=[ask_vaibhav])],
        "PostToolUse": [HookMatcher(hooks=[log_tool])],
    },
    max_turns=40,
    max_budget_usd=1.00,
)


async def main():
    write_log("----- New reply run -----")
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
    print("Open Gmail > Drafts to read, edit and send your replies.")


asyncio.run(main())