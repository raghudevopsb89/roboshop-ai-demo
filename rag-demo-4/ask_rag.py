"""Step 4: answer the demo questions with retrieval, against Foundry.

    question -> embed -> hybrid search over rag_index -> top-k facts
             -> stuffed into the prompt -> grounded answer

Structurally identical to rag-demo-2/ask_rag.py. The retrieval maths is
unchanged; only the models moved. What DID have to change is the blend weight,
and that is the lesson of this demo:

    rag-demo-2, nomic-embed-text:     HYBRID_ALPHA = 0.4
    rag-demo-4, text-embedding-3-*:   HYBRID_ALPHA = see below

The reasoning behind blending BM25 with cosine still holds -- pure vector
search is weak at exact-identifier lookup, because a SKU like "ROB007" carries
almost no semantic signal and the embedder ranks by generic product-ness
instead. But the CONSTANT does not transfer. nomic's cosines sat in a narrow
0.81-0.86 band, so raw cosine contributed a large near-constant term to the
blend. Azure's embeddings are L2-normalised with a much wider, lower spread,
so the same alpha weights the two signals completely differently.

Do not inherit a tuned constant across an embedder change. Measure it:

    python3 tune_alpha.py

Set HYBRID_ALPHA=0 to fall back to pure vector search and show the difference.

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

# Measured against text-embedding-3-small with tune_alpha.py, NOT inherited
# from rag-demo-2. Re-run tune_alpha.py if you change EMBED_MODEL.
HYBRID_ALPHA = float(os.environ.get("HYBRID_ALPHA", "0.35"))

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


def load_rows():
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
    return rows


def score_all(question, rows, alpha):
    """Blended scores for every row, in row order. Shared with tune_alpha.py."""
    qvec = embed([question])[0]
    cos = [cosine(qvec, json.loads(v)) for _, _, v in rows]
    bm = bm25_scores(question, [tokens(txt) for _, txt, _ in rows])

    # BM25 is unbounded, so it gets min-max scaled into [0,1]. Cosine is used
    # RAW and deliberately NOT scaled -- min-max scaling a set of cosines
    # stretches whatever spread they happen to have across the full 0-1 range,
    # manufacturing confidence the embedder never expressed and drowning out
    # BM25. Leaving cosine raw lets a genuine rare-term hit outrank a marginal
    # semantic one.
    bm_n = _minmax(bm)
    blended = [(1 - alpha) * c + alpha * b for c, b in zip(cos, bm_n)]
    return blended, cos, bm


def retrieve(question, k=TOP_K, alpha=HYBRID_ALPHA, rows=None):
    rows = rows if rows is not None else load_rows()
    blended, cos, bm = score_all(question, rows, alpha)
    scored = [
        (blended[i], cos[i], bm[i], rows[i][0], rows[i][1])
        for i in range(len(rows))
    ]
    scored.sort(reverse=True, key=lambda x: x[0])
    return scored[:k]


def ask(question, show=False):
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


def main():
    args = sys.argv[1:]
    show = "--show" in args
    args = [a for a in args if a != "--show"]
    arg = " ".join(args).strip()

    print(f"model: {CHAT_MODEL}   |   context supplied: top-{TOP_K} SQL facts")

    if not arg:
        for item in QUESTIONS:
            ask(item["q"], show)
    elif arg.isdigit():
        ask(QUESTIONS[int(arg) - 1]["q"], show)
    else:
        ask(arg, show=show)


if __name__ == "__main__":
    main()
