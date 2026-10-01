import pyodbc

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

# Saari tables ke naam nikaalein
cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
tables = cursor.fetchall()

print("📋 'cpms' database mein yeh tables hain:")
for table in tables:
    print(f"  - {table[0]}")

conn.close()