"""Step 1: build the SQLite database from schema.sql."""
import os
import sqlite3

from common import DB_PATH, rule

HERE = os.path.dirname(os.path.abspath(__file__))

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

with open(os.path.join(HERE, "schema.sql")) as f:
    sql = f.read()

conn = sqlite3.connect(DB_PATH)
conn.executescript(sql)
conn.commit()

print(rule("SQL DATABASE CREATED"))
print(f"path: {DB_PATH}\n")
for (table,) in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
):
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  {table:<20} {n:>3} rows")

print("\nSample -- APAC revenue for FY2024-Q3:")
for row in conn.execute(
    "SELECT product_line, revenue_usd, deals_closed FROM quarterly_revenue "
    "WHERE region='APAC' AND fiscal_quarter='FY2024-Q3' ORDER BY revenue_usd DESC"
):
    print(f"  {row[0]:<12} ${row[1]:>12,.0f}   {row[2]:>2} deals")

total = conn.execute(
    "SELECT SUM(revenue_usd) FROM quarterly_revenue "
    "WHERE region='APAC' AND fiscal_quarter='FY2024-Q3'"
).fetchone()[0]
print(f"  {'TOTAL':<12} ${total:>12,.0f}")
conn.close()
