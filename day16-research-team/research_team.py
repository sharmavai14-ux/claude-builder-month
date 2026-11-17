"""Day 16: a research team. One lead (Opus) plans the work and sends out
up to four researchers (Haiku). Each researcher has its own fresh memory,
searches the web for one small question, and reports back. The lead then
writes one report.
"""

import asyncio
import sys
from pathlib import Path

from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultError,
    ResultMessage,
    TaskNotificationMessage,
    TaskStartedMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

sys.stdout.reconfigure(encoding="utf-8")  # so symbols like ₹ print without crashing

HERE = Path(__file__).parent
OUTPUT_FOLDER = HERE / "output"
REPORT_FILE = OUTPUT_FOLDER / "report.md"

QUESTION = "What are the best low-cost ways for a small cafe in India to get more customers?"

RESEARCHER = AgentDefinition(
    description="Researches ONE small, clear question on the web and reports back. "
                "Send one researcher per question.",
    prompt="""You are a careful researcher. You get one small question.
1. Search the web and read 2 or 3 good pages.
2. Reply with at most 5 short bullet points of facts you found.
3. After each fact, put the web address it came from.
Only report what the pages say. If you find nothing good, say so.""",
    tools=["WebSearch", "WebFetch"],
    model="haiku",
    maxTurns=10,
)

TASK = f"""Research this question for me: {QUESTION}

1. Split it into 3 or 4 smaller questions that don't overlap.
2. Send one researcher for each smaller question. Send them all in the same
   message so they work at the same time, and wait for their answers
   (set run_in_background to false).
3. When they have all reported, write a report to {REPORT_FILE} with:
   a one-line answer at the top, a short section for each smaller question,
   and a list of the web addresses the researchers used.
Don't search the web yourself: leave that to the researchers.
Use only facts the researchers found. When you finish, say in one sentence what you did."""


async def guard_writes(input_data, tool_use_id, context):
    """Before any Write: block it unless the file is inside the output folder."""
    file_path = Path(input_data["tool_input"].get("file_path", "")).resolve()
    if OUTPUT_FOLDER.resolve() in file_path.parents:
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "You may only write files inside the output folder.",
        }
    }


OPTIONS = ClaudeAgentOptions(
    model="claude-opus-5-5",
    effort="medium",
    cwd=HERE,
    agents={"researcher": RESEARCHER},
    tools=["Agent", "Write", "WebSearch", "WebFetch"],
    allowed_tools=["Agent", "Write", "WebSearch", "WebFetch"],
    hooks={"PreToolUse": [HookMatcher(matcher="Write", hooks=[guard_writes])]},
    max_turns=30,
    max_budget_usd=2.00,
)


async def main():
    OUTPUT_FOLDER.mkdir(exist_ok=True)
    try:
        async for message in query(prompt=TASK, options=OPTIONS):
            if isinstance(message, TaskStartedMessage):
                print(f"\n>> Researcher started: {message.description}")
            elif isinstance(message, TaskNotificationMessage):
                print(f"\n<< Researcher {message.status}: {message.summary}")
            elif isinstance(message, AssistantMessage):
                who = "researcher" if message.parent_tool_use_id else "lead"
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        print(f"  [{who} uses {block.name}]")
                    elif isinstance(block, TextBlock) and who == "lead":
                        print(block.text)
            elif isinstance(message, ResultMessage):
                print("\n--- Done ---")
                for model, usage in (message.model_usage or {}).items():
                    print(f"{model}: about ${usage['costUSD']:.4f}")
                print(f"Total: about ${message.total_cost_usd or 0:.4f}")
    except ResultError as error:
        print(f"\nThe team stopped before finishing. Reason: {error.subtype}")
    print(f"Your report: {REPORT_FILE}")


asyncio.run(main())