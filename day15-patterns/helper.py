"""Day 15: one small helper that every pattern file uses.

ask() sends one message to Claude and returns the text answer.
It also adds up what each call costs, so show_cost() can print the total.
"""

import json

import anthropic

SMART = "claude-opus-5-5"   # the clever, careful model
FAST = "claude-haiku-5-5"   # the quick, cheap model

# dollars per million tokens: (input, output)
PRICES = {SMART: (4.00, 20.00), FAST: (0.10, 0.50)}

client = anthropic.Anthropic()
spent = {"dollars": 0.0, "calls": 0}


def ask(prompt, system="", model=SMART, answer_format=None):
    """Ask Claude one question. With answer_format, the answer comes back as a dict."""
    output_config = {"effort": "medium"}
    if answer_format:
        output_config["format"] = {"type": "json_schema", "schema": answer_format}
    extra = {}
    if model == SMART:  # Opus can switch to a backup model if it declines
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    response = client.beta.messages.create(
        model=model,
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config=output_config,
        **extra,
    )
    price_in, price_out = PRICES[model]
    spent["dollars"] += (response.usage.input_tokens * price_in
                         + response.usage.output_tokens * price_out) / 1_000_000
    spent["calls"] += 1
    text = "".join(block.text for block in response.content if block.type == "text")
    return json.loads(text) if answer_format else text


def show_cost():
    """Print how many calls we made and what they cost in total."""
    print(f"\n({spent['calls']} calls to Claude, about ${spent['dollars']:.4f})")