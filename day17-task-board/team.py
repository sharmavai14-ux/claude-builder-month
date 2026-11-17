"""Day 17: a team that works through a shared task board.

A planner fills the board with writing tasks. Writers take one task each,
write it, and hand it on to a checker. A checker approves the work, or hands
it back to a writer with notes. Every agent starts fresh: everything it needs
is on the board. Stop the program at any time, run it again, and it carries on.
"""

import asyncio
import json
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultError,
    ResultMessage,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

import board

HERE = Path(__file__).parent
OUTPUT_FILE = HERE / "output" / "approved.md"
GOAL = ("Sunrise Cafe is starting a weekend brunch. We need: a 2-line description "
        "for each of 3 new brunch dishes (masala omelette, banana pancakes, "
        "avocado toast), and one short Instagram post announcing the brunch.")
MAX_STEPS = 15  # never run more than 15 agent jobs in one go
spent = {"dollars": 0.0}


def reply(data):
    """Tools answer with text. We turn Python data into JSON text."""
    return {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}


@tool("add_task", "Add a new task to the board. kind is 'write' or 'check'.",
      {"kind": str, "title": str, "details": str})
async def add_task_tool(args):
    return reply({"new_task_id": board.add_task(args["kind"], args["title"], args["details"])})


def make_claim_tool(owner):
    @tool("claim_task", "Take the next waiting task of this kind ('write' or 'check').",
          {"kind": str})
    async def claim_task_tool(args):
        return reply(board.claim_task(args["kind"], owner) or "No tasks waiting.")
    return claim_task_tool


@tool("get_task", "Read any task on the board, with its result.", {"task_id": int})
async def get_task_tool(args):
    return reply(board.get_task(args["task_id"]) or "No task with that id.")


@tool("finish_task", "Mark your task as done and save your result.",
      {"task_id": int, "result": str})
async def finish_task_tool(args):
    board.finish_task(args["task_id"], args["result"])
    return reply("Saved.")


@tool("hand_off", "Hand your finished work on: create a new task for the next role. "
      "to_kind is 'check' (writer to checker) or 'write' (checker back to writer).",
      {"task_id": int, "to_kind": str, "note": str})
async def hand_off_tool(args):
    if board.chain_length(args["task_id"]) >= board.MAX_CHAIN:
        return reply("Refused: this work has been handed on too many times. Stop here.")
    task = board.get_task(args["task_id"])
    new_id = board.add_task(args["to_kind"], task["title"], args["note"], parent_id=task["id"])
    return reply({"new_task_id": new_id})


ROLES = {
    "planner": {
        "model": "claude-opus-5-5",
        "tools": [add_task_tool],
        "prompt": f"""You plan work for a small team. The goal:
{GOAL}
Add one 'write' task for each separate piece of writing. Give each a clear title,
and put everything the writer needs in details. Do not write anything yourself.""",
    },
    "writer": {
        "model": "claude-haiku-5-5",
        "tools": [make_claim_tool("writer"), get_task_tool, finish_task_tool, hand_off_tool],
        "prompt": """You are a writer for Sunrise Cafe, a small friendly cafe.
1. Use claim_task with kind 'write' to take ONE task.
2. If it has a parent_id, use get_task on the parent to see the checker's notes,
   and on the parent's parent to see the earlier version.
3. Write what the task asks. Warm, simple, no made-up prices or claims.
4. Use finish_task to save your writing as the result.
5. Use hand_off with to_kind 'check' and a note saying what to check.""",
    },
    "checker": {
        "model": "claude-opus-5-5",
        "tools": [make_claim_tool("checker"), get_task_tool, finish_task_tool, hand_off_tool],
        "prompt": """You check writing for Sunrise Cafe.
1. Use claim_task with kind 'check' to take ONE task.
2. Use get_task on its parent_id to read the writing.
3. Check it does what its title asks, is warm and short, and has no prices or
   claims that weren't given. Be fair: small style choices are fine.
4. If it's good: finish_task with a result starting 'APPROVED'.
5. If not: finish_task with a result starting 'SENT BACK:' and the reasons,
   then hand_off with to_kind 'write' and a note saying exactly what to fix.""",
    },
}


async def run_role(role):
    """Start one fresh agent for one job, and wait until it is done."""
    setup = ROLES[role]
    server = create_sdk_mcp_server(name="board", tools=setup["tools"])
    names = [f"mcp__board__{t.name}" for t in setup["tools"]]
    options = ClaudeAgentOptions(
        model=setup["model"],
        effort="medium",
        system_prompt=setup["prompt"],
        mcp_servers={"board": server},
        strict_mcp_config=True,  # only the board tools, not other MCP servers on this PC
        tools=[],
        allowed_tools=names,
        max_turns=10,
        max_budget_usd=0.50,
    )
    try:
        async for message in query(prompt="Do your job now.", options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        print(f"    {role} uses {block.name.replace('mcp__board__', '')}")
            elif isinstance(message, ResultMessage):
                spent["dollars"] += message.total_cost_usd or 0
    except ResultError as error:
        print(f"    {role} stopped early: {error.subtype}")


def next_job():
    """Look at the board and decide who works next. Plain code, no AI."""
    if board.count(status="todo") + board.count(status="doing") + board.count(status="done") == 0:
        return "planner"
    if board.count("check") > 0:
        return "checker"
    if board.count("write") > 0:
        return "writer"
    return None


def save_approved():
    """Write every approved piece of work into one file."""
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    lines = ["# Approved writing\n"]
    with board.connect() as db:
        checks = db.execute("SELECT * FROM tasks WHERE kind = 'check' AND status = 'done' "
                            "AND result LIKE 'APPROVED%'").fetchall()
    for check in checks:
        work = board.get_task(check["parent_id"])
        lines.append(f"## {work['title']}\n\n{work['result']}\n")
    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    return len(checks)


async def main():
    stuck = board.reset_stuck_tasks()
    if stuck:
        print(f"Found {stuck} unfinished task(s) from last time. Putting them back to 'todo'.")
    for step in range(1, MAX_STEPS + 1):
        role = next_job()
        if role is None:
            print("\nThe board is clear. Nothing left to do.")
            break
        print(f"\nStep {step}: the {role} works")
        await run_role(role)
        board.show()
    approved = save_approved()
    print(f"\n{approved} piece(s) approved, saved in {OUTPUT_FILE}")
    print(f"This run cost about ${spent['dollars']:.4f}")


try:
    asyncio.run(main())
except KeyboardInterrupt:
    print("\nStopped. The board is saved. Run the program again to carry on.")