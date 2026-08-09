# Ollama + RAG end-to-end demo

Everything is installed and working on this server. This runbook is the script
to re-run it, plus what to say while it runs.

**Project dir:** `/var/ragdemo` (also reachable at `/root/code/rag-demo`)
Placed on `/var` because `/` has only ~1.6 GB free.

---

## What is running

| Piece | Choice | Why |
|---|---|---|
| Runtime | Ollama 0.32.6, systemd service on `127.0.0.1:11434` | CPU-only, no GPU on this box |
| Chat model | `llama3.2:3b` (2.0 GB) | Fits comfortably in CPU RAM, ~15 s/answer |
| Embeddings | `nomic-embed-text` (274 MB), 768-dim | Runs in Ollama, so **no PyTorch install** |
| Vector store | a `rag_index` table in the same SQLite DB | 50 chunks — a real vector DB is pointless here |
| Python deps | **none** — standard library only | Avoids RHEL 10 PEP-668 `pip` friction |

Models live in `/var/ollama/models` (set via a systemd drop-in at
`/etc/systemd/system/ollama.service.d/override.conf`), not the default
`/usr/share/ollama`.

---

## Demo script (~3 minutes)

### 0. Confirm the service is up

```bash
systemctl status ollama --no-pager
ollama list
```

### 1. Create the SQL data

```bash
cd /var/ragdemo
python3 01_setup_db.py
```

Builds `company.db` for a **fictional** company, Nimbus Retail Analytics:
`employees`, `products`, `quarterly_revenue`, `projects`, `policies`.

> Say out loud: *this company does not exist.* Nothing about it is on the public
> internet, so the model has no legitimate way to know any of these answers.
> That is what makes it a clean hallucination test.

### 2. Show the hallucination

```bash
python3 02_ask_raw.py 2
```

Q: *Who leads the Atlas Migration project, how many engineers, what budget?*

The model confidently invents a lead named **Rohan Patil**, **12 engineers**,
fake employee IDs (`JAV-0001`…), a budget in **₹25 lakhs**, and even adds
*"these figures are accurate as of our last update in December 2023."*
Truth: Sofia Marchetti, 9 engineers, $1,250,000.

Run `python3 02_ask_raw.py` for all five questions.

**Be straight with the audience about the system prompt.** `02_ask_raw.py` uses
a persona that *asserts* the assistant has access to internal systems and tells
it to always give figures. That is not rigging the demo — it is the most common
way teams actually deploy an internal chatbot, and it is exactly the bug: the
persona claims data access the model does not have, so the model fills the gap.

To show the honest contrast:

```bash
NEUTRAL=1 python3 02_ask_raw.py 2
```

With a neutral persona this model mostly **refuses** instead of fabricating.
Safer — but still useless to the employee who asked. RAG fixes both failures.

### 3. Build the RAG index

```bash
python3 03_build_index.py
```

Takes ~3 seconds. SQL rows → natural-language facts → 768-dim vectors → stored
back in SQLite. Two design points worth calling out:

1. **Rows become sentences, not CSV.** Embedding models are trained on prose, so
   `"Employee NRA-1119 is Aisha Rahman, a Senior ML Engineer…"` retrieves far
   better than `"NRA-1119,Aisha Rahman,…"`.
2. **Aggregates are pre-computed and indexed.** Vector search cannot do
   arithmetic. If someone asks for a regional total, that total must exist as a
   retrievable fact — hence the 6 `revenue_rollup` chunks.

### 4. Same question, now grounded

```bash
python3 04_ask_rag.py 2
```

Shows the retrieved facts with cosine scores, then the answer:
*Sofia Marchetti, 9 engineers, $1,250,000.00 USD.* Correct.

Add `--show` to print full chunks: `python3 04_ask_rag.py --show 2`

### 5. The side-by-side (best single command for an audience)

```bash
python3 05_compare.py 2      # one question
python3 05_compare.py        # all five
```

Prints hallucinated answer, retrieved facts, grounded answer, and ground truth
in one block.

### 6. Show it also knows when to shut up

```bash
python3 04_ask_rag.py "What was Nimbus Retail's marketing spend in FY2023-Q1?"
```

There is no marketing data in the DB. It replies
*"That information is not in the company database."* rather than inventing a
number. This matters: retrieval alone does not stop hallucination — the system
prompt in `04_ask_rag.py` forbids outside knowledge **and gives an explicit
escape hatch**, so "I don't know" is a legal answer. Without that, a model
handed weak context will still paper over the gap.

### 7. Live Q&A

```bash
python3 06_chat.py
```

Type any question. `/rag` toggles retrieval mid-conversation — the strongest
live moment is asking the same question twice across a toggle. `/facts` shows
what was retrieved, `/q` lists the demo questions, `/quit` exits.

---

## Full reset

```bash
cd /var/ragdemo && rm -f company.db && python3 01_setup_db.py && python3 03_build_index.py
```

---

## Files

| File | Role |
|---|---|
| `schema.sql` | Fictional company data — edit here to change the story |
| `common.py` | Ollama client (urllib) + cosine similarity |
| `questions.py` | The 5 demo questions + ground truth, strongest first |
| `01_setup_db.py` | SQL → `company.db` |
| `02_ask_raw.py` | No-RAG baseline (the hallucination) |
| `03_build_index.py` | Chunk → embed → `rag_index` |
| `04_ask_rag.py` | Retrieve → grounded answer |
| `05_compare.py` | Both, side by side |
| `06_chat.py` | Interactive REPL with `/rag` toggle |

---

## Expected timings (CPU-only, 8 cores)

| Step | Time |
|---|---|
| First answer after idle (model load) | ~15–20 s |
| Subsequent answers | ~5–10 s |
| Embedding all 50 chunks | ~3 s |
| `05_compare.py` (all 5) | ~2 min |

`OLLAMA_KEEP_ALIVE=30m` is set so the model stays resident between steps — a
cold reload mid-demo is the main thing that makes it feel slow. Warm it up right
before presenting:

```bash
ollama run llama3.2:3b "hi" --keepalive 30m
```

---

## Honest caveats

- **Q5 (the SLA question) is the weak one.** "30 minutes" is a common industry
  SLA value, so the model sometimes guesses it right without RAG — though it
  still fabricates supporting detail. It is kept last, and it is a fair thing to
  point out: hallucination is not uniform, which is exactly why you cannot eyeball
  your way to trusting an ungrounded model.
- **`llama3.2:3b` is small.** It follows the grounding instructions well here,
  but on a harder corpus a 3B model will still misread context. Scale up with
  `ollama pull qwen2.5:7b` and `export CHAT_MODEL=qwen2.5:7b` — all scripts
  respect that variable (also `EMBED_MODEL`, `OLLAMA_HOST`).
- **This is semantic-search RAG, not text-to-SQL.** It retrieves pre-serialised
  facts. It cannot answer questions requiring arithmetic that was not
  pre-computed (e.g. "average deal size in EMEA"). The other approach — have the
  LLM write a SQL query, run it, answer from the result set — is better for
  numeric/aggregate questions and worse for policy text. Production systems
  often route between both.
- **Brute-force cosine over 50 chunks** is intentional. At ~100k chunks you would
  want `sqlite-vec`, FAISS, or pgvector.
