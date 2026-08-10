"""Run this FIRST. It proves the two databases are reachable, before any model
is involved.

Both stores are private to workstation-vnet, so the single most likely failure
is a network or DNS one -- and if you only ever run ask_live.py, that surfaces as
a confusing tool error buried in a model conversation. This script isolates it.

Usage:
    python3 check_conn.py
"""
import socket
import sys
from urllib.parse import urlsplit

import config

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
    private = ip.startswith(("10.", "192.168.")) or ip.startswith("172.")
    line(OK, f"{label} DNS", f"{host} -> {ip}"
         + ("" if private else "  (public IP -- expected a private endpoint address)"))
    try:
        with socket.create_connection((host, port), timeout=8):
            line(OK, f"{label} TCP", f"port {port} open")
            return True
    except OSError as e:
        line(BAD, f"{label} TCP", f"cannot connect to {host}:{port}: {e}\n"
                                  "         Are you running this on the VM inside "
                                  "workstation-vnet? NSG rules?")
        return False


def check_mysql():
    print("\n--- MySQL (catalogue: products, live stock) ---")
    if config.missing("MYSQL_HOST", "MYSQL_PASSWORD"):
        line(BAD, "config", "MYSQL_HOST / MYSQL_PASSWORD not set")
        return False
    if not check_dns_and_port(config.MYSQL_HOST, config.MYSQL_PORT, "mysql"):
        return False
    try:
        import pymysql  # noqa: F401
    except ImportError:
        line(BAD, "driver", "pymysql not installed -- run: make venv")
        return False

    import tools
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
        if "SSL" in str(e) or "certificate" in str(e).lower():
            hint = ("\n         TLS problem. Check MYSQL_SSL_CA points at a real CA "
                    "bundle,\n         or set MYSQL_TLS=false for a local plaintext "
                    "MySQL.")
        elif "Access denied" in str(e):
            hint = "\n         Wrong user/password, or the user lacks rights on this DB."
        elif "Unknown database" in str(e):
            hint = f"\n         Database '{config.MYSQL_DATABASE}' does not exist yet."
        line(BAD, "query", f"{type(e).__name__}: {e}{hint}")
        return False


def check_mongo():
    print("\n--- MongoDB / Cosmos (orders: the sale data) ---")
    if config.missing("MONGO_URL"):
        line(BAD, "config", "MONGO_URL not set")
        return False
    parts = urlsplit(config.MONGO_URL)
    if parts.hostname:
        # Bail out here rather than letting pymongo burn its full timeout on a
        # host we already know is unreachable.
        if not check_dns_and_port(parts.hostname, parts.port or 10255, "mongo"):
            return False
    try:
        from pymongo import MongoClient  # noqa: F401
    except ImportError:
        line(BAD, "driver", "pymongo not installed -- run: make venv")
        return False

    import tools
    try:
        coll = tools.orders_collection()
        n = coll.estimated_document_count()
        line(OK, "query", f"{config.MONGO_DB}.{config.MONGO_COLLECTION} "
                          f"has {n} documents")
        if n == 0:
            line(WARN, "no sale data",
                 "The orders collection is empty. That is expected on a fresh\n"
                 "         environment: orders are written only when a checkout\n"
                 "         completes (payment -> Service Bus -> orders), and there\n"
                 "         is no seed script for them anywhere in azure-services.\n"
                 "         The sales tools will honestly report zero.")
        else:
            for d in coll.find({}, {"total": 1, "status": 1}).limit(3):
                print(f"           {str(d.get('_id'))[:24]}  total={d.get('total')}  "
                      f"status={d.get('status')}")
        return True
    except Exception as e:
        line(BAD, "query", f"{type(e).__name__}: {e}\n"
                           "         Cosmos is private-endpoint only; this must run "
                           "from inside the VNet.")
        return False


def main():
    print("RoboShop live-data connectivity check")
    print(config.summary())
    results = [check_mysql(), check_mongo()]
    print()
    if all(results):
        print("both databases reachable -- you can run: python3 ask_live.py 1")
        return 0
    print("at least one database is unreachable; fix the FAIL lines above first")
    return 1


if __name__ == "__main__":
    sys.exit(main())
