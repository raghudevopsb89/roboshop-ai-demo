# Microsoft Foundry + RAG (hosted models)

---

Demo 2, moved off local Ollama and onto hosted Foundry endpoints. Same RoboShop
data, same 37 chunks, same hybrid retrieval, same questions — so the two demos
sit side by side and only the models differ.

The point of running it is not that it works. It is **what had to change**, and
what did not.

## Pre-requisites

| Piece | Choice | Why |
|---|---|---|
| Endpoint | Foundry, `../infra` Terraform stack | `make dev` there first |
| Chat model | `gpt-5-mini` (default), `Ministral-3B` (alt) | see "Two chat models" |
| Embeddings | `text-embedding-3-small`, 1536-dim | replaces `nomic-embed-text` |
| Vector store | `rag_index` table in `roboshop.db` | unchanged from demo 2 |
| Python deps | **none** — standard library only | `/openai/v1/` is plain REST |

The zero-pip-install property survives the move. The OpenAI-compatible route is
HTTPS + JSON, so `urllib` still does the job and RHEL 10's PEP-668 friction
stays avoided.

## Run it

Everyone has their own Foundry, so nothing about your setup is committed. Save
your settings once as a profile:

```bash
cd ../infra && ENV=<yourname> make profile     # -> profiles/<yourname>.env
```

Then select it per run, or source it:

```bash
export ROBOSHOP_PROFILE=<yourname>
# or: source profiles/<yourname>.env
```

`profiles/*.env` is gitignored — `AZURE_KEY` and `MONGO_URL` are secrets.
`profiles/example.env` is the committed template. A real environment variable
always beats the file, so you can override one value for a single run:

```bash
CHAT_MODEL=Ministral-3B python3 ask_rag.py 1
```

Exporting the four variables by hand still works and needs no profile:

```bash
cd ../infra && eval "$(make -s env)" && cd ../rag-demo-4
```

Either way you end up with `AZURE_BASE`, `AZURE_KEY`, `CHAT_MODEL`,
`EMBED_MODEL`.

```bash
python3 ask_raw.py 1          # before: no context
python3 setup_db.py           # 1 - load catalogue.sql + shipping.sql
python3 build_index.py        # 2 - 37 chunks -> embeddings -> rag_index
python3 ask_rag.py 1          # after: grounded
python3 compare.py 1          # both halves, one screen
```

Switches:

```bash
python3 tune_alpha.py                    # re-derive HYBRID_ALPHA (see below)
HYBRID_ALPHA=0 python3 ask_rag.py 1      # pure vector search
CHAT_MODEL=Ministral-3B python3 ask_rag.py 1
NEUTRAL=1 python3 ask_raw.py 1
python3 ask_rag.py --show 1
```

## What actually changed

### 1. The tuned constant did not transfer — and the reason is measurable

Demo 2 uses `HYBRID_ALPHA=0.4`, justified by `nomic-embed-text` producing
cosines in a narrow **0.81–0.86** band. `text-embedding-3-small` produces
**0.32–0.89** on the same corpus, and **0.03–0.57** on paraphrased questions.
Same maths, completely different distribution — so the old constant is
meaningless here even though it happens to still fall in a working range.

Pure cosine gets *worse* with the better embedder on exact-ID lookup:

| | correct chunk's rank on "SKU ROB007", cosine only |
|---|---|
| demo 2, `nomic-embed-text` | 4th of 37 (scraped into top-5) |
| demo 4, `text-embedding-3-small` | **10th of 37** (misses top-5 entirely) |

`python3 ask_rag.py 1` with `HYBRID_ALPHA=0` shows this — ROB007 is simply
absent from the retrieved context, and the model correctly answers that it
doesn't know. Blending fixes it:

```
[0.765  cos=0.639 bm25= 5.14] ROB007  LiPo Battery Pack 48V   <- the answer
[0.724  cos=0.686 bm25= 4.11] ROB001  Robo-Arm Deluxe
```

Look at the cosine column: ROB007 scores **lower** than ROB001 on pure
semantics (0.639 vs 0.686). BM25 is what puts it first. That is the entire
argument for hybrid retrieval, in two lines.

### 2. `tune_alpha.py` measures it instead of asserting it

```
optimal plateau: alpha 0.2 .. 1.0  (17 of 21 values tie at MRR 1.000)
cliff edge:      alpha < 0.2 loses exact-identifier lookups
chosen:          0.35   (edge + 0.15 margin)
```

**The honest result is that this corpus cannot tune alpha.** 37 chunks and 10
questions is too easy: everything from 0.2 to 1.0 scores perfectly, pure BM25
included. A second cohort of paraphrased, identifier-free questions was added
specifically to break that tie and it didn't — RoboShop's descriptions repeat
distinctive terms ("Kanto", "Telangana", "six-axis"), so even reworded queries
land rare-term matches.

What *is* measured is the **lower bound**, and that is the number that moved
when the embedder changed. The script picks a margin above the cliff rather
than the argmax, because argmax on a flat curve means picking arbitrarily —
and the tie-break lands you exactly on the edge, where one more product could
push you off.

Reporting a flat curve as flat is the lesson. A tuner that printed a confident
optimum off this data would be lying.

### 3. Two chat models, and neither behaved as assumed

**`Ministral-3B` is deployed but is not the default.** Azure caps it at
`capacity = 1` — literally, it rejects any other value — and that is not enough
throughput for a RAG turn. A five-chunk context reliably returns 429
`RateLimitReached`, and it keeps returning it through the full retry budget
even honouring `Retry-After`. It works fine for short prompts. Use it to show
small-model behaviour; don't build the demo on it.

**`gpt-5-mini` rejects `temperature=0`** — only its default is allowed. Demos
1–3 all pass `temperature=0` for reproducibility, and Ministral-3B honours it.
`common.py` sends it, notices the 400, and drops it for the rest of the run
rather than hardcoding a model list that would rot. Consequence worth saying on
screen: **demo 4's answers are not bit-reproducible** the way demos 1–3 are.

**`gpt-4o-mini` cannot be deployed at all** any more — `ServiceModelDeprecating`.
Model coordinates rot; `make models` in `../infra` lists what your region
currently accepts.

### 4. A capable model still hallucinates

The worry going in was that a stronger model would refuse rather than fabricate,
weakening the "before" half. It did not. `gpt-5-mini`, no context, naive
persona:

> SKU ROB007 is the RoboCore R7 Microcontroller Development Kit. Price: $59.95
> USD. Current stock: 42 units available.

Invented product, invented price, invented stock level, stated flatly. The
truth is a LiPo Battery Pack 48V at $199.99 with 150 in stock. The persona that
claims data access the model doesn't have is the bug, and model quality does
not fix it — which is the whole point of the demo.

Worth running `NEUTRAL=1` too: a plain persona usually produces a refusal
instead. Safer, still useless, still fixed by RAG.

## Live data (`ask_live.py`)

The RAG half above answers from text embedded once. Stock and sales are not
that: `Current stock on hand: 150 units` is frozen into a chunk until the index
is rebuilt. `ask_live.py` holds no index and queries the databases per question,
via tool calling.

```
stock, prices  ->  Azure MySQL Flexible Server  (catalogue.products)
sale data      ->  Azure Cosmos DB for MongoDB  (orders.orders)
```

Those databases are the `azure-services` stack, not `../infra`, and they are
private to `workstation-vnet` — **this half runs on the RHEL VM only.** The
Foundry endpoint is public, so the RAG half still runs anywhere.

It also needs drivers, so the zero-pip property does not survive here:

```bash
make venv && source .venv/bin/activate
```

```bash
cd ../../azure-services/infra
export MYSQL_HOST=$(terraform output -raw mysql_host)
export MYSQL_PASSWORD='RoboShop@1'
export MONGO_URL=$(terraform output -json mongo_urls \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["orders"])')
```

`MONGO_URL` contains the Cosmos key. Keep it out of git.

```bash
python3 check_conn.py     # Foundry + both databases, run first
python3 ask_live.py 1     # stock, hits MySQL
python3 ask_live.py 4     # sales, hits MongoDB
python3 ask_live.py --quiet 1
```

| Tool | Store | Returns |
|---|---|---|
| `get_product(sku \| name)` | MySQL | price, category, description, stock |
| `get_stock(sku)` | MySQL | current stock |
| `get_sales_for_sku(sku)` | MongoDB | units sold, revenue |
| `get_recent_orders(limit)` | MongoDB | recent orders, newest first |

**Use `gpt-5-mini`, not `Ministral-3B`.** A tool-calling turn is several round
trips, so `capacity = 1` throttles even harder here than it does on a RAG turn.

**The orders collection is empty.** Orders are written only when a checkout
completes through payment and Service Bus, and nothing seeds them. The sales
tools return `orders_found: 0` and the model is told to report that plainly
rather than invent a figure — Q4 and Q5 exist to show it doing so.

## Files

| File | Step |
|---|---|
| `catalogue.sql`, `shipping.sql` | the data — 12 products, 25 cities (copied from demo 2 so this demo stands alone) |
| `envprofile.py` | loads `profiles/<name>.env` when `ROBOSHOP_PROFILE` is set |
| `profiles/example.env` | template — copy, fill in, it stays gitignored |
| `common.py` | Foundry client — auth, retries, response shapes, tool calling |
| `setup_db.py` | 1 — load the two `.sql` files into `roboshop.db` |
| `ask_raw.py` | 2 — no context (the hallucination half) |
| `build_index.py` | 3 — rows → prose facts → embeddings → `rag_index` |
| `ask_rag.py` | 4 — hybrid retrieve top-k and answer, grounded |
| `tune_alpha.py` | measure `HYBRID_ALPHA` rather than inherit it |
| `compare.py` | both halves of one question, one output |
| `questions.py` | demo questions + paraphrase cohort + live questions |
| `tools.py` | the four live tools and the DB connections |
| `check_conn.py` | Foundry + database reachability, run before `ask_live.py` |
| `ask_live.py` | live tool calling — no index, queries per question |
| `Makefile` | `venv`, `check`, `live`, `clean` |

## Gotchas

**Do not mix indexes across demos.** This demo keeps its own `roboshop.db`
because its vectors are 1536-dim and demo 2's are 768-dim. `common.cosine()`
uses `zip()`, which truncates to the shorter vector rather than raising — so a
mixed index scores plausible-looking nonsense instead of failing loudly.

**Embedding order is not guaranteed.** The API returns a `data` list whose
entries carry an `index`; `embed()` sorts by it. Skipping that pairs the wrong
vector with the wrong chunk and produces an index that looks fine and retrieves
garbage.

**Cost.** 37 chunks embedded once, a few hundred tokens per question. Both
deployments are serverless — no idle charge. `cd ../infra && make dev-destroy`
removes everything.
