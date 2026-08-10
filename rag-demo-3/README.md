# Ollama + live data (tool calling)
---

No index. The model calls tools, the tools query the real databases, and the
answer comes from whatever the database says at that moment.

Demo 2 embedded `Current stock on hand: 150 units` into a chunk once. Sell ten
and it still says 150. Stock and sales belong in a live query, not in RAG.

## Pre-requisites

| Piece | Choice | Why |
|---|---|---|
| Runtime | Ollama on `127.0.0.1:11434` | same box as demos 1 and 2 |
| Chat model | `llama3.2:3b` | must support tool calling |
| Catalogue | Azure MySQL Flexible Server, db `catalogue` | live stock and prices |
| Sale data | Azure Cosmos DB for MongoDB, db `orders` | live orders |
| Python deps | `PyMySQL`, `pymongo` | wire protocols need real drivers |

Runs on the RHEL VM only. Both stores are private to `workstation-vnet`.

```bash
make venv
source .venv/bin/activate
```

## Configuration

```bash
cd ../../azure-services/infra
export MYSQL_HOST=$(terraform output -raw mysql_host)
export MYSQL_USER=roboshopadmin
export MYSQL_PASSWORD='RoboShop@1'
export MYSQL_DATABASE=catalogue
export MONGO_URL=$(terraform output -json mongo_urls \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["orders"])')
```

`MONGO_URL` contains the Cosmos key. Keep it out of git.

## Run the demo

Check connectivity first:

```bash
python3 check_conn.py
```

Then ask:

```bash
python3 ask_live.py 1              # stock, hits MySQL
python3 ask_live.py 4              # sales, hits MongoDB
python3 ask_live.py "what does ROB012 cost?"
python3 ask_live.py --quiet 1      # hide the tool trace
```

Each query is shown as it runs:

```
  [round 1] get_stock({"sku": "ROB007"})
              -> {"found": true, "sku": "ROB007", "stock": 143, ...}
```

## Tools

| Tool | Store | Returns |
|---|---|---|
| `get_product(sku \| name)` | MySQL | price, category, description, stock |
| `get_stock(sku)` | MySQL | current stock |
| `get_sales_for_sku(sku)` | MongoDB | units sold, revenue |
| `get_recent_orders(limit)` | MongoDB | recent orders, newest first |

## Two things to expect

**The orders collection is empty.** Orders are written only when a checkout
completes through payment and Service Bus, and nothing seeds them. The sales
tools return `orders_found: 0` and the model is told to report that plainly
rather than invent a figure.

**A 3B model is unreliable at tool calling.** It sometimes skips the tool or
passes a bad SKU. Errors are handed back to it and the loop stops after 4 rounds.
Q6 needs two tools at once and often gets only one. Use a larger `CHAT_MODEL` if
you want it to look clean.

## Files

| File | Role |
|---|---|
| `config.py` | connection settings from env |
| `tools.py` | the four tools and the DB connections |
| `common.py` | Ollama client with tool calling |
| `check_conn.py` | connectivity check, run first |
| `ask_live.py` | the demo |
| `questions.py` | the demo questions |
| `Makefile` | `venv`, `check`, `ask`, `clean` |
