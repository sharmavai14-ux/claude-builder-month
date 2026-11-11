"""Pattern 5: evaluator and optimizer. One writes, one marks, repeat until it passes.

Like a student and a teacher: write, get feedback, improve, hand it in again.
"""

from helper import ask, show_cost

TASK = "Write a slogan for Sunrise Cafe's new pumpkin spice latte."
RULES = """- 10 words or fewer
- mentions pumpkin
- no claims like 'best' or 'number one'
- sounds warm and cosy"""

MARKS = {
    "type": "object",
    "properties": {"passed": {"type": "boolean"}, "feedback": {"type": "string"}},
    "required": ["passed", "feedback"],
    "additionalProperties": False,
}

feedback = ""
for round_number in range(1, 4):  # at most 3 rounds, so it can't loop forever
    slogan = ask(f"{TASK}\nRules:\n{RULES}\n{feedback}\nReply with the slogan only.")
    marks = ask(f"Check this slogan against every rule. Be strict.\n"
                f"Rules:\n{RULES}\n\nSlogan: {slogan}", answer_format=MARKS)
    print(f"ROUND {round_number}: {slogan}")
    print(f"  {'PASS' if marks['passed'] else 'FAIL'}: {marks['feedback']}")
    if marks["passed"]:
        break
    feedback = (f"Your last try was: {slogan}\n"
                f"The checker said: {marks['feedback']}\nFix that.")

show_cost()