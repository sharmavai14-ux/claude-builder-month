"""Pattern 1: prompt chaining. Small steps in a row, with a check in between.

Like an assembly line: each worker does one simple job and hands it on.
"""

from helper import ask, show_cost

NOTES = """Sunrise Cafe, autumn menu, starts Monday 9 November.
New: pumpkin spice latte, apple cinnamon muffin, hot chai with oat milk.
Open 7am to 6pm. 10% off for students all of November."""

# Step 1: pull out the facts
facts = ask(f"From these notes, list exactly 3 key facts, one per line, "
            f"each starting with '- '. Facts only.\n\n{NOTES}")
print("STEP 1, the facts:\n" + facts)

# The gate: plain code checks step 1 before we go on
lines = [line for line in facts.splitlines() if line.startswith("- ")]
if len(lines) != 3:
    print(f"\nStopped: expected 3 facts, got {len(lines)}.")
    raise SystemExit

# Step 2: write the post, using only the checked facts
post = ask(f"Write a friendly Instagram post (under 60 words) for Sunrise Cafe "
           f"using only these facts:\n{facts}")
print("\nSTEP 2, the post:\n" + post)

# Step 3: make a short text-message version of the post
sms = ask(f"Shorten this into one text message under 25 words:\n{post}")
print("\nSTEP 3, the text message:\n" + sms)

show_cost()