import pyodbc

DB_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=192.168.10.98,2433;"
    "DATABASE=cpms;"
    "UID=python_app;"
    "PWD=Python@2024#;"
    "Encrypt=no;"
)

# Yeh do values search karenge (CID aur pehla IMEI)
SEARCH_VALUES = ["WP-SH3IMPRO266120046", "357015922125304", "IMPR483203006255"]

def brute_force_search():
    try:
        conn = pyodbc.connect(DB_STR)
        cursor = conn.cursor()
        print("🔍 Brute-Force Search Starting...")
        print("=" * 80)

        # Saari tables ki list lein
        cursor.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'")
        tables = cursor.fetchall()

        for schema, table in tables:
            # Har table ke columns ki list lein
            cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table}' AND TABLE_SCHEMA = '{schema}'")
            cols = [row[0] for row in cursor.fetchall()]
            
            for col in cols:
                # Har column mein har value search karein
                for val in SEARCH_VALUES:
                    try:
                        # Exact match (trimmed)
                        query = f"SELECT COUNT(*) FROM [{schema}].[{table}] WHERE LTRIM(RTRIM({col})) = ?"
                        cursor.execute(query, (val,))
                        count = cursor.fetchone()[0]
                        if count > 0:
                            print(f"✅ FOUND: Table = [{schema}].[{table}], Column = {col}")
                            print(f"   Value = '{val}' appears {count} time(s).")
                            # Agar match mila toh sample data bhi dikhayein
                            sample_query = f"SELECT TOP 1 * FROM [{schema}].[{table}] WHERE LTRIM(RTRIM({col})) = ?"
                            cursor.execute(sample_query, (val,))
                            sample_row = cursor.fetchone()
                            if sample_row:
                                print(f"   Sample Row: {sample_row}")
                            print("-" * 60)
                    except Exception as e:
                        # Some columns might cause errors (like binary, etc.) - ignore
                        pass

        conn.close()
        print("\n" + "=" * 80)
        print("📌 Search Complete! Agar kuch mila toh upar list mein dikhega.")
        print("   Agar kuch nahi mila, toh software shayad 'VIEW' ya 'STORED PROCEDURE' use kar raha hai.")
        print("   Aap SSMS mein yeh query chala kar dekh lein:")
        print("   SELECT * FROM INFORMATION_SCHEMA.VIEWS;")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    brute_force_search()