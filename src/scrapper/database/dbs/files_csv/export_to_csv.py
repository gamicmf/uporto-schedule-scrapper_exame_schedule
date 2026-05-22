import sqlite3
import os
from openpyxl import Workbook

# ── Config ──────────────────────────────────────────────
DB_PATH = "../database.db"
OUTPUT_FILE = "./database_export.xlsx"
# ────────────────────────────────────────────────────────

def export_to_excel(db_path, output_file):
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    # Get all table names
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]

    print(f"Found {len(tables)} tables: {tables}\n")

    wb = Workbook()
    wb.remove(wb.active)  # remove default empty sheet

    for table in tables:
        # Get column names
        cur.execute(f"PRAGMA table_info({table})")
        columns = [row[1] for row in cur.fetchall()]

        # Get all rows
        cur.execute(f"SELECT * FROM {table}")
        rows = cur.fetchall()

        # Create a sheet per table
        ws = wb.create_sheet(title=table)
        ws.append(columns)  # header row
        for row in rows:
            ws.append(list(row))

        print(f"✓ Sheet '{table}' → {len(rows)} rows, {len(columns)} columns")

    wb.save(output_file)
    con.close()
    print(f"\nExcel file saved to: {os.path.abspath(output_file)}")

if __name__ == "__main__":
    export_to_excel(DB_PATH, OUTPUT_FILE)