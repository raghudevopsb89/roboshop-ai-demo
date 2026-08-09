"""Step 5: the demo. Same question, same model, twice -- without and with RAG.

Usage:
    python3 05_compare.py            # all demo questions
    python3 05_compare.py 1          # question #1 only
    python3 05_compare.py "your own question here"
"""
import sys
import textwrap

from common import CHAT_MODEL, EMBED_MODEL, chat, rule
import importlib

raw = importlib.import_module("02_ask_raw")
rag = importlib.import_module("04_ask_rag")
from questions import QUESTIONS


def wrap(text, indent="    "):
    out = []
    for para in text.split("\n"):
        out.append(textwrap.fill(para, 74, initial_indent=indent,
                                 subsequent_indent=indent) if para.strip() else "")
    return "\n".join(out)


def compare(q, truth=None):
    print(rule())
    print(f"QUESTION: {q}")
    print("=" * 78)

    print("\n[1] WITHOUT RAG  -- no access to the database\n")
    print(wrap(chat(q, system=raw.SYSTEM)))

    hits = rag.retrieve(q)
    context = "\n".join(f"- {t}" for _, _, t in hits)
    print(f"\n[2] WITH RAG  -- top-{len(hits)} facts retrieved from SQL\n")
    for score, src, txt in hits[:3]:
        print(f"    [{score:.3f}] ({src}) {txt[:80]}...")
    print()
    print(wrap(chat(f"CONTEXT:\n{context}\n\nQUESTION: {q}", system=rag.SYSTEM)))

    if truth:
        print(f"\n[3] GROUND TRUTH (straight from SQL)\n")
        print(wrap(truth))


def main():
    arg = " ".join(sys.argv[1:]).strip()
    print(f"chat model: {CHAT_MODEL}   embedding model: {EMBED_MODEL}")

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
