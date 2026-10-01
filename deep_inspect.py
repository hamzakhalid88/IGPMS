import pyodbc

conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=192.168.10.98,2433;"
    "DATABASE=cpms;"
    "UID=python_app;"
    "PWD=Python@2024#;"
    "Encrypt=no;"
)

MID_CARTON_ID = "P302-SH3SHF2404150019"
BIG_CARTON_ID = "PLT240310286"

try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    print("✅ Connected!\n")
    print("=" * 80)

    # ---- 1. Check ODM_Packing (Most Likely) ----
    print("📦 1. Checking 'ODM_Packing' table...")
    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'ODM_Packing'")
    cols_pack = [row[0] for row in cursor.fetchall()]
    print(f"   Columns: {cols_pack}")
    
    # Search for the MidCartonID
    cursor.execute("SELECT * FROM ODM_Packing WHERE MidCartonID = ?", (MID_CARTON_ID,))
    rows = cursor.fetchall()
    if rows:
        print(f"   ✅ FOUND {len(rows)} records in ODM_Packing!")
        # Print headers
        headers = [desc[0] for desc in cursor.description]
        print("   " + " | ".join(headers))
        for row in rows:
            print(f"   {row}")
    else:
        print("   ❌ No records found in ODM_Packing.")

    print("\n" + "=" * 80)

    # ---- 2. Check ODM_PalletPacking ----
    print("📦 2. Checking 'ODM_PalletPacking' table...")
    cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'ODM_PalletPacking'")
    cols_pallet = [row[0] for row in cursor.fetchall()]
    print(f"   Columns: {cols_pallet}")
    
    cursor.execute("SELECT * FROM ODM_PalletPacking WHERE BigCartonID = ?", (BIG_CARTON_ID,))
    rows = cursor.fetchall()
    if rows:
        print(f"   ✅ FOUND {len(rows)} records in ODM_PalletPacking!")
        headers = [desc[0] for desc in cursor.description]
        print("   " + " | ".join(headers))
        for row in rows:
            print(f"   {row}")
    else:
        print("   ❌ No records found in ODM_PalletPacking.")

    print("\n" + "=" * 80)

    # ---- 3. Check ODM_SNLinkIMEI ----
    print("🔗 3. Checking 'ODM_SNLinkIMEI' table...")
    try:
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'ODM_SNLinkIMEI'")
        cols_sn = [row[0] for row in cursor.fetchall()]
        print(f"   Columns: {cols_sn}")
        
        # Try to find any column that matches our IDs
        query_parts = []
        for col in cols_sn:
            if 'Carton' in col or 'ID' in col:
                query_parts.append(f"{col} = ? OR {col} = ?")
        
        if query_parts:
            full_query = f"SELECT * FROM ODM_SNLinkIMEI WHERE " + " OR ".join(query_parts)
            # Execute with both IDs
            params = []
            for _ in query_parts:
                params.extend([MID_CARTON_ID, BIG_CARTON_ID])
            cursor.execute(full_query, params)
            rows = cursor.fetchall()
            if rows:
                print(f"   ✅ FOUND {len(rows)} records in ODM_SNLinkIMEI!")
                headers = [desc[0] for desc in cursor.description]
                print("   " + " | ".join(headers))
                for row in rows:
                    print(f"   {row}")
            else:
                print("   ❌ No records found.")
        else:
            print("   ⚠️ No relevant columns found to search.")
    except Exception as e:
        print(f"   ⚠️ Table may not exist or error: {e}")

    print("\n" + "=" * 80)

    # ---- 4. Check ODM_BoundImei ----
    print("🔗 4. Checking 'ODM_BoundImei' table...")
    try:
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'ODM_BoundImei'")
        cols_bound = [row[0] for row in cursor.fetchall()]
        print(f"   Columns: {cols_bound}")
        
        query_parts = []
        for col in cols_bound:
            if 'Carton' in col or 'ID' in col:
                query_parts.append(f"{col} = ? OR {col} = ?")
        
        if query_parts:
            full_query = f"SELECT * FROM ODM_BoundImei WHERE " + " OR ".join(query_parts)
            params = []
            for _ in query_parts:
                params.extend([MID_CARTON_ID, BIG_CARTON_ID])
            cursor.execute(full_query, params)
            rows = cursor.fetchall()
            if rows:
                print(f"   ✅ FOUND {len(rows)} records in ODM_BoundImei!")
                headers = [desc[0] for desc in cursor.description]
                print("   " + " | ".join(headers))
                for row in rows:
                    print(f"   {row}")
            else:
                print("   ❌ No records found.")
        else:
            print("   ⚠️ No relevant columns found to search.")
    except Exception as e:
        print(f"   ⚠️ Table may not exist or error: {e}")

    print("\n" + "=" * 80)

    # ---- 5. Check IMEI table (full data sample) ----
    print("📱 5. Sampling 'IMEI' table (to understand data format)...")
    cursor.execute("SELECT TOP 3 * FROM IMEI")
    rows = cursor.fetchall()
    if rows:
        headers = [desc[0] for desc in cursor.description]
        print("   Sample rows (Columns: " + " | ".join(headers) + ")")
        for row in rows:
            print(f"   {row}")
    else:
        print("   ⚠️ IMEI table is completely empty!")

    conn.close()
    print("\n✅ Done!")

except Exception as e:
    print(f"❌ Error: {e}")