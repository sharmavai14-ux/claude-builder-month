import time

import anthropic
from dotenv import load_dotenv

load_dotenv()  # reads ANTHROPIC_API_KEY from the repo's .env file

MODEL = "claude-sonnet-5-5"
SYSTEM_PROMPT = "You are a friendly, knowledgeable assistant. Answer clearly in plain English."


def main():
    client = anthropic.Anthropic()
    history = []
    print("Streaming chat. Try asking for something long, like a short story. Type 'quit' to stop.\n")

    while True:
        question = input("You: ").strip()
        if question.lower() in {"quit", "exit", "q"}:
            break
        if not question:
            continue
        history.append({"role": "user", "content": question})

        print("\nClaude: ", end="", flush=True)
        started = time.time()
        first_word_at = None

        # .stream() instead of .create(): the answer arrives in small pieces as it is written.
        with client.messages.stream(
            model=MODEL,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            messages=history,
        ) as stream:
            for piece in stream.text_stream:
                if first_word_at is None:
                    first_word_at = time.time() - started
                print(piece, end="", flush=True)  # print each piece immediately, on the same line
            final = stream.get_final_message()  # the complete answer, once streaming ends

        total = time.time() - started
        history.append({"role": "assistant", "content": final.content})
        print(f"\n\n  [first words after {first_word_at or total:.1f}s, finished after {total:.1f}s,"
              f" {final.usage.output_tokens} output tokens]\n")


if __name__ == "__main__":
    main()