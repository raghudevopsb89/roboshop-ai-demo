"""Step 4: answer the SAME questions, now with retrieval.

    question -> embed -> hybrid search over rag_index -> top-k facts
             -> stuffed into the prompt -> grounded answer

Two halves to the fix:

1. HYBRID RETRIEVAL. Pure cosine similarity is weak at exact-identifier lookup.
   Asked for "SKU ROB007" it ranked the right chunk 4th of 5, only 0.001 ahead of
   the chunk that fell off the list -- because "ROB007" carries almost no semantic
   signal, so the embedder ranks by generic product-ness instead. So we blend
   cosine with BM25, a classic keyword score that weights RARE terms heavily. A
   SKU appears in exactly one chunk out of 37, which is as rare as it gets, so
   BM25 pins it to rank 1. Still zero pip installs -- BM25 is ~25 lines.

   Set HYBRID_ALPHA=0 to fall back to pure vector search and demo the difference.

2. THE SYSTEM PROMPT. It forbids outside knowledge and gives the model an
   explicit escape hatch, so "not in the data" is a legal answer. Without that, a
   model handed weak context will still paper over the gap.

Usage:
    python3 ask_rag.py                  # all demo questions
    python3 ask_rag.py 1                # question #1 only
    python3 ask_rag.py "your question"
    python3 ask_rag.py --show 1         # print the retrieved chunks in full
    TOP_K=8 python3 ask_rag.py 1        # widen retrieval
    HYBRID_ALPHA=0 python3 ask_rag.py 1 # pure vector search (no BM25)
"""
import json
import math
import os
import re
import sqlite3
import sys

from common import CHAT_MODEL, DB_PATH, chat, cosine, embed, rule
from questions import QUESTIONS

TOP_K = int(os.environ.get("TOP_K", "5"))
# 0.0 = pure cosine, 1.0 = pure BM25. 0.4 is enough to win exact-ID lookups
# without letting keyword overlap drown out semantic matches.
HYBRID_ALPHA = float(os.environ.get("HYBRID_ALPHA", "0.4"))

SYSTEM = """You are the product assistant for the RoboShop online store.

Answer ONLY using the facts in the CONTEXT block below. These facts come from
RoboShop's catalogue and shipping databases and are authoritative.

Rules:
- Never use outside knowledge and never guess.
- If the context does not contain the answer, reply exactly:
  "That information is not in the RoboShop database."
- Quote prices, SKUs, stock levels and regions exactly as they appear.
- Be concise."""

_WORD = re.compile(r"[a-z0-9]+")


def tokens(text):
    """Lowercase alphanumeric tokens. Keeps 'ROB007' intact as 'rob007'."""
    return _WORD.findall(text.lower())


def bm25_scores(query, docs, k1=1.5, b=0.75):
    """Textbook BM25 over a tiny in-memory corpus. docs is a list of token lists."""
    n = len(docs)
    lengths = [len(d) for d in docs]
    avgdl = sum(lengths) / n if n else 0.0

    df = {}
    for d in docs:
        for term in set(d):
            df[term] = df.get(term, 0) + 1

    scores = []
    qterms = tokens(query)
    for d, dl in zip(docs, lengths):
        freq = {}
        for term in d:
            freq[term] = freq.get(term, 0) + 1
        s = 0.0
        for term in qterms:
            f = freq.get(term, 0)
            if not f:
                continue
            # Rare terms (a SKU, a city name) dominate; "the" contributes ~nothing.
            idf = math.log(1 + (n - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
            s += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
        scores.append(s)
    return scores


def _minmax(values):
    """Scale to [0,1]. Order-preserving. Used on BM25 only -- see retrieve()."""
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [0.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def retrieve(question, k=TOP_K, alpha=HYBRID_ALPHA):
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
    cos = [cosine(qvec, json.loads(v)) for _, _, v in rows]
    bm = bm25_scores(question, [tokens(txt) for _, txt, _ in rows])

    # BM25 is unbounded, so it gets min-max scaled into [0,1]. Cosine is used
    # RAW and deliberately NOT scaled: nomic cosines sit in a narrow absolute
    # band (0.81-0.86 for the ROB007 question), and min-max scaling stretches
    # that meaningless 0.04 spread across the full 0-1 range -- manufacturing
    # confidence the embedder never had, and drowning out BM25. Leaving cosine
    # raw lets a genuine rare-term hit outrank a marginal semantic one.
    bm_n = _minmax(bm)
    blended = [(1 - alpha) * c + alpha * b for c, b in zip(cos, bm_n)]

    scored = [
        (blended[i], cos[i], bm[i], rows[i][0], rows[i][1])
        for i in range(len(rows))
    ]
    scored.sort(reverse=True, key=lambda x: x[0])
    return scored[:k]


def ask(question, truth=None, show=False):
    hits = retrieve(question)
    context = "\n".join(f"- {txt}" for _, _, _, _, txt in hits)

    print(rule("WITH RAG  (answer grounded in RoboShop SQL data)"))
    print(f"Q: {question}\n")

    mode = "cosine only" if HYBRID_ALPHA == 0 else f"cosine+BM25, alpha={HYBRID_ALPHA}"
    print(f"retrieved top-{len(hits)} facts  [{mode}]:")
    for score, cos, bm, src, txt in hits:
        preview = txt if show else (txt[:80] + "..." if len(txt) > 80 else txt)
        print(f"  [{score:.3f}  cos={cos:.3f} bm25={bm:5.2f}] ({src}) {preview}")

    prompt = f"CONTEXT:\n{context}\n\nQUESTION: {question}"
    print(rule("MODEL ANSWER  (grounded in the retrieved context above)"))
    print(chat(prompt, system=SYSTEM))
    if truth:
        print(rule("GROUND TRUTH  (read from SQL -- never shown to the model)"))
        print(truth)


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
