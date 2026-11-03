"""Day 14: test how well Claude writes replies, before you trust it with real email.

For every email in the "reply-cases" folder it:
1. asks Claude to write a reply, using your house rules and reply-style Skill
2. checks the reply with simple code checks (free and exact)
3. asks a second Claude, the judge, to check the things code can't
Files whose name starts with "skip-" are emails that must NOT get a reply.
It prints a score and adds one line to reply-history.csv.
"""

import csv
import json
import time
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()  # reads ANTHROPIC_API_KEY from the repo's .env file

HERE = Path(__file__).parent
HOUSE_RULES = (HERE / "CLAUDE.md").read_text(encoding="utf-8")
STYLE = (HERE / ".claude" / "skills" / "reply-style" / "SKILL.md").read_text(encoding="utf-8")
CASES_FOLDER = HERE / "reply-cases"
RESULTS_FOLDER = HERE / "reply-results"
HISTORY_FILE = HERE / "reply-history.csv"

MODEL = "claude-opus-5-5"
PRICE_IN = 4.00 / 1_000_000    # dollars per input token
PRICE_OUT = 20.00 / 1_000_000  # dollars per output token

NO_REPLY = "NO REPLY"
NEVER_IN_A_REPLY = ["password", "bank", "sort code", "phone number"]

JUDGE_QUESTIONS = {
    "type": "object",
    "properties": {
        "answers_what_they_asked": {"type": "boolean"},
        "no_invented_facts": {"type": "boolean"},
        "friendly_and_polite": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["answers_what_they_asked", "no_invented_facts",
                 "friendly_and_polite", "reason"],
    "additionalProperties": False,
}

client = anthropic.Anthropic()
spent = {"input": 0, "output": 0}


def ask_claude(system, question, answer_format=None):
    """Send one message to Claude and return its text answer."""
    output_config = {"effort": "medium"}
    if answer_format:
        output_config["format"] = {"type": "json_schema", "schema": answer_format}
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": question}],
        output_config=output_config,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    spent["input"] += response.usage.input_tokens
    spent["output"] += response.usage.output_tokens
    return "".join(block.text for block in response.content if block.type == "text")


def write_reply(email):
    """Step 1: Claude writes a reply, following your house rules and reply style."""
    system = HOUSE_RULES + "\n\n" + STYLE
    question = ("Write a reply to this email. Answer with the reply text only.\n"
                f"If this email should not get a reply, answer only: {NO_REPLY}\n\n"
                f"<email>\n{email}\n</email>")
    return ask_claude(system, question).strip()


def code_checks(reply):
    """Step 2: checks that code can do exactly. Returns a list of problems."""
    problems = []
    lines = reply.splitlines()
    if not lines or not lines[0].startswith("Hi "):
        problems.append('does not start with "Hi <name>,"')
    if not lines or lines[-1].strip() != "Vaibhav":
        problems.append('does not end with "Vaibhav"')
    words = len(reply.split())
    if words > 120:
        problems.append(f"too long: {words} words (limit 120)")
    for word in NEVER_IN_A_REPLY:
        if word in reply.lower():
            problems.append(f'mentions "{word}"')
    return problems


def judge(email, reply):
    """Step 3: a second Claude checks what code can't. Returns a list of problems."""
    system = "You are a strict, fair checker of email replies. Answer every question honestly."
    question = f"""Here is an email, and a reply written for Vaibhav.

<email>
{email}
</email>

<reply>
{reply}
</reply>

Answer these questions about the reply:
- answers_what_they_asked: does the reply deal with what the sender asked?
  A gap like "[CHECK: ...]" counts as dealing with it.
- no_invented_facts: is every date, time, amount, decision and promise in the reply
  either in the email or left as a "[CHECK: ...]" gap?
- friendly_and_polite: is the reply friendly and polite?
- reason: one short sentence explaining any "false" answer, or "All good"."""
    answer = json.loads(ask_claude(system, question, JUDGE_QUESTIONS))
    problems = [name for name, ok in answer.items() if ok is False]
    return problems, answer["reason"]


def main():
    RESULTS_FOLDER.mkdir(exist_ok=True)
    start = time.time()
    passed = 0
    cases = sorted(CASES_FOLDER.glob("*.txt"))
    if not cases:
        print(f"No practice emails found. Put some .txt files in the {CASES_FOLDER.name} folder.")
        return
    for case in cases:
        email = case.read_text(encoding="utf-8")
        reply = write_reply(email)
        (RESULTS_FOLDER / f"{case.stem}.txt").write_text(reply, encoding="utf-8")
        reason = ""
        if case.stem.startswith("skip-"):
            problems = [] if reply == NO_REPLY else ["wrote a reply to an email that must not get one"]
        elif reply == NO_REPLY:
            problems = ["said NO REPLY to an email that needs a reply"]
        else:
            problems = code_checks(reply)
            judge_problems, reason = judge(email, reply)
            problems += judge_problems
        if problems:
            print(f"FAIL  {case.name}")
            for problem in problems:
                print(f"      - {problem}")
            if reason:
                print(f"      Judge says: {reason}")
        else:
            passed += 1
            print(f"PASS  {case.name}")

    seconds = time.time() - start
    cost = spent["input"] * PRICE_IN + spent["output"] * PRICE_OUT
    rate = passed / len(cases) * 100
    print(f"\nScore: {passed} out of {len(cases)} passed ({rate:.0f}%)")
    print(f"Time: {seconds:.0f} seconds   Cost: about ${cost:.4f}")

    new_file = not HISTORY_FILE.exists()
    with HISTORY_FILE.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if new_file:
            writer.writerow(["when", "passed", "cases", "pass_rate", "cost_usd", "seconds"])
        writer.writerow([f"{datetime.now():%Y-%m-%d %H:%M}", passed, len(cases),
                         f"{rate:.0f}%", f"{cost:.4f}", f"{seconds:.0f}"])
    print(f"Saved to {HISTORY_FILE.name}. Replies are in the {RESULTS_FOLDER.name} folder.")


main()