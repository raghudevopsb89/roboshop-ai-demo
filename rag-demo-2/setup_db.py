"""Step 1: mirror the real RoboShop SQL data into a local SQLite database.

Unlike rag-demo-1 -- which invented a company -- this demo indexes REAL data from
the azure-services monorepo. We read the actual .sql files the services ship with
and replay them into a local roboshop.db, so the demo never forks the data and
never needs Azure, MySQL or the network.

Those files are MySQL, so a handful of dialect fixes are applied on the way in
(see translate()). Only DDL/DML we actually use is handled -- this is a demo
loader, not a general MySQL-to-SQLite porting tool.

Usage:
    python3 setup_db.py
    AZURE_REPO=/path/to/azure-services python3 setup_db.py
"""
import os
import re
import sqlite3
import sys

from common import AZURE_REPO, DB_PATH, rule

# (label, path relative to the azure-services repo root)
SOURCES = [
    ("catalogue schema", "apps/roboshop-catalogue/db/schema.sql"),
    ("catalogue data",   "apps/roboshop-catalogue/db/master-data.sql"),
    ("cities schema",    "apps/roboshop-shipping/db/schema.sql"),
    ("cities data",      "apps/roboshop-shipping/src/main/resources/data.sql"),
]


def translate(sql):
    """MySQL -> SQLite, for the subset of syntax these files actually use."""
    # SQLite has one database per file: CREATE DATABASE / USE have no meaning.
    sql = re.sub(r"(?im)^\s*CREATE\s+DATABASE.*?;\s*$", "", sql)
    sql = re.sub(r"(?im)^\s*USE\s+\w+\s*;\s*$", "", sql)
    # AUTO_INCREMENT is only legal on INTEGER PRIMARY KEY in SQLite.
    sql = re.sub(r"(?i)\bBIGINT\s+AUTO_INCREMENT\s+PRIMARY\s+KEY\b",
                 "INTEGER PRIMARY KEY AUTOINCREMENT", sql)
    # INSERT IGNORE -> INSERT OR IGNORE
    sql = re.sub(r"(?i)\bINSERT\s+IGNORE\s+INTO\b", "INSERT OR IGNORE INTO", sql)
    # Named UNIQUE KEY constraints -> plain UNIQUE(...)
    sql = re.sub(r"(?i)\bUNIQUE\s+KEY\s+\w+\s*\(", "UNIQUE (", sql)
    return sql


def main():
    if not os.path.isdir(AZURE_REPO):
        sys.exit(
            f"azure-services repo not found at: {AZURE_REPO}\n"
            f"Set AZURE_REPO=/path/to/azure-services and re-run."
        )

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)

    print(rule("MIRRORING ROBOSHOP SQL INTO SQLITE"))
    print(f"source repo: {AZURE_REPO}")
    print(f"target db:   {DB_PATH}\n")

    for label, rel in SOURCES:
        path = os.path.join(AZURE_REPO, rel)
        if not os.path.exists(path):
            sys.exit(f"missing source file: {path}")
        with open(path) as f:
            conn.executescript(translate(f.read()))
        print(f"  loaded {label:<18} <- {rel}")
    conn.commit()

    print("\ntables:")
    for (table,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<20} {n:>3} rows")

    print("\nSample -- three products:")
    for row in conn.execute(
        "SELECT sku, name, price, category, stock FROM products "
        "ORDER BY price DESC LIMIT 3"
    ):
        print(f"  {row[0]:<8} {row[1]:<28} ${row[2]:>8,.2f}  {row[3]:<12} {row[4]:>3} in stock")

    print("\nSample -- three shipping destinations:")
    for row in conn.execute(
        "SELECT country_code, city, region FROM cities ORDER BY city LIMIT 3"
    ):
        print(f"  {row[0]:<3} {row[1]:<16} {row[2]}")

    conn.close()


if __name__ == "__main__":
    main()
