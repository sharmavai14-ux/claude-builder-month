"""Day 12: test your report agent's style with code checks and a Claude judge.

For every notes file in the "cases" folder it:
1. asks Claude to write a report, using your Day 11 house rules and Skill
2. checks the report with simple code checks (free and exact)
3. asks a second Claude, the judge, to check the things code can't
Then it prints a score, and adds one line to history.csv so you can
compare runs over time.
"""

import csv
import json
import time
from datetime import datetime
from pathlib import Path

import anthropic

HERE = Path(__file__).parent
DAY11 = HERE.parent / "day11-report-agent"
HOUSE_RULES = (DAY11 / "CLAUDE.md").read_text(encoding="utf-8")
RECIPE = (DAY11 / ".claude" / "skills" / "house-report" / "SKILL.md").read_text(encoding="utf-8")
CASES_FOLDER = HERE / "cases"
RESULTS_FOLDER = HERE / "results"
HISTORY_FILE = HERE / "history.csv"

MODEL = "claude-opus-5-5"
PRICE_IN = 4.00 / 1_000_000    # dollars per input token
PRICE_OUT = 20.00 / 1_000_000  # dollars per output token

HEADINGS = ["# Report:", "## In one line", "## What happened",
            "## What's next", "## Open questions"]

JUDGE_QUESTIONS = {
    "type": "object",
    "properties": {
        "only_facts_from_notes": {"type": "boolean"},
        "next_steps_say_who_and_when": {"type": "boolean"},
        "most_important_thing_first": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["only_facts_from_notes", "next_steps_say_who_and_when",
                 "most_important_thing_first", "reason"],
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


def write_report(notes):
    """Step 1: the 'agent' writes a report, following your house rules and recipe."""
    system = HOUSE_RULES + "\n\n" + RECIPE
    question = f"Write a report from these notes. Reply with the report only.\n\n{notes}"
    return ask_claude(system, question)


def code_checks(report):
    """Step 2: checks that code can do exactly. Returns a list of problems."""
    problems = []
    place = 0
    for heading in HEADINGS:
        found = report.find(heading, place)
        if found == -1:
            problems.append(f"missing or out of order: {heading}")
        else:
            place = found
    words = len(report.split())
    if words > 200:
        problems.append(f"too long: {words} words (limit 200)")
    last_line = report.strip().splitlines()[-1] if report.strip() else ""
    if not last_line.startswith("_Written by"):
        problems.append("last line is not the italic 'Written by' line")
    return problems


def judge(notes, report):
    """Step 3: a second Claude checks what code can't. Returns a list of problems."""
    system = "You are a strict, fair checker of short reports. Answer every question honestly."
    question = f"""Here are some notes, and a report written from them.

<notes>
{notes}
</notes>

<report>
{report}
</report>

Answer these questions about the report:
- only_facts_from_notes: does every name, date and fact in the report come from the notes?
- next_steps_say_who_and_when: does every point under "What's next" say who and by when,
  or clearly say "not decided" when the notes don't say?
- most_important_thing_first: does "In one line" give the most important point of the notes?
- reason: one short sentence explaining any "false" answer, or "All good"."""
    answer = json.loads(ask_claude(system, question, JUDGE_QUESTIONS))
    problems = [name for name, ok in answer.items() if ok is False]
    return problems, answer["reason"]


def main():
    RESULTS_FOLDER.mkdir(exist_ok=True)
    start = time.time()
    passed = 0
    cases = sorted(CASES_FOLDER.glob("*.txt"))
    for case in cases:
        notes = case.read_text(encoding="utf-8")
        report = write_report(notes)
        (RESULTS_FOLDER / f"{case.stem}.md").write_text(report, encoding="utf-8")
        problems = code_checks(report)
        judge_problems, reason = judge(notes, report)
        problems += judge_problems
        if problems:
            print(f"FAIL  {case.name}")
            for problem in problems:
                print(f"      - {problem}")
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
    print(f"Saved to {HISTORY_FILE.name}. Reports are in the {RESULTS_FOLDER.name} folder.")


main()