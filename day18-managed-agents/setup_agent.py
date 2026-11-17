"""Day 18, part 1: set up the Managed Agent. Run this ONCE.

It creates two things on Anthropic's side and saves their ids in ids.json:
  - an environment: the kind of computer (container) the agent works in
  - an agent: the model, its instructions and its tools
After that, run_report.py reuses them every time.
"""

import json
from pathlib import Path

import anthropic

HERE = Path(__file__).parent
IDS_FILE = HERE / "ids.json"
DAY11 = HERE.parent / "day11-report-agent"

if IDS_FILE.exists():
    print("Already set up. The ids are in ids.json. Run run_report.py instead.")
    raise SystemExit

# The same house rules and report skill you wrote on Day 11
house_rules = (DAY11 / "CLAUDE.md").read_text(encoding="utf-8")
skill = (DAY11 / ".claude" / "skills" / "house-report" / "SKILL.md").read_text(encoding="utf-8")

SYSTEM = f"""You write short reports from meeting notes for a small cafe.

Follow these house rules:
{house_rules}

Follow this report style:
{skill}

Where things are:
- The notes are in /mnt/session/uploads/. Read them first.
- Save the finished report as /mnt/session/outputs/report.md
Only use facts from the notes. Never make anything up."""

client = anthropic.Anthropic()

environment = client.beta.environments.create(
    name="day18-report-env",
    config={
        "type": "cloud",
        "networking": {"type": "limited"},  # no internet: the job doesn't need it
    },
)
print(f"Environment created: {environment.id}")

agent = client.beta.agents.create(
    name="Day 18 report writer",
    model={"id": "claude-opus-5-5", "effort": "medium"},
    system=SYSTEM,
    tools=[
        {
            "type": "agent_toolset_20260401",
            "default_config": {"enabled": True, "permission_policy": {"type": "auto"}},
            "configs": [
                {"name": "web_fetch", "enabled": False},
                {"name": "web_search", "enabled": False},
            ],
        },
    ],
)
print(f"Agent created: {agent.id} (version {agent.version})")

IDS_FILE.write_text(json.dumps({
    "environment_id": environment.id,
    "agent_id": agent.id,
    "agent_version": agent.version,
}, indent=2), encoding="utf-8")
print("Saved both ids in ids.json. Now run run_report.py.")