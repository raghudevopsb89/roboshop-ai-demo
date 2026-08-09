"""Step 2: ask the model WITHOUT RAG. This is the hallucination demo.

The model has no access to company.db, so it cannot possibly know the answers.

About the system prompt below: this is the naive "internal company chatbot"
persona -- it ASSERTS the assistant has access to internal systems and tells it
to always give figures. That is not a trick to rig the demo, it is the single
most common way teams actually deploy an LLM internally, and it is precisely the
bug: the persona claims data access that the model does not have, so the model
fills the gap by inventing plausible names, IDs and numbers.

(With a plain neutral persona this model mostly refuses instead -- worth showing
too, via: NEUTRAL=1 python3 ask_raw.py 1. Refusal is safer, but it is still
useless to the user, and RAG is what turns both refusal and fabrication into a
correct answer.)

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
    "You are the internal analytics assistant for Nimbus Retail Analytics Pvt Ltd. "
    "You have full access to the company's internal SQL data warehouse, HR records "
    "and finance systems. Employees rely on you for exact figures. Always answer "
    "directly and confidently with specific numbers, names and IDs. Never tell the "
    "user to check elsewhere and never say you lack access."
)

NEUTRAL_SYSTEM = (
    "You are a helpful business analyst assistant for Nimbus Retail Analytics."
)

if os.environ.get("NEUTRAL"):
    SYSTEM = NEUTRAL_SYSTEM


def ask(q, truth=None):
    print(rule("NO RAG  (model answers from parametric memory only)"))
    print(f"Q: {q}\n")
    print(f"A: {chat(q, system=SYSTEM)}\n")
    if truth:
        print(f"GROUND TRUTH (from SQL): {truth}")


def main():
    arg = " ".join(sys.argv[1:]).strip()
    persona = "neutral" if os.environ.get("NEUTRAL") else "naive internal-assistant"
    print(f"model: {CHAT_MODEL}   |   context: NONE   |   persona: {persona}")

    if not arg:
        for item in QUESTIONS:
            ask(item["q"], item["truth"])
    elif arg.isdigit():
        item = QUESTIONS[int(arg) - 1]
        ask(item["q"], item["truth"])
    else:
        ask(arg)


if __name__ == "__main__":
    main()
