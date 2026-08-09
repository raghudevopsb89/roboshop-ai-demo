"""Step 1: load the RoboShop SQL data into a local SQLite database.

The data lives in two files next to this script -- catalogue.sql and
shipping.sql -- lifted from the RoboShop services. They are MySQL dumps and are
INSERT-only (no CREATE TABLE), so this script supplies the two table
definitions itself and then replays the inserts.

Keeping the schema here rather than in a third .sql file means catalogue.sql and
shipping.sql stay the single source of truth for the *data*: drop in new rows and
re-run, nothing else to keep in sync.

A few MySQL-isms are rewritten on the way in -- see translate().

Usage:
    python3 setup_db.py
"""
import os
import re
import sqlite3
import sys

from common import DB_PATH, rule

HERE = os.path.dirname(os.path.abspath(__file__))

# The INSERT files carry no DDL, so the tables are declared here. Column names
# and order match the INSERT column lists in the .sql files exactly.
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

# (label, filename, table it populates)
SOURCES = [
    ("catalogue products", "catalogue.sql", "products"),
    ("shipping cities",    "shipping.sql",  "cities"),
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
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    print(rule("LOADING ROBOSHOP SQL INTO SQLITE"))
    print(f"target db: {DB_PATH}\n")

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
