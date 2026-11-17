"""Day 11: a report agent with house rules, a skill and a memory.

- CLAUDE.md holds the house rules. The agent reads them every time it starts.
- .claude/skills/house-report/SKILL.md is the house report style.
  The agent opens it whenever you ask for a report.
- session.txt remembers your last chat, so you can carry on tomorrow.
Type "bye" to stop.
"""

import asyncio
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultError,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

HERE = Path(__file__).parent
PRACTICE_FOLDER = HERE.parent / "day08-agent-sdk" / "practice"
OUTPUT_FOLDER = HERE / "output"
SESSION_FILE = HERE / "session.txt"


def last_session():
    """Return the id of the last chat, or None if there isn't one."""
    if SESSION_FILE.exists():
        return SESSION_FILE.read_text(encoding="utf-8").strip() or None
    return None


def ask_to_continue():
    """If there is a saved chat, ask whether to carry on with it."""
    saved = last_session()
    if saved is None:
        return None
    answer = input("Carry on with your last chat? (y/n): ").strip().lower()
    return saved if answer.startswith("y") else None


def make_options(resume_id):
    return ClaudeAgentOptions(
        model="claude-opus-5-5",
        effort="medium",
        cwd=HERE,
        add_dirs=[PRACTICE_FOLDER],
        setting_sources=["project"],
        skills=["house-report"],
        tools=["Glob", "Read", "Write", "Skill"],
        allowed_tools=["Glob", "Read", "Write"],
        resume=resume_id,
        max_turns=20,
        max_budget_usd=1.00,
    )


async def main():
    OUTPUT_FOLDER.mkdir(exist_ok=True)
    resume_id = ask_to_continue()
    if resume_id:
        print("Carrying on from last time.\n")
    else:
        print("Starting a new chat.\n")
    print("Type 'bye' to stop.\n")

    async with ClaudeSDKClient(options=make_options(resume_id)) as agent:
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
                                print(f"  [{block.name}]")
                            elif isinstance(block, TextBlock):
                                print(f"Agent: {block.text}")
                    elif isinstance(message, ResultMessage):
                        SESSION_FILE.write_text(message.session_id, encoding="utf-8")
                        if message.subtype != "success":
                            print(f"Agent stopped early. Reason: {message.subtype}")
            except ResultError as error:
                print(f"Agent stopped early. Reason: {error.subtype}")
            print()
    print(f"Bye! Your chat is saved in {SESSION_FILE.name}")


asyncio.run(main())