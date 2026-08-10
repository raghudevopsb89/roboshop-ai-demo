"""The live tools: real queries against real databases, executed per question.

This is the whole point of demo 3. Demos 1 and 2 answered from text that was
embedded once, at index time -- so a chunk saying "Current stock on hand: 150
units" stays 150 forever, however many people buy one. Here nothing is
pre-computed: every answer runs a query at the moment it is asked.

    stock, prices  ->  MySQL      (catalogue database, products table)
    sale data      ->  MongoDB    (orders database, orders collection)

Note on the sales tools: the orders collection is populated only at runtime, by
OrderListener consuming Service Bus messages that payment publishes. There is no
seed data for it anywhere in azure-services, so on a fresh environment it is
EMPTY. The tools report that honestly -- orders_found: 0 -- and the system prompt
in ask_live.py forbids the model from filling the gap. A truthful "no sales
recorded" is the correct answer, and is exactly what demo 1 could not produce.
"""
import config

# Drivers are imported lazily so that --help and the unit checks still work in a
# bare interpreter with no venv activated.
_mysql_conn = None
_mongo_client = None


# ---------------------------------------------------------------- connections
def mysql():
    """Open (once) a real, authenticated connection to Azure MySQL."""
    global _mysql_conn
    if _mysql_conn is not None:
        return _mysql_conn

    import pymysql

    config.require("MYSQL_HOST", "MYSQL_PASSWORD")
    kwargs = dict(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        database=config.MYSQL_DATABASE,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
        charset="utf8mb4",
    )
    if config.MYSQL_TLS:
        # Passing ssl_ca is what actually switches PyMySQL into TLS mode.
        kwargs["ssl_ca"] = config.MYSQL_SSL_CA
    _mysql_conn = pymysql.connect(**kwargs)
    return _mysql_conn


def mongo():
    """Open (once) a real, authenticated connection to Cosmos DB for MongoDB."""
    global _mongo_client
    if _mongo_client is not None:
        return _mongo_client

    from pymongo import MongoClient

    config.require("MONGO_URL")
    _mongo_client = MongoClient(
        config.MONGO_URL,
        serverSelectionTimeoutMS=config.MONGO_TIMEOUT_MS,
        connectTimeoutMS=config.MONGO_TIMEOUT_MS,
    )
    return _mongo_client


def orders_collection():
    return mongo()[config.MONGO_DB][config.MONGO_COLLECTION]


# --------------------------------------------------------------------- tools
def get_product(sku=None, name=None):
    """Look up one product in the live catalogue by SKU or by (partial) name."""
    if not sku and not name:
        return {"error": "provide either sku or name"}
    with mysql().cursor() as cur:
        if sku:
            cur.execute(
                "SELECT sku, name, description, price, category, stock "
                "FROM products WHERE sku = %s", (sku.strip().upper(),))
        else:
            cur.execute(
                "SELECT sku, name, description, price, category, stock "
                "FROM products WHERE name LIKE %s LIMIT 1", (f"%{name.strip()}%",))
        row = cur.fetchone()
    if not row:
        return {"found": False, "query": sku or name}
    row["price"] = float(row["price"])
    return {"found": True, **row}


def get_stock(sku):
    """Current stock level for one SKU. Read live -- this is the volatile field."""
    with mysql().cursor() as cur:
        cur.execute("SELECT sku, name, stock FROM products WHERE sku = %s",
                    (sku.strip().upper(),))
        row = cur.fetchone()
    if not row:
        return {"found": False, "sku": sku}
    return {"found": True, **row}


def get_sales_for_sku(sku):
    """Units sold and revenue for one SKU, computed from the live orders data.

    Deliberately a find() plus a Python loop rather than an aggregation
    pipeline: Cosmos DB's Mongo 4.2 surface supports only a subset of aggregation
    operators, and the order volume here is tiny. Correctness over cleverness.
    """
    sku = sku.strip().upper()
    coll = orders_collection()
    total_orders = coll.estimated_document_count()

    units = revenue = 0.0
    matching = 0
    for doc in coll.find({"items.sku": sku}, {"items": 1, "orderDate": 1}):
        matching += 1
        for item in doc.get("items") or []:
            if (item.get("sku") or "").upper() == sku:
                q = item.get("quantity") or 0
                units += q
                revenue += (item.get("price") or 0) * q

    out = {
        "sku": sku,
        "orders_containing_sku": matching,
        "units_sold": int(units),
        "revenue": round(revenue, 2),
        "total_orders_in_database": total_orders,
    }
    if total_orders == 0:
        out["note"] = (
            "The orders collection is empty. RoboShop records a sale only when a "
            "checkout completes (payment -> Service Bus -> orders), and this "
            "environment has had none. There is no sales history to report.")
    return out


def get_recent_orders(limit=5):
    """The most recent orders, newest first. Live read from the orders database."""
    limit = max(1, min(int(limit or 5), 25))
    coll = orders_collection()
    total = coll.estimated_document_count()
    if total == 0:
        return {
            "orders_found": 0,
            "total_orders_in_database": 0,
            "note": ("The orders collection is empty -- no checkout has ever "
                     "completed in this environment. There are no orders to list."),
        }

    docs = list(coll.find({}, {"userName": 1, "total": 1, "status": 1,
                               "shippingCity": 1, "orderDate": 1, "items": 1})
                .sort("orderDate", -1).limit(limit))
    orders = []
    for d in docs:
        orders.append({
            "orderId": str(d.get("_id")),
            "customer": d.get("userName") or "(unknown)",
            "total": d.get("total"),
            "status": d.get("status"),
            "shippingCity": d.get("shippingCity"),
            "orderDate": str(d.get("orderDate")),
            "lineItems": len(d.get("items") or []),
        })
    return {"orders_found": len(orders), "total_orders_in_database": total,
            "orders": orders}


# ------------------------------------------------- schemas handed to the model
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_product",
            "description": ("Look up a RoboShop product in the live catalogue "
                            "database by SKU (e.g. ROB007) or by name. Returns "
                            "price, category, description and stock."),
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "Product SKU, e.g. ROB007"},
                    "name": {"type": "string", "description": "Full or partial product name"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock",
            "description": ("Current stock level for one SKU, read live from the "
                            "catalogue database. Use this for any question about "
                            "availability or how many units are left."),
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "Product SKU, e.g. ROB007"},
                },
                "required": ["sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_sales_for_sku",
            "description": ("Units sold and revenue for one SKU, computed from the "
                            "live orders database. Use this for any question about "
                            "sales, revenue or how well a product is selling."),
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {"type": "string", "description": "Product SKU, e.g. ROB007"},
                },
                "required": ["sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_orders",
            "description": ("The most recent RoboShop orders, newest first, read "
                            "live from the orders database. Use this for questions "
                            "about recent sales activity or latest orders."),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer",
                              "description": "How many orders to return (1-25)"},
                },
            },
        },
    },
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
