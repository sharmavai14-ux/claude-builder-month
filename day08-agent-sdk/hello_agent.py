"""Day 8: my first agent with the Claude Agent SDK.

It asks Claude one question and prints the answer and the cost.
No tools yet: this agent can only talk.
"""

import asyncio

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    query,
)

OPTIONS = ClaudeAgentOptions(
    model="claude-opus-5-5",
    effort="medium",
    tools=[],
    max_turns=1,
)


async def main():
    question = "In 3 short sentences, explain what an AI agent is to a 10-year-old."
    async for message in query(prompt=question, options=OPTIONS):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
        elif isinstance(message, ResultMessage):
            print(f"\nCost: about ${message.total_cost_usd or 0:.4f}")


asyncio.run(main())