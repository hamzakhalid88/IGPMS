import pyodbc
import pandas as pd

conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=192.168.10.98,2433;"
    "DATABASE=cpms;"
    "UID=python_app;"
    "PWD=Python@2024#;"
    "Encrypt=no;"
)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# ---- 1. BigCartonInfo ki Structure (Columns) ----
print("="*60)
print("📦 ODM_BigCartonInfo TABLE STRUCTURE (Columns):")
cursor.execute("SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'ODM_BigCartonInfo' ORDER BY ORDINAL_POSITION")
for row in cursor.fetchall():
    print(f"  - {row[0]} ({row[1]}) Nullable: {row[2]}")

# ---- 2. MidCartonInfo ki Structure ----
print("\n" + "="*60)
print("📦 ODM_MidCartonInfo TABLE STRUCTURE (Columns):")
cursor.execute("SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'ODM_MidCartonInfo' ORDER BY ORDINAL_POSITION")
for row in cursor.fetchall():
    print(f"  - {row[0]} ({row[1]}) Nullable: {row[2]}")

# ---- 3. Current Counter Tables ka Data (Yahan se ID generate hoti hai) ----
print("\n" + "="*60)
print("🔢 ODM_CurrentBigCartonid (Current Counter Value):")
cursor.execute("SELECT * FROM ODM_CurrentBigCartonid")
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"  {row}")
else:
    print("  (Table empty)")

print("\n" + "="*60)
print("🔢 ODM_CurrentMidcartonid (Current Counter Value):")
cursor.execute("SELECT * FROM ODM_CurrentMidcartonid")
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"  {row}")
else:
    print("  (Table empty)")

# ---- 4. Carton se related Stored Procedures (Agar ID yahan generate hoti hai) ----
print("\n" + "="*60)
print("⚙️ Stored Procedures related to 'Carton':")
cursor.execute("SELECT name FROM sys.procedures WHERE name LIKE '%Carton%' OR name LIKE '%BigCarton%' OR name LIKE '%MidCarton%'")
procs = cursor.fetchall()
if procs:
    for p in procs:
        print(f"  - {p[0]}")
else:
    print("  (Koi SP nahi mili)")

conn.close()
print("\n✅ Inspection complete!")