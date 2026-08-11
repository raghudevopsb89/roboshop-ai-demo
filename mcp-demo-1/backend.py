"""Data access for the RoboShop MCP server.

This is the only place database credentials exist. Nothing that connects here
ever leaves the process -- the whole point of the demo is that a client gets
four specific questions it may ask, not a database login.

Two backends:

  live    (default)  Azure MySQL Flexible Server + Cosmos DB for MongoDB.
                     Only reachable from inside workstation-vnet, i.e. the VM.
  sqlite             The roboshop.db snapshot from rag-demo-4. Runs anywhere,
                     so you can rehearse the demo on a laptop with no VNet, no
                     credentials and no drivers installed.

Same four functions either way, same return shapes, so server.py does not care
which is in use.
"""
import os
import sqlite3

BACKEND = os.environ.get("ROBOSHOP_BACKEND", "live").lower()

# ---- live: Azure MySQL (catalogue) + Cosmos MongoDB (orders) -------------
MYSQL_HOST = os.environ.get("MYSQL_HOST", "")
MYSQL_USER = os.environ.get("MYSQL_USER", "roboshopadmin")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "catalogue")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_TLS = os.environ.get("MYSQL_TLS", "true").lower() not in ("false", "0", "no")
MYSQL_SSL_CA = os.environ.get("MYSQL_SSL_CA", "/etc/pki/tls/certs/ca-bundle.crt")

MONGO_URL = os.environ.get("MONGO_URL", "")
MONGO_DB = os.environ.get("MONGO_DB", "orders")
MONGO_COLLECTION = os.environ.get("MONGO_COLLECTION", "orders")
MONGO_TIMEOUT_MS = int(os.environ.get("MONGO_TIMEOUT_MS", "8000"))

# ---- sqlite: the rag-demo-4 snapshot ------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
SQLITE_PATH = os.environ.get(
    "ROBOSHOP_SQLITE", os.path.join(_HERE, "..", "rag-demo-4", "roboshop.db"))

_mysql_conn = None
_mongo_client = None


class ConfigError(RuntimeError):
    """Raised at startup so the server refuses to boot half-configured."""


def describe():
    """Secret-free one-liner for the startup banner and the health endpoint."""
    if BACKEND == "sqlite":
        return f"sqlite:{os.path.abspath(SQLITE_PATH)}"
    mongo = MONGO_URL.split("@")[-1].split("/")[0] if "@" in MONGO_URL else "(unset)"
    return (f"mysql:{MYSQL_USER}@{MYSQL_HOST or '(unset)'}/{MYSQL_DATABASE} "
            f"mongo:{mongo}/{MONGO_DB}")


def check_config():
    """Fail fast and loudly rather than at the first tool call."""
    if BACKEND == "sqlite":
        if not os.path.exists(SQLITE_PATH):
            raise ConfigError(
                f"sqlite backend selected but {os.path.abspath(SQLITE_PATH)} "
                f"does not exist.\nBuild it:  cd ../rag-demo-4 && python3 setup_db.py"
                f"\nOr point at another file with ROBOSHOP_SQLITE=/path/to.db")
        return
    if BACKEND != "live":
        raise ConfigError(f"ROBOSHOP_BACKEND must be 'live' or 'sqlite', got {BACKEND!r}")
    gaps = [n for n in ("MYSQL_HOST", "MYSQL_PASSWORD", "MONGO_URL")
            if not globals()[n]]
    if gaps:
        raise ConfigError(
            "live backend is missing: " + ", ".join(gaps) + "\n"
            "These come from the azure-services stack:\n"
            "  cd ../../azure-services/infra\n"
            "  export MYSQL_HOST=$(terraform output -raw mysql_host)\n"
            "  export MYSQL_PASSWORD='RoboShop@1'\n"
            "  export MONGO_URL=$(terraform output -json mongo_urls | "
            "python3 -c 'import json,sys; print(json.load(sys.stdin)[\"orders\"])')\n"
            "Or rehearse without them:  ROBOSHOP_BACKEND=sqlite")


# ------------------------------------------------------------- connections
def _mysql():
    global _mysql_conn
    if _mysql_conn is not None:
        return _mysql_conn
    import pymysql
    kwargs = dict(host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
                  password=MYSQL_PASSWORD, database=MYSQL_DATABASE,
                  cursorclass=pymysql.cursors.DictCursor,
                  connect_timeout=10, charset="utf8mb4")
    if MYSQL_TLS:
        kwargs["ssl_ca"] = MYSQL_SSL_CA
    _mysql_conn = pymysql.connect(**kwargs)
    return _mysql_conn


def _orders():
    global _mongo_client
    if _mongo_client is None:
        from pymongo import MongoClient
        _mongo_client = MongoClient(MONGO_URL,
                                    serverSelectionTimeoutMS=MONGO_TIMEOUT_MS,
                                    connectTimeoutMS=MONGO_TIMEOUT_MS)
    return _mongo_client[MONGO_DB][MONGO_COLLECTION]


def _sqlite():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _query_one(sql_mysql, sql_sqlite, params):
    """Run a single-row lookup against whichever backend is configured."""
    if BACKEND == "sqlite":
        conn = _sqlite()
        try:
            row = conn.execute(sql_sqlite, params).fetchone()
        finally:
            conn.close()
        return dict(row) if row else None
    with _mysql().cursor() as cur:
        cur.execute(sql_mysql, params)
        return cur.fetchone()


# ------------------------------------------------------------------- tools
def get_product(sku=None, name=None):
    if not sku and not name:
        return {"error": "provide either sku or name"}
    cols = "sku, name, description, price, category, stock"
    if sku:
        row = _query_one(f"SELECT {cols} FROM products WHERE sku = %s",
                         f"SELECT {cols} FROM products WHERE sku = ?",
                         (sku.strip().upper(),))
    else:
        row = _query_one(f"SELECT {cols} FROM products WHERE name LIKE %s LIMIT 1",
                         f"SELECT {cols} FROM products WHERE name LIKE ? LIMIT 1",
                         (f"%{name.strip()}%",))
    if not row:
        return {"found": False, "query": sku or name}
    row["price"] = float(row["price"])
    return {"found": True, **row}


def get_stock(sku):
    row = _query_one("SELECT sku, name, stock FROM products WHERE sku = %s",
                     "SELECT sku, name, stock FROM products WHERE sku = ?",
                     (sku.strip().upper(),))
    return {"found": True, **row} if row else {"found": False, "sku": sku}


_EMPTY_NOTE = ("No orders exist. RoboShop records a sale only when a checkout "
               "completes (payment -> Service Bus -> orders), and this "
               "environment has had none. There is no sales history to report.")


def get_sales_for_sku(sku):
    sku = sku.strip().upper()
    if BACKEND == "sqlite":
        # The snapshot carries products and cities only -- no orders table.
        # That matches live, where the collection is empty anyway.
        return {"sku": sku, "orders_containing_sku": 0, "units_sold": 0,
                "revenue": 0.0, "total_orders_in_database": 0, "note": _EMPTY_NOTE}

    coll = _orders()
    total = coll.estimated_document_count()
    units = revenue = 0.0
    matching = 0
    for doc in coll.find({"items.sku": sku}, {"items": 1}):
        matching += 1
        for item in doc.get("items") or []:
            if (item.get("sku") or "").upper() == sku:
                q = item.get("quantity") or 0
                units += q
                revenue += (item.get("price") or 0) * q
    out = {"sku": sku, "orders_containing_sku": matching, "units_sold": int(units),
           "revenue": round(revenue, 2), "total_orders_in_database": total}
    if total == 0:
        out["note"] = _EMPTY_NOTE
    return out


def get_recent_orders(limit=5):
    limit = max(1, min(int(limit or 5), 25))
    if BACKEND == "sqlite":
        return {"orders_found": 0, "total_orders_in_database": 0, "note": _EMPTY_NOTE}

    coll = _orders()
    total = coll.estimated_document_count()
    if total == 0:
        return {"orders_found": 0, "total_orders_in_database": 0, "note": _EMPTY_NOTE}
    docs = list(coll.find({}, {"userName": 1, "total": 1, "status": 1,
                               "shippingCity": 1, "orderDate": 1, "items": 1})
                .sort("orderDate", -1).limit(limit))
    orders = [{"orderId": str(d.get("_id")),
               "customer": d.get("userName") or "(unknown)",
               "total": d.get("total"), "status": d.get("status"),
               "shippingCity": d.get("shippingCity"),
               "orderDate": str(d.get("orderDate")),
               "lineItems": len(d.get("items") or [])} for d in docs]
    return {"orders_found": len(orders), "total_orders_in_database": total,
            "orders": orders}


def close():
    global _mysql_conn, _mongo_client
    if _mysql_conn is not None:
        _mysql_conn.close()
        _mysql_conn = None
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
