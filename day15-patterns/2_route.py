"""Pattern 2: routing. Sort each message first, then send it to the right expert.

Like a receptionist who asks "what is it about?" and sends you to the right desk.
"""

from helper import FAST, SMART, ask, show_cost

MESSAGES = [
    "My latte was cold this morning and the staff were rude.",
    "Do you have any dairy-free milk?",
    "Can I book a table for 6 people on Saturday at 11am?",
]

SORTER = {
    "type": "object",
    "properties": {"kind": {"type": "string", "enum": ["complaint", "question", "booking"]}},
    "required": ["kind"],
    "additionalProperties": False,
}

EXPERTS = {
    "complaint": (SMART, "You handle complaints for Sunrise Cafe. Say sorry, show you "
                         "understand, and offer a free drink. Under 50 words."),
    "question": (FAST, "You answer questions for Sunrise Cafe. Be short and friendly. "
                       "We have oat, soy and almond milk. Under 30 words."),
    "booking": (FAST, "You take bookings for Sunrise Cafe. Repeat the day, time and "
                      "number of people, and say a person will confirm. Under 40 words."),
}

for message in MESSAGES:
    kind = ask(f"What kind of message is this?\n\n{message}", model=FAST,
               answer_format=SORTER)["kind"]
    model, instructions = EXPERTS[kind]
    answer = ask(message, system=instructions, model=model)
    print(f"\nMESSAGE: {message}\nSORTED AS: {kind} (answered by {model})\nREPLY: {answer}")

show_cost()