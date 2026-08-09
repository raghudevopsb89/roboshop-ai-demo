"""Step 3: build the RAG index over the SQL data.

Pipeline:
    SQL rows  ->  natural-language "fact" chunks  ->  embeddings  ->  rag_index table

Two things worth pointing out during the demo:

1. Rows are serialised into sentences, not dumped as CSV. Embedding models are
   trained on prose, so "Employee NRA-1119 is Aisha Rahman, a Senior ML
   Engineer..." retrieves far better than "NRA-1119,Aisha Rahman,...".

2. We also index pre-computed AGGREGATE facts (regional revenue totals). Pure
   vector search cannot do arithmetic -- if a user asks for a total, the total
   itself has to exist as a retrievable fact.
"""
import json
import sqlite3

from common import DB_PATH, EMBED_MODEL, embed, rule

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

chunks = []  # (source, text)


def add(source, text):
    chunks.append((source, " ".join(text.split())))


# ---- employees ----------------------------------------------------------
for r in conn.execute("SELECT * FROM employees"):
    mgr = r["manager"] if r["manager"] and r["manager"] != "NULL" else "no direct manager (reports to the executive team)"
    add("employees", f"""
        Employee {r['emp_id']} is {r['name']}, who works as {r['role']} in the
        {r['department']} department at Nimbus Retail Analytics. Based in
        {r['location']}. Joined on {r['joined_on']}. Manager: {mgr}.
    """)

# ---- products -----------------------------------------------------------
for r in conn.execute("SELECT * FROM products"):
    add("products", f"""
        Product SKU {r['sku']} belongs to the {r['product_line']} product line,
        {r['tier']} tier. Launched on {r['launched_on']} with a list price of
        ${r['list_price_usd']:,.2f} USD.
    """)

# ---- revenue: per-row facts --------------------------------------------
for r in conn.execute("SELECT * FROM quarterly_revenue"):
    add("quarterly_revenue", f"""
        In fiscal quarter {r['fiscal_quarter']}, the {r['region']} region generated
        ${r['revenue_usd']:,.2f} USD of revenue from the {r['product_line']} product
        line, across {r['deals_closed']} closed deals.
    """)

# ---- revenue: pre-computed aggregates ----------------------------------
for r in conn.execute("""
        SELECT fiscal_quarter, region,
               SUM(revenue_usd) AS total,
               SUM(deals_closed) AS deals,
               COUNT(*) AS lines
        FROM quarterly_revenue GROUP BY fiscal_quarter, region"""):
    top = conn.execute("""
        SELECT product_line, revenue_usd FROM quarterly_revenue
        WHERE fiscal_quarter=? AND region=?
        ORDER BY revenue_usd DESC LIMIT 1""",
        (r["fiscal_quarter"], r["region"])).fetchone()
    add("revenue_rollup", f"""
        TOTAL revenue for the {r['region']} region in fiscal quarter
        {r['fiscal_quarter']} was ${r['total']:,.2f} USD across {r['lines']} product
        lines and {r['deals']} closed deals. The highest contributing product line
        was {top['product_line']} at ${top['revenue_usd']:,.2f} USD.
    """)

# ---- projects -----------------------------------------------------------
for r in conn.execute("SELECT * FROM projects"):
    add("projects", f"""
        Project {r['project_code']} "{r['project_name']}" is led by {r['lead']}.
        Status: {r['status']}. It has {r['engineers']} engineers assigned, a target
        date of {r['target_date']}, and an approved budget of ${r['budget_usd']:,.2f} USD.
    """)

# ---- policies -----------------------------------------------------------
for r in conn.execute("SELECT * FROM policies"):
    add("policies", f"Company policy {r['policy_id']} -- {r['title']}: {r['body']}")

# ---- embed and persist --------------------------------------------------
print(rule("BUILDING RAG INDEX"))
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
    "SELECT text FROM rag_index WHERE source='revenue_rollup' LIMIT 1").fetchone()[0])
conn.close()
