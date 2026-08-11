"""Run this before ask_live.py. Checks the Foundry endpoint and both databases.

The databases are private to workstation-vnet, so the likeliest failure is
network or DNS -- and inside a tool-calling conversation that surfaces as a
confusing model error. This isolates it.

Usage:
    python3 check_conn.py
"""
import socket
import sys
from urllib.parse import urlsplit

import tools

OK, BAD, WARN = "  ok  ", " FAIL ", " warn "


def line(status, label, detail=""):
    print(f"[{status}] {label}" + (f"\n         {detail}" if detail else ""))


def check_dns_and_port(host, port, label):
    try:
        ip = socket.gethostbyname(host)
    except socket.gaierror as e:
        line(BAD, f"{label} DNS", f"cannot resolve {host}: {e}\n"
                                  "         Private DNS zone not linked to this VNet?")
        return False
    private = ip.startswith(("10.", "192.168.", "172."))
    line(OK, f"{label} DNS", f"{host} -> {ip}"
         + ("" if private else "  (public IP -- expected a private endpoint)"))
    try:
        with socket.create_connection((host, port), timeout=8):
            line(OK, f"{label} TCP", f"port {port} open")
            return True
    except OSError as e:
        line(BAD, f"{label} TCP", f"cannot connect to {host}:{port}: {e}\n"
                                  "         Run this on the VM inside "
                                  "workstation-vnet.")
        return False


def check_foundry():
    print("\n--- Foundry (chat model) ---")
    import common
    if not common.AZURE_BASE or not common.AZURE_KEY:
        line(BAD, "config", 'AZURE_BASE / AZURE_KEY not set -- '
                            'cd ../infra && eval "$(make -s env)"')
        return False
    try:
        reply = common.chat("Reply with the single word: ok")
        line(OK, "chat", f"{common.CHAT_MODEL} responded: {reply[:40]!r}")
        return True
    except SystemExit as e:
        line(BAD, "chat", str(e)[:300])
        return False


def check_mysql():
    print("\n--- MySQL (catalogue: products, live stock) ---")
    if tools.missing("MYSQL_HOST", "MYSQL_PASSWORD"):
        line(BAD, "config", "MYSQL_HOST / MYSQL_PASSWORD not set")
        return False
    if not check_dns_and_port(tools.MYSQL_HOST, tools.MYSQL_PORT, "mysql"):
        return False
    try:
        import pymysql  # noqa: F401
    except ImportError:
        line(BAD, "driver", "pymysql not installed -- run: make venv")
        return False
    try:
        with tools.mysql().cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM products")
            n = cur.fetchone()["n"]
            cur.execute("SELECT sku, name, stock FROM products ORDER BY sku LIMIT 3")
            rows = cur.fetchall()
        line(OK, "query", f"products table has {n} rows")
        for r in rows:
            print(f"           {r['sku']}  {r['name'][:28]:<28} stock={r['stock']}")
        return True
    except Exception as e:
        hint = ""
        s = str(e)
        if "SSL" in s or "certificate" in s.lower():
            hint = ("\n         TLS problem. Check MYSQL_SSL_CA, or set "
                    "MYSQL_TLS=false for a local plaintext MySQL.")
        elif "Access denied" in s:
            hint = "\n         Wrong user/password, or no rights on this database."
        elif "Unknown database" in s:
            hint = f"\n         Database '{tools.MYSQL_DATABASE}' does not exist."
        line(BAD, "query", f"{type(e).__name__}: {e}{hint}")
        return False


def check_mongo():
    print("\n--- MongoDB / Cosmos (orders: the sale data) ---")
    if tools.missing("MONGO_URL"):
        line(BAD, "config", "MONGO_URL not set")
        return False
    parts = urlsplit(tools.MONGO_URL)
    if parts.hostname:
        # Bail here rather than let pymongo burn its full timeout on a host we
        # already know is unreachable.
        if not check_dns_and_port(parts.hostname, parts.port or 10255, "mongo"):
            return False
    try:
        from pymongo import MongoClient  # noqa: F401
    except ImportError:
        line(BAD, "driver", "pymongo not installed -- run: make venv")
        return False
    try:
        coll = tools.orders_collection()
        n = coll.estimated_document_count()
        line(OK, "query", f"{tools.MONGO_DB}.{tools.MONGO_COLLECTION} has "
                          f"{n} documents")
        if n == 0:
            line(WARN, "no sale data",
                 "Empty, and that is expected: orders are written only when a\n"
                 "         checkout completes, and nothing seeds them. The sales\n"
                 "         tools will honestly report zero.")
        else:
            for d in coll.find({}, {"total": 1, "status": 1}).limit(3):
                print(f"           {str(d.get('_id'))[:24]}  "
                      f"total={d.get('total')}  status={d.get('status')}")
        return True
    except Exception as e:
        line(BAD, "query", f"{type(e).__name__}: {e}\n"
                           "         Cosmos is private-endpoint only; run from "
                           "inside the VNet.")
        return False


def main():
    print("RoboShop demo 4 -- live data connectivity check")
    print(tools.summary())
    results = [check_foundry(), check_mysql(), check_mongo()]
    print()
    if all(results):
        print("all reachable -- run: python3 ask_live.py 1")
        return 0
    print("fix the FAIL lines above first")
    return 1


if __name__ == "__main__":
    sys.exit(main())
