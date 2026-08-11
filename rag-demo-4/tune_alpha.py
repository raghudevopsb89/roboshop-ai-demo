"""Measure HYBRID_ALPHA instead of inheriting it.

rag-demo-2 tuned alpha=0.4 against nomic-embed-text. That constant is a
property of THAT embedder's score distribution, not a universal truth, so it
does not survive the move to text-embedding-3-small. This script re-derives it.

Method: each question carries an `expect` marker -- a string appearing in
exactly one indexed chunk. For each candidate alpha we rank all chunks and
record where the expected one landed, reporting:

    hit@1   how many questions put the right chunk first (higher is better)
    MRR     mean reciprocal rank, 1/rank averaged -- rewards near-misses too

TWO COHORTS. questions.QUESTIONS all contain a rare literal token (ROB007,
"Hyderabad"), which is precisely what BM25 is best at. questions.PARAPHRASES
asks for the same five facts the way a customer would -- no SKU, no exact
product or city name -- which is where the embedder earns its keep.

WHAT THIS ACTUALLY MEASURED, honestly: on a 37-chunk corpus, both cohorts hit
5/5 at every alpha above the cliff, including pure BM25. The paraphrases were
added to break that tie and they did not, because RoboShop's product
descriptions keep repeating the same distinctive terms ("Kanto", "Telangana",
"six-axis"), so even a reworded question still lands rare-term matches. The
corpus is too small and too lexically distinctive for the upper end of the
range to matter.

What the run DOES establish is the lower bound -- the cliff below which exact
identifier lookup breaks -- and that bound is what moved when the embedder
changed. See the README for the numbers. Reporting a flat curve as a flat curve
is the point; a tuning script that prints a confident optimum off data like
this would be lying.

Each question is embedded ONCE and reused across every alpha, so this costs ten
embedding calls total, not ten per alpha.

Usage:
    python3 tune_alpha.py
"""
import json
import sys

from ask_rag import bm25_scores, _minmax, load_rows, tokens
from common import EMBED_MODEL, cosine, embed, rule
from questions import PARAPHRASES, QUESTIONS

ALPHAS = [round(i * 0.05, 2) for i in range(0, 21)]


def rank_of_expected(blended, rows, marker):
    """1-based rank of the first chunk containing `marker`."""
    order = sorted(range(len(rows)), key=lambda i: blended[i], reverse=True)
    for pos, i in enumerate(order, start=1):
        if marker.lower() in rows[i][1].lower():
            return pos
    return None


def precompute(cohort, rows, doc_vecs, doc_toks):
    """Embed each question once; return [(item, cosines, bm25_normed), ...]."""
    vecs = embed([item["q"] for item in cohort])
    out = []
    for item, qvec in zip(cohort, vecs):
        cos = [cosine(qvec, dv) for dv in doc_vecs]
        bm_n = _minmax(bm25_scores(item["q"], doc_toks))
        out.append((item, cos, bm_n))
    return out


def score(pre, rows, alpha):
    ranks = []
    for item, cos, bm_n in pre:
        blended = [(1 - alpha) * c + alpha * b for c, b in zip(cos, bm_n)]
        ranks.append(rank_of_expected(blended, rows, item["expect"]))
    found = [r for r in ranks if r]
    hit1 = sum(1 for r in ranks if r == 1)
    mrr = sum(1.0 / r for r in found) / len(ranks) if ranks else 0.0
    return hit1, mrr, ranks


def main():
    rows = load_rows()
    print(rule("TUNING HYBRID_ALPHA"))
    print(f"embedding model: {EMBED_MODEL}")
    print(f"corpus: {len(rows)} chunks")
    print(f"cohorts: {len(QUESTIONS)} exact-identifier, {len(PARAPHRASES)} paraphrased\n")

    doc_vecs = [json.loads(v) for _, _, v in rows]
    doc_toks = [tokens(txt) for _, txt, _ in rows]

    pre_exact = precompute(QUESTIONS, rows, doc_vecs, doc_toks)
    pre_para = precompute(PARAPHRASES, rows, doc_vecs, doc_toks)

    for label, pre in (("exact", pre_exact), ("paraphrase", pre_para)):
        for item, cos, _ in pre:
            print(f"  cosine spread [{label:<10}] {item['expect']:<10} "
                  f"{min(cos):.3f} .. {max(cos):.3f}")

    n = len(QUESTIONS) + len(PARAPHRASES)
    print(f"\n{'alpha':<7} {'exact':<16} {'paraphrase':<16} {'combined MRR'}")
    print("-" * 60)

    results = []
    for alpha in ALPHAS:
        e_hit, e_mrr, _ = score(pre_exact, rows, alpha)
        p_hit, p_mrr, p_ranks = score(pre_para, rows, alpha)
        combined = (e_mrr * len(QUESTIONS) + p_mrr * len(PARAPHRASES)) / n
        results.append((alpha, e_hit, p_hit, combined))
        print(f"{alpha:<7.2f} {e_hit}/{len(QUESTIONS)} mrr {e_mrr:.3f}     "
              f"{p_hit}/{len(PARAPHRASES)} mrr {p_mrr:.3f}     {combined:.3f}   "
              f"[{','.join(str(r) if r else '-' for r in p_ranks)}]")

    # Do NOT just take argmax. On a corpus this small the winning scores form a
    # wide plateau, and every alpha on it looks identical -- picking one by
    # argmax means picking arbitrarily, and the tie-break lands you exactly on
    # the cliff edge where the plateau starts. One more product could push you
    # off it.
    #
    # So: find the plateau, then sit a margin ABOVE its lower edge. The margin
    # buys headroom against the cliff; staying near the low end keeps weight on
    # the embedder, which degrades more gracefully on wording no test set
    # anticipated.
    MARGIN = 0.15
    top = max(round(r[3], 4) for r in results)
    plateau = [r[0] for r in results if round(r[3], 4) == top]
    edge = min(plateau)
    chosen = min([a for a in plateau if a >= edge + MARGIN] or [edge])
    best = next(r for r in results if r[0] == chosen)

    print(rule("RESULT"))
    print(f"optimal plateau: alpha {edge} .. {max(plateau)}  "
          f"({len(plateau)} of {len(ALPHAS)} values tie at MRR {top:.3f})")
    print(f"cliff edge:      alpha < {edge} loses exact-identifier lookups")
    print(f"chosen:          {chosen}   (edge + {MARGIN} margin)")
    print(f"                 exact {best[1]}/{len(QUESTIONS)}, "
          f"paraphrase {best[2]}/{len(PARAPHRASES)}")

    if len(plateau) > len(ALPHAS) // 3:
        print("\nHONEST CAVEAT: that plateau is wide, so this corpus cannot")
        print("discriminate between alphas above the cliff -- 37 chunks and 10")
        print("questions is too easy a problem. What IS measured here is the")
        print("lower bound, and that is the number that moved when the embedder")
        print("changed. Treat the value above as 'safely past the cliff', not as")
        print("a finely-tuned optimum. To tune properly, grow the corpus and add")
        print("questions whose answers share no rare terms with their chunk.")

    print("\nSet it in ask_rag.py, or export it:")
    print(f"  export HYBRID_ALPHA={chosen}")

    pure_cos = next(r for r in results if r[0] == 0.0)
    pure_bm = next(r for r in results if r[0] == 1.0)
    print("\nthe case for blending, in two rows:")
    print(f"  pure cosine (alpha=0): exact {pure_cos[1]}/{len(QUESTIONS)}, "
          f"paraphrase {pure_cos[2]}/{len(PARAPHRASES)}, combined MRR {pure_cos[3]:.3f}")
    print(f"  pure BM25   (alpha=1): exact {pure_bm[1]}/{len(QUESTIONS)}, "
          f"paraphrase {pure_bm[2]}/{len(PARAPHRASES)}, combined MRR {pure_bm[3]:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
