"""Step 4: answer the SAME questions, now with retrieval.

    question -> embed -> cosine search over rag_index -> top-k facts
             -> stuffed into the prompt -> grounded answer

The system prompt is the other half of the fix: it forbids outside knowledge and
gives the model an explicit escape hatch, so "not in the data" is a legal answer.
Without that, a model handed weak context will still paper over the gap.

Usage:
    python3 ask_rag.py            # all demo questions
    python3 ask_rag.py 1          # question #1 only
    python3 ask_rag.py "your own question here"
    python3 ask_rag.py --show 1   # also print the retrieved chunks in full
    TOP_K=8 python3 ask_rag.py 1  # widen retrieval
"""
import json
import os
import sqlite3
import sys

from common import CHAT_MODEL, DB_PATH, chat, cosine, embed, rule
from questions import QUESTIONS

TOP_K = int(os.environ.get("TOP_K", "5"))

SYSTEM = """You are the product assistant for the RoboShop online store.

Answer ONLY using the facts in the CONTEXT block below. These facts come from
RoboShop's catalogue and shipping databases and are authoritative.

Rules:
- Never use outside knowledge and never guess.
- If the context does not contain the answer, reply exactly:
  "That information is not in the RoboShop database."
- Quote prices, SKUs, stock levels and regions exactly as they appear.
- Be concise."""


def retrieve(question, k=TOP_K):
    if not os.path.exists(DB_PATH):
        sys.exit(f"{DB_PATH} not found -- run: python3 setup_db.py")
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("SELECT source, text, vector FROM rag_index").fetchall()
    except sqlite3.OperationalError:
        sys.exit("rag_index table missing -- run: python3 build_index.py")
    finally:
        conn.close()
    if not rows:
        sys.exit("rag_index is empty -- run: python3 build_index.py")

    qvec = embed([question])[0]
    scored = [(cosine(qvec, json.loads(v)), src, txt) for src, txt, v in rows]
    scored.sort(reverse=True, key=lambda x: x[0])
    return scored[:k]


def ask(question, truth=None, show=False):
    hits = retrieve(question)
    context = "\n".join(f"- {txt}" for _, _, txt in hits)

    print(rule("WITH RAG  (answer grounded in RoboShop SQL data)"))
    print(f"Q: {question}\n")

    print(f"retrieved top-{len(hits)} facts:")
    for score, src, txt in hits:
        preview = txt if show else (txt[:95] + "..." if len(txt) > 95 else txt)
        print(f"  [{score:.3f}] ({src}) {preview}")

    prompt = f"CONTEXT:\n{context}\n\nQUESTION: {question}"
    print(f"\nA: {chat(prompt, system=SYSTEM)}\n")
    if truth:
        print(f"GROUND TRUTH (from SQL): {truth}")


def main():
    args = sys.argv[1:]
    show = "--show" in args
    args = [a for a in args if a != "--show"]
    arg = " ".join(args).strip()

    print(f"model: {CHAT_MODEL}   |   context supplied: top-{TOP_K} SQL facts")

    if not arg:
        for item in QUESTIONS:
            ask(item["q"], item["truth"], show)
    elif arg.isdigit():
        item = QUESTIONS[int(arg) - 1]
        ask(item["q"], item["truth"], show)
    else:
        ask(arg, show=show)


if __name__ == "__main__":
    main()
