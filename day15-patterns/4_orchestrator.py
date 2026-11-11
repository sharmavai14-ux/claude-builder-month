"""Pattern 4: orchestrator and workers. A planner splits the job, workers do the parts.

Like a head chef who decides the dishes, gives one to each cook, then plates the meal.
"""

from concurrent.futures import ThreadPoolExecutor

from helper import FAST, SMART, ask, show_cost

GOAL = "Write the 'About us' page for Sunrise Cafe's new website."
FACTS = """Opened in 2019 by two friends, Asha and Leo. Small cafe, 20 seats.
Coffee beans from one farm in Karnataka. Everything baked in-house each morning.
Free wifi. Dogs welcome. Open 7am to 6pm, every day."""

SECTION = {"type": "object",
           "properties": {"title": {"type": "string"}, "instructions": {"type": "string"}},
           "required": ["title", "instructions"], "additionalProperties": False}
PLAN = {"type": "object",
        "properties": {"sections": {"type": "array", "items": SECTION}},
        "required": ["sections"], "additionalProperties": False}

# 1. The orchestrator (smart model) plans the sections
plan = ask(f"Goal: {GOAL}\nFacts:\n{FACTS}\n\nSplit this into 3 or 4 short sections. "
           f"For each, give a title and clear instructions for a writer.",
           model=SMART, answer_format=PLAN)["sections"]
print("THE PLAN:")
for section in plan:
    print(f"- {section['title']}")


# 2. Workers (fast model) write one section each, all at the same time
def write_section(section):
    return ask(f"Write the section '{section['title']}' (under 60 words).\n"
               f"Instructions: {section['instructions']}\nUse only these facts:\n{FACTS}",
               model=FAST)


with ThreadPoolExecutor() as workers:
    parts = list(workers.map(write_section, plan))

# 3. The orchestrator puts the parts together into one page
pieces = "\n\n".join(f"## {s['title']}\n{p}" for s, p in zip(plan, parts))
page = ask(f"Join these sections into one smooth 'About us' page. Keep the facts. "
           f"Fix any repeats.\n\n{pieces}", model=SMART)
print("\nTHE FINISHED PAGE:\n" + page)

show_cost()