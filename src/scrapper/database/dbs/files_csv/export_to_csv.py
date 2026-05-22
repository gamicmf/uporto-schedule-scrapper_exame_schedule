import sqlite3
import csv
import os

# ---- CONFIG ----
DB_PATH = "./database.db"       # path to your database.db
OUTPUT_DIR = "./csv_export"     # folder where CSVs will be saved
# ----------------

os.makedirs(OUTPUT_DIR, exist_ok=True)

con = sqlite3.connect(DB_PATH)
cur = con.cursor()

# Get all table names
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cur.fetchall()]

print(f"Found {len(tables)} tables: {tables}\n")

for table in tables:
    # Get all rows
    cur.execute(f"SELECT * FROM {table}")
    rows = cur.fetchall()

    # Get column names
    col_names = [description[0] for description in cur.description]

    csv_path = os.path.join(OUTPUT_DIR, f"{table}.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(col_names)
        writer.writerows(rows)

    print(f"Exported {table}.csv — {len(rows)} rows, {len(col_names)} columns")

con.close()
print(f"\nAll CSVs saved to: {os.path.abspath(OUTPUT_DIR)}/")
