"""The money shot: run one question BOTH ways and print the answers together.

This is what to put on a screen. ask_raw.py and ask_rag.py each show one half,
which makes the contrast easy to miss -- especially since both of them end with
the same GROUND TRUTH line, which is read from SQL and never shown to the model.

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


def compare(question, truth=None):
    print(rule(f"Q: {question}"))

    print("\n### WITHOUT RAG -- no context, naive assistant persona\n")
    print(chat(question, system=ask_raw.SYSTEM))

    hits = ask_rag.retrieve(question)
    context = "\n".join(f"- {txt}" for _, _, _, _, txt in hits)
    prompt = f"CONTEXT:\n{context}\n\nQUESTION: {question}"

    print(f"\n### WITH RAG -- top-{len(hits)} facts retrieved from SQL\n")
    print(chat(prompt, system=ask_rag.SYSTEM))

    if truth:
        print("\n### GROUND TRUTH -- read from SQL, never shown to the model\n")
        print(truth)
    print()


def main():
    arg = " ".join(sys.argv[1:]).strip()
    print(f"model: {CHAT_MODEL}   |   comparing NO-RAG vs RAG on the same question")

    if not arg:
        for item in QUESTIONS:
            compare(item["q"], item["truth"])
    elif arg.isdigit():
        item = QUESTIONS[int(arg) - 1]
        compare(item["q"], item["truth"])
    else:
        compare(arg)


if __name__ == "__main__":
    main()
