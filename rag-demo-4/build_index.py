"""Step 3: build the RAG index over the RoboShop SQL data, using Foundry.

Pipeline is identical to rag-demo-2:

    SQL rows  ->  natural-language "fact" chunks  ->  embeddings  ->  rag_index

Rows are serialised into sentences, not dumped as CSV. Embedding models are
trained on prose, so "SKU ROB007 is the LiPo Battery Pack 48V, priced at
$199.99..." retrieves far better than "ROB007,LiPo Battery Pack 48V,199.99".

The one thing that changed is the vector width: nomic-embed-text produced 768
dimensions, text-embedding-3-small produces 1536. That is why this demo keeps
its own roboshop.db -- vectors from two different embedders are not comparable,
and common.cosine() uses zip(), which silently truncates to the shorter vector
rather than raising. Mixing them yields plausible-looking nonsense rather than
an error, which is far worse.

Note on scope: per-row facts only, no pre-computed aggregates. "What does
ROB007 cost" works perfectly; "total inventory value" does not, because vector
search cannot add and top-k only ever sees k rows. rag-demo-1/build_index.py
shows the rollup-fact technique if you want it here.
"""
import json
import sqlite3

from common import DB_PATH, EMBED_MODEL, embed, rule

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

chunks = []  # (source, text)


def add(source, text):
    chunks.append((source, " ".join(text.split())))


# ---- catalogue products -------------------------------------------------
for r in conn.execute("SELECT * FROM products ORDER BY sku"):
    add("products", f"""
        RoboShop product SKU {r['sku']} is the {r['name']}, sold in the
        {r['category']} category at a list price of ${r['price']:,.2f} USD.
        Current stock on hand: {r['stock']} units. Description: {r['description']}
    """)

# ---- shipping destinations ----------------------------------------------
for r in conn.execute("SELECT * FROM cities ORDER BY country_code, city"):
    add("cities", f"""
        RoboShop ships to {r['city']}, which is listed under the region
        {r['region']} in country code {r['country_code']}. Coordinates:
        latitude {r['latitude']}, longitude {r['longitude']}.
    """)

# ---- embed and persist --------------------------------------------------
print(rule("BUILDING RAG INDEX  (embeddings from Microsoft Foundry)"))
print(f"embedding model: {EMBED_MODEL}")
print(f"chunks to embed: {len(chunks)}\n")

conn.execute("DROP TABLE IF EXISTS rag_index")
conn.execute("""
    CREATE TABLE rag_index (
        id     INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        text   TEXT NOT NULL,
        vector TEXT NOT NULL
    )""")

BATCH = 16
for i in range(0, len(chunks), BATCH):
    batch = chunks[i:i + BATCH]
    vectors = embed([t for _, t in batch])
    conn.executemany(
        "INSERT INTO rag_index (source, text, vector) VALUES (?,?,?)",
        [(src, txt, json.dumps(vec)) for (src, txt), vec in zip(batch, vectors)],
    )
    print(f"  embedded {min(i + BATCH, len(chunks)):>3}/{len(chunks)}")

conn.commit()

dim = len(json.loads(conn.execute("SELECT vector FROM rag_index LIMIT 1").fetchone()[0]))
print(f"\nindexed {len(chunks)} chunks, vector dimension = {dim}")
print("\nchunks by source table:")
for row in conn.execute(
        "SELECT source, COUNT(*) c FROM rag_index GROUP BY source ORDER BY c DESC"):
    print(f"  {row[0]:<20} {row[1]:>3}")

print("\nexample chunk:")
print("  " + conn.execute(
    "SELECT text FROM rag_index WHERE source='products' LIMIT 1").fetchone()[0])
conn.close()
