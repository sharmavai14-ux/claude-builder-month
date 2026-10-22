import contextlib
import io

import anthropic

from research import run_research

NOT_FOUND_WORDS = ["could not find", "couldn't find", "unable to find",
                   "no reliable", "no information", "no record",
                   "does not appear", "doesn't appear", "not aware of"]

TESTS = [
    {"question": "What is the capital city of Australia?", "look_for": ["Canberra"]},
    {"question": "Who wrote the novel Nineteen Eighty-Four?", "look_for": ["Orwell"]},
    {"question": "In which year did India become independent?", "look_for": ["1947"]},
    {"question": "Which is the largest planet in our solar system?", "look_for": ["Jupiter"]},
    {"question": "What does HTTP stand for?", "look_for": ["Hypertext Transfer Protocol"]},
    {"question": "What is the currency of Japan called?", "look_for": ["yen"]},
    {"question": "What is the official website of the Python programming language?", "look_for": ["python.org"]},
    {"question": "Which company makes the Claude AI models?", "look_for": ["Anthropic"]},
    {"question": "What is the tallest mountain in the world above sea level?", "look_for": ["Everest"]},
    {"question": "What is the population of the town of Xyzabad in Zorvania?",
     "look_for": NOT_FOUND_WORDS, "min_sources": 0},
]


def check_report(test, result):
    """Check one report. Return a list of problems (empty list = passed)."""
    text = result["report_text"]
    problems = []
    if "## Short answer" not in text:
        problems.append('no "## Short answer" section')
    if "## Details" not in text:
        problems.append('no "## Details" section')
    if len(result["sources"]) < test.get("min_sources", 1):
        problems.append("no sources")
    if not any(word.lower() in text.lower() for word in test["look_for"]):
        problems.append(f"didn't mention any of: {', '.join(test['look_for'][:3])}")
    return problems


def main():
    client = anthropic.Anthropic()
    passed = 0
    total_cost = 0.0
    for number, test in enumerate(TESTS, start=1):
        print(f"Test {number}/{len(TESTS)}: {test['question']}")
        with contextlib.redirect_stdout(io.StringIO()):
            result = run_research(client, test["question"], keep_note=False)
        total_cost += result["cost"]
        problems = check_report(test, result)
        if problems:
            print(f"  FAIL: {'; '.join(problems)}")
        else:
            passed += 1
            print("  PASS")
    print(f"\nScore: {passed} out of {len(TESTS)} passed")
    print(f"Total cost of this test run: about ${total_cost:.2f}")


if __name__ == "__main__":
    main()