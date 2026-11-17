"""Day 18, part 2: run the report agent on Anthropic's computers.

Each run is one session: Anthropic starts a fresh container, our notes are
copied in, the agent writes report.md, and we download it.
"""

import json
import sys
import time
from pathlib import Path

import anthropic

HERE = Path(__file__).parent
IDS = json.loads((HERE / "ids.json").read_text(encoding="utf-8"))
NOTES_FILE = HERE / "notes" / (sys.argv[1] if len(sys.argv) > 1 else "cafe-meeting.txt")
OUTPUT_DIR = HERE / "output"
BUDGET_CENTS = "50"  # stop the session if it ever costs more than 50 cents

client = anthropic.Anthropic()

# 1. Upload the notes, so the agent's container can see them
with open(NOTES_FILE, "rb") as f:
    uploaded = client.beta.files.upload(file=(NOTES_FILE.name, f, "text/plain"))
print(f"Uploaded {NOTES_FILE.name}")

# 2. Start a session: a fresh container with our agent and our notes in it
session = client.beta.sessions.create(
    agent={"type": "agent", "id": IDS["agent_id"], "version": IDS["agent_version"]},
    environment_id=IDS["environment_id"],
    title=f"Report for {NOTES_FILE.name}",
    resources=[{"type": "file", "file_id": uploaded.id, "mount_path": "/notes.txt"}],
    budget={"type": "limit", "max_list_cost": {"amount": BUDGET_CENTS, "currency": "USD"}},
)
print(f"Session started: {session.id}")
print(f"Watch it live: https://platform.claude.com/workspaces/default/sessions/{session.id}\n")

# 3. Open the stream first, then give the agent its job
with client.beta.sessions.events.stream(session.id) as stream:
    client.beta.sessions.events.send(
        session.id,
        events=[{"type": "user.message", "content": [{"type": "text",
                 "text": "Write the report for the notes in /mnt/session/uploads/notes.txt"}]}],
    )
    for event in stream:
        if event.type == "agent.message":
            for block in event.content:
                if block.type == "text":
                    print(block.text)
        elif event.type == "agent.tool_use":
            print(f"    agent uses {event.name}")
            if event.evaluated_permission == "ask":
                answer = input(f"    Allow {event.name} {json.dumps(event.input)[:80]}? (y/n) ")
                client.beta.sessions.events.send(session.id, events=[{
                    "type": "user.tool_confirmation",
                    "tool_use_id": event.id,
                    "result": "allow" if answer.strip().lower() == "y" else "deny",
                }])
        elif event.type == "session.error":
            print(f"    error: {event.error.message}")
        elif event.type == "session.status_idle":
            if event.stop_reason.type == "requires_action":
                continue  # waiting for our y/n answer
            if event.stop_reason.type == "budget_reached":
                print("    The session reached its budget and paused.")
            break
        elif event.type == "session.status_terminated":
            break

# 4. Download what the agent saved in /mnt/session/outputs/
OUTPUT_DIR.mkdir(exist_ok=True)
for attempt in range(5):
    files = client.beta.files.list(scope_id=session.id, betas=["managed-agents-2026-04-01"]).data
    if files:
        break
    time.sleep(2)  # the files can take a few seconds to appear
for f in files:
    client.beta.files.download(f.id).write_to_file(OUTPUT_DIR / Path(f.filename).name)
    print(f"\nDownloaded {f.filename} into the output folder")
if not files:
    print("\nNo files came back. Open the 'Watch it live' link to see what happened.")

# 5. What did it cost?
usage = client.beta.sessions.retrieve(session.id).usage
seconds = usage.active_seconds or 0
print(f"\nTokens: {usage.input_tokens} in, {usage.output_tokens} out, "
      f"{usage.cache_read_input_tokens} read from cache")
print(f"Time the agent was working: {seconds:.0f} seconds "
      f"(about ${seconds / 3600 * 0.08:.4f} of running time)")
if usage.list_cost:
    print(f"Total list cost: ${int(usage.list_cost.amount) / 100:.2f}")