"""Live tools: real queries against the real RoboShop databases.

The RAG half of this demo (build_index.py / ask_rag.py) answers from text
embedded once. That is right for descriptions and wrong for anything volatile:
a chunk saying "Current stock on hand: 150 units" stays 150 until the index is
rebuilt. These tools run a query at the moment the question is asked.

    stock, prices  ->  Azure MySQL Flexible Server  (catalogue.products)
    sale data      ->  Azure Cosmos DB for MongoDB  (orders.orders)

Both stores are PRIVATE to workstation-vnet, so this half only runs on the RHEL
VM. The Foundry endpoint in common.py is public and works from anywhere -- which
is why the RAG half runs on a laptop and this one does not.

Connection settings come from the environment; nothing secret is committed.
See check_conn.py for a standalone reachability test.
"""
import os

# Same side-effect import as common.py: load the selected profile before the
# settings below read os.environ. Safe to import twice; Python caches it.
import envprofile  # noqa: F401

# ---- MySQL (catalogue: products, live stock) ----------------------------
MYSQL_HOST = os.environ.get("MYSQL_HOST", "")
MYSQL_USER = os.environ.get("MYSQL_USER", "roboshopadmin")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "catalogue")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))

# Azure MySQL Flexible Server requires TLS. It presents a DigiCert chain, which
# is already in the RHEL system trust store, so the default bundle works.
MYSQL_TLS = os.environ.get("MYSQL_TLS", "true").lower() not in ("false", "0", "no")
MYSQL_SSL_CA = os.environ.get("MYSQL_SSL_CA", "/etc/pki/tls/certs/ca-bundle.crt")

# ---- MongoDB / Cosmos (orders: the sale data) ---------------------------
MONGO_URL = os.environ.get("MONGO_URL", "")
MONGO_DB = os.environ.get("MONGO_DB", "orders")
MONGO_COLLECTION = os.environ.get("MONGO_COLLECTION", "orders")
MONGO_TIMEOUT_MS = int(os.environ.get("MONGO_TIMEOUT_MS", "8000"))

_mysql_conn = None
_mongo_client = None


def missing(*names):
    return [n for n in names if not globals().get(n)]


def require(*names):
    gaps = missing(*names)
    if gaps:
        raise SystemExit(
            "missing environment variable(s): " + ", ".join(gaps) + "\n\n"
            "These come from the azure-services stack, not ../infra:\n"
            "  cd ../../azure-services/infra\n"
            "  export MYSQL_HOST=$(terraform output -raw mysql_host)\n"
            "  export MYSQL_PASSWORD='RoboShop@1'\n"
            "  export MONGO_URL=$(terraform output -json mongo_urls | "
            "python3 -c 'import json,sys; print(json.load(sys.stdin)[\"orders\"])')")


def summary():
    """Secret-free view of where we are pointed."""
    mongo = "(unset)"
    if MONGO_URL:
        # Never print the URL itself: it embeds the Cosmos primary key.
        mongo = MONGO_URL.split("@")[-1].split("/")[0] if "@" in MONGO_URL else "?"
    return (f"mysql: {MYSQL_USER}@{MYSQL_HOST or '(unset)'}:{MYSQL_PORT}/"
            f"{MYSQL_DATABASE} tls={'on' if MYSQL_TLS else 'off'}\n"
            f"mongo: {mongo} db={MONGO_DB} coll={MONGO_COLLECTION}")


# ---------------------------------------------------------------- connections
def mysql():
    global _mysql_conn
    if _mysql_conn is not None:
        return _mysql_conn
    import pymysql

    require("MYSQL_HOST", "MYSQL_PASSWORD")
    kwargs = dict(
        host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
        password=MYSQL_PASSWORD, database=MYSQL_DATABASE,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10, charset="utf8mb4",
    )
    if MYSQL_TLS:
        # Passing ssl_ca is what actually switches PyMySQL into TLS mode.
        kwargs["ssl_ca"] = MYSQL_SSL_CA
    _mysql_conn = pymysql.connect(**kwargs)
    return _mysql_conn


def mongo():
    global _mongo_client
    if _mongo_client is not None:
        return _mongo_client
    from pymongo import MongoClient

    require("MONGO_URL")
    _mongo_client = MongoClient(
        MONGO_URL, serverSelectionTimeoutMS=MONGO_TIMEOUT_MS,
        connectTimeoutMS=MONGO_TIMEOUT_MS)
    return _mongo_client


def orders_collection():
    return mongo()[MONGO_DB][MONGO_COLLECTION]


# --------------------------------------------------------------------- tools
def get_product(sku=None, name=None):
    """One product from the live catalogue, by SKU or partial name."""
    if not sku and not name:
        return {"error": "provide either sku or name"}
    with mysql().cursor() as cur:
        if sku:
            cur.execute("SELECT sku, name, description, price, category, stock "
                        "FROM products WHERE sku = %s", (sku.strip().upper(),))
        else:
            cur.execute("SELECT sku, name, description, price, category, stock "
                        "FROM products WHERE name LIKE %s LIMIT 1",
                        (f"%{name.strip()}%",))
        row = cur.fetchone()
    if not row:
        return {"found": False, "query": sku or name}
    row["price"] = float(row["price"])
    return {"found": True, **row}


def get_stock(sku):
    """Current stock for one SKU. The volatile field -- always read live."""
    with mysql().cursor() as cur:
        cur.execute("SELECT sku, name, stock FROM products WHERE sku = %s",
                    (sku.strip().upper(),))
        row = cur.fetchone()
    return {"found": True, **row} if row else {"found": False, "sku": sku}


def get_sales_for_sku(sku):
    """Units sold and revenue for one SKU, from the live orders data.

    A find() plus a Python loop rather than an aggregation pipeline: Cosmos DB's
    Mongo 4.2 surface supports only a subset of aggregation operators, and the
    order volume does not justify the risk.
    """
    sku = sku.strip().upper()
    coll = orders_collection()
    total_orders = coll.estimated_document_count()

    units = revenue = 0.0
    matching = 0
    for doc in coll.find({"items.sku": sku}, {"items": 1}):
        matching += 1
        for item in doc.get("items") or []:
            if (item.get("sku") or "").upper() == sku:
                q = item.get("quantity") or 0
                units += q
                revenue += (item.get("price") or 0) * q

    out = {"sku": sku, "orders_containing_sku": matching,
           "units_sold": int(units), "revenue": round(revenue, 2),
           "total_orders_in_database": total_orders}
    if total_orders == 0:
        out["note"] = ("The orders collection is empty. RoboShop records a sale "
                       "only when a checkout completes (payment -> Service Bus "
                       "-> orders), and this environment has had none. There is "
                       "no sales history to report.")
    return out


def get_recent_orders(limit=5):
    """Most recent orders, newest first. Live read."""
    limit = max(1, min(int(limit or 5), 25))
    coll = orders_collection()
    total = coll.estimated_document_count()
    if total == 0:
        return {"orders_found": 0, "total_orders_in_database": 0,
                "note": ("The orders collection is empty -- no checkout has ever "
                         "completed in this environment.")}
    docs = list(coll.find({}, {"userName": 1, "total": 1, "status": 1,
                               "shippingCity": 1, "orderDate": 1, "items": 1})
                .sort("orderDate", -1).limit(limit))
    orders = [{
        "orderId": str(d.get("_id")),
        "customer": d.get("userName") or "(unknown)",
        "total": d.get("total"),
        "status": d.get("status"),
        "shippingCity": d.get("shippingCity"),
        "orderDate": str(d.get("orderDate")),
        "lineItems": len(d.get("items") or []),
    } for d in docs]
    return {"orders_found": len(orders), "total_orders_in_database": total,
            "orders": orders}


# ------------------------------------------------- schemas handed to the model
TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "get_product",
        "description": ("Look up a RoboShop product in the live catalogue "
                        "database by SKU (e.g. ROB007) or by name. Returns "
                        "price, category, description and stock."),
        "parameters": {"type": "object", "properties": {
            "sku": {"type": "string", "description": "Product SKU, e.g. ROB007"},
            "name": {"type": "string", "description": "Full or partial product name"},
        }}}},
    {"type": "function", "function": {
        "name": "get_stock",
        "description": ("Current stock level for one SKU, read live from the "
                        "catalogue database. Use for any question about "
                        "availability or units remaining."),
        "parameters": {"type": "object", "properties": {
            "sku": {"type": "string", "description": "Product SKU, e.g. ROB007"},
        }, "required": ["sku"]}}},
    {"type": "function", "function": {
        "name": "get_sales_for_sku",
        "description": ("Units sold and revenue for one SKU, from the live "
                        "orders database. Use for any question about sales, "
                        "revenue or how well a product is selling."),
        "parameters": {"type": "object", "properties": {
            "sku": {"type": "string", "description": "Product SKU, e.g. ROB007"},
        }, "required": ["sku"]}}},
    {"type": "function", "function": {
        "name": "get_recent_orders",
        "description": ("The most recent RoboShop orders, newest first, from "
                        "the live orders database."),
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer", "description": "How many to return (1-25)"},
        }}}},
]

DISPATCH = {
    "get_product": get_product,
    "get_stock": get_stock,
    "get_sales_for_sku": get_sales_for_sku,
    "get_recent_orders": get_recent_orders,
}


def close():
    global _mysql_conn, _mongo_client
    if _mysql_conn is not None:
        _mysql_conn.close()
        _mysql_conn = None
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
