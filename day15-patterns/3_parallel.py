"""Pattern 3: parallelization. Several checks at the same time, then put the results together.

Like three friends each proofreading a different thing in your letter, all at once.
"""

import time
from concurrent.futures import ThreadPoolExecutor

from helper import FAST, ask, show_cost

AD = """Sunrise Cafe has the best coffee in the whole city!!
Our new pumpkin latte is made fresh evry morning.
Come in before 9am and your second cup is free."""

CHECKS = {
    "spelling": "List any spelling or grammar mistakes. If there are none, say 'None'.",
    "tone": "Is this friendly and welcoming? Answer in one sentence.",
    "claims": "List any claims we might not be able to prove, like 'the best'. "
              "If there are none, say 'None'.",
}


def run_check(name):
    """One checker: looks at the ad for one thing only."""
    return name, ask(f"{CHECKS[name]}\n\n<ad>\n{AD}\n</ad>", model=FAST)


start = time.time()
with ThreadPoolExecutor() as helpers:
    results = list(helpers.map(run_check, CHECKS))
print(f"All {len(results)} checks finished in {time.time() - start:.1f} seconds.\n")

for name, answer in results:
    print(f"{name.upper()}:\n{answer}\n")

show_cost()