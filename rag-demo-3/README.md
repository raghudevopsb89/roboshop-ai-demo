# Live data via tool calling
---

Demos 1 and 2 answered from text embedded once, at index time. This one holds no
index at all — every answer runs a real, authenticated query against the real
databases at the moment you ask.

| | demo 2 | demo 3 |
|---|---|---|
| Data | embedded snapshot in SQLite | **live** Azure MySQL + Cosmos MongoDB |
| Mechanism | vector + BM25 retrieval | **tool calling** |
| Stock figure | frozen at index time | read per question |
| Python deps | none | `PyMySQL`, `pymongo` |

**Why this demo exists.** Look at what demo 2 bakes into every chunk:

```
Current stock on hand: 150 units.
```

That number is frozen into the embedded text. Sell ten units and the RAG answer
still says 150 until you re-run `build_index.py`. Price and description are fine
in RAG — they rarely change. **Stock and sales are exactly the fields that must
not be RAG.** That is the lesson here.

## Where the sale data lives

Traced through the `azure-services` monorepo:

| | |
|---|---|
| Store | Azure **Cosmos DB for MongoDB**, account `roboshop-dev-mongo` |
| Database / collection | `orders` / `orders` |
| Written by | `OrderListener.handleOrderEvent`, consuming Service Bus messages published by **payment** |
| Document shape | `userId, userEmail, userName, items[{productId,name,sku,price,quantity}], total, shippingCost, shippingCity, cityId, transactionId, status, orderDate` |

**It is empty on a fresh environment, and that is expected.** An order document
is created only when a checkout completes end to end. There is no seed script
for orders anywhere in `azure-services` — the only Mongo seed is
`roboshop-user/db/master-data.js`, which seeds one admin user.

That is deliberately not worked around here. The sales tools report
`orders_found: 0` and the system prompt forbids the model from filling the gap,
so you get *"no sales have been recorded"* — a truthful answer to a question
about missing data, which is precisely what demo 1 could not produce.

## Prerequisites

**This must run on the RHEL VM**, not a laptop. Cosmos has
`public_network_access_enabled = false` and MySQL is VNet-integrated on a
delegated subnet — both are reachable only from inside `workstation-vnet`, where
the VM (`10.1.0.100`) lives.

Unlike demos 1 and 2, this one **cannot be stdlib-only**: the MySQL and MongoDB
wire protocols need real drivers. RHEL 10 marks the system Python as externally
managed (PEP 668), so use the venv:

```bash
make venv
source .venv/bin/activate
```

## Configuration

Everything comes from the environment; no secret is committed.

```bash
cd ../../azure-services/infra
export MYSQL_HOST=$(terraform output -raw mysql_host)
export MYSQL_USER=roboshopadmin
export MYSQL_PASSWORD='RoboShop@1'        # infra/env-dev/main.tfvars
export MYSQL_DATABASE=catalogue
export MONGO_URL=$(terraform output -json mongo_urls \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["orders"])')
```

`MONGO_URL` embeds the Cosmos primary key — keep it out of git, out of shell
history where you can, and out of screenshots. `config.summary()` prints only the
host, never the string.

Other knobs: `MYSQL_TLS=false` for a local plaintext MySQL, `MYSQL_SSL_CA` if
your CA bundle is not at `/etc/pki/tls/certs/ca-bundle.crt`, `MONGO_TIMEOUT_MS`.

## Run it

Connectivity first — this isolates network and DNS problems before a model is
anywhere near them:

```bash
python3 check_conn.py      # or: make check
```

Then ask:

```bash
python3 ask_live.py 1              # stock -- hits MySQL
python3 ask_live.py 4              # sales -- hits MongoDB, honestly reports empty
python3 ask_live.py "what does ROB012 cost?"
python3 ask_live.py --quiet 1      # hide the tool-call trace
```

The trace shows each real query as it happens:

```
  [round 1] get_stock({"sku": "ROB007"})
              -> {"found": true, "sku": "ROB007", "stock": 143, ...}
```

## The tools

| Tool | Store | Returns |
|---|---|---|
| `get_product(sku \| name)` | MySQL | price, category, description, stock |
| `get_stock(sku)` | MySQL | current stock — the volatile field |
| `get_sales_for_sku(sku)` | MongoDB | units sold, revenue, orders containing it |
| `get_recent_orders(limit)` | MongoDB | most recent orders, newest first |

`get_sales_for_sku` uses `find()` plus a Python loop rather than an aggregation
pipeline: Cosmos DB's Mongo 4.2 surface supports only a subset of aggregation
operators, and the order volume here does not justify the risk.

## Honest caveat: 3B models are bad at tool calling

`llama3.2:3b` supports tools, but it is small. Expect it to sometimes skip the
tool and answer from memory, pass a malformed SKU, or call the same tool
repeatedly. Unknown tools and bad arguments are caught and returned to the model
as `{"error": ...}` so it can recover, and the loop gives up after
`MAX_ROUNDS = 4`.

Q6 is in the set precisely to show this: it needs **two** tools (MySQL stock plus
MongoDB sales) in one answer, and a 3B model frequently manages only one. That is
a real limitation of small-model tool calling, worth showing rather than hiding.
If you want it to look reliable, run a bigger model via `CHAT_MODEL`.

## Files

| File | Role |
|---|---|
| `config.py` | connection settings from env, secret-free summary |
| `tools.py` | the four live tools, their schemas, and the DB connections |
| `common.py` | Ollama client with tool-calling support |
| `check_conn.py` | connectivity smoke test — run this first |
| `ask_live.py` | the demo: question → tool → real query → answer |
| `questions.py` | the demo questions |
| `Makefile` | `venv`, `check`, `ask`, `clean` |
