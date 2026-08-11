"""Build the local roboshop.db used by ROBOSHOP_BACKEND=sqlite.

Only needed for the offline/rehearsal backend. The live backend talks to Azure
MySQL and Cosmos and never touches this file.

The data lives in catalogue.sql and shipping.sql next to this script. They are
MySQL INSERT-only dumps (no CREATE TABLE), so the two table definitions are
supplied here and a few dialect differences are rewritten on the way in.

Usage:
    python3 setup_db.py
"""
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "roboshop.db")

# The INSERT files carry no DDL. Column names and order match the INSERT column
# lists in the .sql files exactly.
SCHEMA = """
DROP TABLE IF EXISTS products;
CREATE TABLE products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sku         TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    description TEXT,
    price       REAL NOT NULL,
    image_url   TEXT,
    category    TEXT,
    stock       INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS cities;
CREATE TABLE cities (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    city         TEXT NOT NULL,
    region       TEXT,
    latitude     REAL,
    longitude    REAL
);
"""

# There is deliberately no `orders` table. Live RoboShop writes an order only
# when a checkout completes, and that collection is empty -- so the sales tools
# reporting zero here is the same answer the live backend gives.

SOURCES = [
    ("catalogue products", "catalogue.sql", "products"),
    ("shipping cities", "shipping.sql", "cities"),
]


def translate(sql):
    """MySQL -> SQLite, for the subset of syntax these files use."""
    sql = re.sub(r"(?im)^\s*CREATE\s+DATABASE.*?;\s*$", "", sql)
    sql = re.sub(r"(?im)^\s*USE\s+\w+\s*;\s*$", "", sql)
    sql = re.sub(r"(?i)\bINSERT\s+IGNORE\s+INTO\b", "INSERT OR IGNORE INTO", sql)
    return sql


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    for label, filename, table in SOURCES:
        path = os.path.join(HERE, filename)
        if not os.path.exists(path):
            sys.exit(f"missing source file: {path}")
        with open(path) as f:
            conn.executescript(translate(f.read()))
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if not n:
            sys.exit(f"{filename} loaded but {table} is empty -- check the file")
        print(f"  loaded {label:<20} <- {filename:<16} {n:>3} rows")

    conn.commit()
    print(f"\nbuilt {DB_PATH}")
    conn.close()


if __name__ == "__main__":
    main()
