"""The money shot: run one question BOTH ways and print the answers together.

This is what to put on a screen. ask_raw.py and ask_rag.py each show one half,
so the contrast is split across two scrollbacks; here the fabricated answer and
the grounded one sit directly above and below each other.

Usage:
    python3 compare.py            # every demo question, both ways
    python3 compare.py 1          # question #1 only
    python3 compare.py "your own question here"
"""
import sys

from common import CHAT_MODEL, chat, rule
from questions import QUESTIONS

import ask_rag
import ask_raw


def compare(question):
    print(rule(f"Q: {question}"))

    print("\n### WITHOUT RAG -- no context, naive assistant persona\n")
    print(chat(question, system=ask_raw.SYSTEM))

    hits = ask_rag.retrieve(question)
    context = "\n".join(f"- {txt}" for _, _, _, _, txt in hits)
    prompt = f"CONTEXT:\n{context}\n\nQUESTION: {question}"

    print(f"\n### WITH RAG -- top-{len(hits)} facts retrieved from SQL\n")
    print(chat(prompt, system=ask_rag.SYSTEM))
    print()


def main():
    arg = " ".join(sys.argv[1:]).strip()
    print(f"model: {CHAT_MODEL}   |   comparing NO-RAG vs RAG on the same question")

    if not arg:
        for q in QUESTIONS:
            compare(q)
    elif arg.isdigit():
        compare(QUESTIONS[int(arg) - 1])
    else:
        compare(arg)


if __name__ == "__main__":
    main()
