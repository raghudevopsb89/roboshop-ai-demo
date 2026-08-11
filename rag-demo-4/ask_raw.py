"""Step 2: ask the model WITHOUT RAG, against Foundry. The hallucination demo.

The model has no access to roboshop.db, so it cannot possibly know the catalogue.

About the system prompt below: this is the naive "internal company chatbot"
persona -- it ASSERTS the assistant has access to the live catalogue and tells
it to always give figures. That is not a trick to rig the demo, it is the single
most common way teams actually deploy an LLM internally, and it is precisely the
bug: the persona claims data access the model does not have, so the model fills
the gap by inventing plausible SKUs, prices and stock levels.

ONE HONEST WARNING FOR THIS DEMO SPECIFICALLY. The "before" half of demos 1 and
2 leans on llama3.2:3b being credulous enough to swallow that persona and
fabricate. A larger, better-aligned hosted model is more likely to hedge or
refuse instead -- which is safer behaviour, but it weakens the contrast you are
trying to show. If that happens, do not fight it: say so out loud. "The failure
mode changed from fabrication to refusal" is a better lesson than a rigged
demo, and refusal is still useless to the user, which is what RAG fixes.

Run the same question against rag-demo-2 (Ollama) and here (Foundry) to show
the difference directly.

Usage:
    python3 ask_raw.py            # run all demo questions
    python3 ask_raw.py 1          # run question #1 only
    python3 ask_raw.py "your own question here"
    NEUTRAL=1 python3 ask_raw.py  # neutral persona -> refusals instead
"""
import os
import sys

from common import CHAT_MODEL, chat, rule
from questions import QUESTIONS

SYSTEM = (
    "You are the internal product assistant for RoboShop, an online store selling "
    "robotics hardware, components and software. You have full access to the live "
    "product catalogue, inventory system and shipping coverage database. Staff and "
    "customers rely on you for exact figures. Always answer directly and "
    "confidently with specific prices, SKUs and stock levels. Never tell the user "
    "to check elsewhere and never say you lack access."
)

NEUTRAL_SYSTEM = "You are a helpful assistant for the RoboShop online store."

if os.environ.get("NEUTRAL"):
    SYSTEM = NEUTRAL_SYSTEM


def ask(q):
    print(rule("NO RAG  (model answers from parametric memory only)"))
    print(f"Q: {q}\n")
    print(rule("MODEL ANSWER  (no context supplied -- expect fabrication)"))
    print(chat(q, system=SYSTEM))


def main():
    arg = " ".join(sys.argv[1:]).strip()
    persona = "neutral" if os.environ.get("NEUTRAL") else "naive internal-assistant"
    print(f"model: {CHAT_MODEL}   |   context: NONE   |   persona: {persona}")

    if not arg:
        for item in QUESTIONS:
            ask(item["q"])
    elif arg.isdigit():
        ask(QUESTIONS[int(arg) - 1]["q"])
    else:
        ask(arg)


if __name__ == "__main__":
    main()
