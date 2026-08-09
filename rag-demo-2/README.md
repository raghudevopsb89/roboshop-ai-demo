# Ollama + RAG over real RoboShop data
---

## Pre-requisites

Identical to demo 1 — same Ollama, same models, **no pip installs**.

| Piece | Choice | Why |
|---|---|---|
| Runtime | Ollama 0.32.6, systemd service on `127.0.0.1:11434` | CPU-only, no GPU on this box |
| Chat model | `llama3.2:3b` (2.0 GB) | Fits comfortably in CPU RAM, ~15 s/answer |
| Embeddings | `nomic-embed-text` (274 MB), 768-dim | Runs in Ollama, so **no PyTorch install** |
| Vector store | a `rag_index` table in the same SQLite DB | 37 chunks — a real vector DB is pointless here |
| Python deps | **none** — standard library only | Avoids RHEL 10 PEP-668 `pip` friction |


```bash
dnf install zstd -y
curl -fsSL https://ollama.com/install.sh | sh
ollama list
ollama pull nomic-embed-text
ollama pull llama3.2:3b
```


## Run the demo

Before RAG — the model has no catalogue, so it invents one:

```bash
python3 ask_raw.py 1
python3 ask_raw.py 2
```

Setup RAG:

```bash
python3 setup_db.py
python3 build_index.py
```

After RAG — same questions, now grounded:

```bash
python3 ask_rag.py 1
python3 ask_rag.py 2
python3 ask_rag.py --show 1        # also print the retrieved chunks in full
python3 ask_rag.py "is the gripper kit in stock?"
```

Or both at once — this is the one to put on a screen:

```bash
python3 compare.py 1               # same question, no-RAG and RAG side by side
```

Other switches:

```bash
NEUTRAL=1 python3 ask_raw.py 1        # neutral persona -> refusals instead of fabrication
TOP_K=8 python3 ask_rag.py 1          # widen retrieval
HYBRID_ALPHA=0 python3 ask_rag.py 1   # pure vector search, no BM25 (see below)
```

## Two honest caveats

**1. RoboShop is a real public project.** Unlike Nimbus in demo 1, "RoboShop" is
a widely-used public DevOps training app, so `llama3.2:3b` has *some* genuine
knowledge of its microservice architecture. Ask "what services does RoboShop
have" and the no-RAG answer is partly right, which muddies the contrast. Every
question in `questions.py` is therefore about **catalogue and shipping data** —
the 12 products are invented for RoboShop, so the model cannot know them
and fails cleanly. Q5 (Tokyo → Kanto) is deliberately left as the weak one: it is
real-world public knowledge, so the model often gets it right by luck. That is an
honest illustration that hallucination is not uniform — it fails hardest on
private data.

**2. This index holds per-row facts only — no aggregates.** So "what does ROB007
cost" works perfectly, but "total inventory value" or "your most expensive
product" are **not** reliably answerable: vector search cannot add or sort, and
top-k only ever sees k rows. `rag-demo-1/build_index.py` shows the fix —
indexing pre-computed rollup facts — if you want to demo that technique here.

## Why retrieval is hybrid, not pure cosine

Worth demoing on its own — run `HYBRID_ALPHA=0 python3 ask_rag.py 1` to see it.

Pure vector search is bad at exact-identifier lookup. Asked for **SKU ROB007**,
`nomic-embed-text` ranked the correct chunk **4th of 5**, a thousandth of a point
ahead of the chunk that fell off the list:

```
[0.856] ROB001  Robo-Arm Deluxe
[0.826] ROB005  RoboOS Pro License
[0.816] ROB011  MicroBot Starter Kit
[0.815] ROB007  LiPo Battery Pack 48V   <- the answer
[0.814] ROB003  Servo Motor Pack        <- 0.001 behind
```

It got the right answer only because `TOP_K=5` reached far enough. `ROB007`
carries almost no semantic signal, so the embedder ranked by generic
product-ness instead — the top hit is the most *typical* product, not the one
asked for. Add a dozen products and this question starts failing.

The fix is **BM25 blended with cosine** (`HYBRID_ALPHA`, default 0.4). BM25
weights *rare* terms heavily, and a SKU appears in exactly one chunk out of 37,
so it pins that chunk to rank 1 — now first with a 0.057 margin instead of
fourth by 0.001. It is ~25 lines and needs no new dependencies.

One subtlety worth pointing at during the demo: **cosine is used raw and
deliberately not normalised**, while BM25 is min-max scaled. Min-max scaling the
cosines stretches their narrow 0.81–0.86 band across the full 0–1 range, which
manufactures confidence the embedder never had and drowns out BM25 — with that
bug in place, ROB007 only climbed to rank 3. Rank-fusion (RRF) also fails here,
because ROB001 scores well on *both* signals while ROB007 wins on only one.

## Files

| File | Step |
|---|---|
| `catalogue.sql` | the data — 12 RoboShop products (INSERT-only) |
| `shipping.sql` | the data — 25 shipping destinations (INSERT-only) |
| `common.py` | Ollama client, cosine, config |
| `setup_db.py` | 1 — load the two `.sql` files into `roboshop.db` |
| `ask_raw.py` | 2 — ask with **no** context (the hallucination half) |
| `build_index.py` | 3 — rows → prose facts → embeddings → `rag_index` |
| `ask_rag.py` | 4 — hybrid retrieve top-k and answer, grounded |
| `compare.py` | both halves of one question, in one output |
| `questions.py` | the demo questions |

Both `.sql` files are INSERT-only MySQL dumps, so `setup_db.py` supplies the two
`CREATE TABLE` definitions itself and rewrites the MySQL-isms on the way in
(`USE` dropped, `INSERT IGNORE` → `INSERT OR IGNORE`). To change the demo data,
edit those two files and re-run steps 1 and 3 — nothing else needs touching.
