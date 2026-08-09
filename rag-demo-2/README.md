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

Other switches:

```bash
NEUTRAL=1 python3 ask_raw.py 1     # neutral persona -> refusals instead of fabrication
TOP_K=8 python3 ask_rag.py 1       # widen retrieval
```

## Two honest caveats

**1. RoboShop is a real public project.** Unlike Nimbus in demo 1, "RoboShop" is
a widely-used public DevOps training app, so `llama3.2:3b` has *some* genuine
knowledge of its microservice architecture. Ask "what services does RoboShop
have" and the no-RAG answer is partly right, which muddies the contrast. Every
question in `questions.py` is therefore about **catalogue and shipping data** —
the 12 products are invented for this monorepo, so the model cannot know them
and fails cleanly. Q5 (Tokyo → Kanto) is deliberately left as the weak one: it is
real-world public knowledge, so the model often gets it right by luck. That is an
honest illustration that hallucination is not uniform — it fails hardest on
private data.

**2. This index holds per-row facts only — no aggregates.** So "what does ROB007
cost" works perfectly, but "total inventory value" or "your most expensive
product" are **not** reliably answerable: vector search cannot add or sort, and
top-k only ever sees k rows. `rag-demo-1/build_index.py` shows the fix —
indexing pre-computed rollup facts — if you want to demo that technique here.

Related: exact-identifier lookups like `ROB007` are the known weak spot of pure
vector search, since a rare token carries little semantic signal. If Q1 retrieves
poorly on the real embedder, either raise `TOP_K` or add a keyword/BM25 pass
alongside cosine.

## Files

| File | Step |
|---|---|
| `common.py` | Ollama client, cosine, config |
| `setup_db.py` | 1 — mirror the real SQL into `roboshop.db` |
| `ask_raw.py` | 2 — ask with **no** context (the hallucination half) |
| `build_index.py` | 3 — rows → prose facts → embeddings → `rag_index` |
| `ask_rag.py` | 4 — retrieve top-k and answer, grounded |
| `questions.py` | the demo questions + ground truth from SQL |
