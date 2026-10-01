import pyodbc

DB_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=192.168.10.98,2433;"
    "DATABASE=cpms;"
    "UID=python_app;"
    "PWD=Python@2024#;"
    "Encrypt=no;"
)

MID_CARTON_ID = "P302-SH3SHF2404150019"

try:
    conn = pyodbc.connect(DB_STR)
    cursor = conn.cursor()
    print("✅ Connected!\n")
    print("=" * 80)

    # ---- 1. Check Foreign Keys between ODM_Packing and IMEI ----
    print("🔗 1. Foreign Keys between ODM_Packing and IMEI:")
    cursor.execute("""
        SELECT 
            OBJECT_NAME(fk.parent_object_id) AS Parent_Table,
            COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS Parent_Column,
            OBJECT_NAME(fk.referenced_object_id) AS Referenced_Table,
            COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS Referenced_Column
        FROM sys.foreign_keys fk
        INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        WHERE OBJECT_NAME(fk.parent_object_id) = 'ODM_Packing' 
           OR OBJECT_NAME(fk.referenced_object_id) = 'ODM_Packing'
    """)
    fk_rows = cursor.fetchall()
    if fk_rows:
        for row in fk_rows:
            print(f"   ✅ {row.Parent_Table}.{row.Parent_Column} -> {row.Referenced_Table}.{row.Referenced_Column}")
    else:
        print("   ⚠️ ODM_Packing ki koi Foreign Key nahi mili.")

    print("\n" + "=" * 80)

    # ---- 2. Check if there's any FK from IMEI table ----
    print("🔗 2. Foreign Keys on IMEI table:")
    cursor.execute("""
        SELECT 
            OBJECT_NAME(fk.parent_object_id) AS Parent_Table,
            COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS Parent_Column,
            OBJECT_NAME(fk.referenced_object_id) AS Referenced_Table,
            COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS Referenced_Column
        FROM sys.foreign_keys fk
        INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
        WHERE OBJECT_NAME(fk.parent_object_id) = 'IMEI'
    """)
    fk_rows = cursor.fetchall()
    if fk_rows:
        for row in fk_rows:
            print(f"   ✅ {row.Parent_Table}.{row.Parent_Column} -> {row.Referenced_Table}.{row.Referenced_Column}")
    else:
        print("   ⚠️ IMEI table ki koi Foreign Key nahi mili.")

    print("\n" + "=" * 80)

    # ---- 3. IMEI table ke columns and sample data ----
    print("📋 3. IMEI Table Structure & Sample Data:")
    cursor.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'IMEI' ORDER BY ORDINAL_POSITION")
    cols = cursor.fetchall()
    print("   Columns:")
    for col in cols:
        print(f"      - {col[0]} ({col[1]})")
    
    print("\n   Sample 5 rows from IMEI:")
    cursor.execute("SELECT TOP 5 * FROM IMEI")
    rows = cursor.fetchall()
    if rows:
        headers = [desc[0] for desc in cursor.description]
        print("   " + " | ".join(headers))
        for row in rows:
            print(f"   {row}")
    else:
        print("   ⚠️ IMEI table is empty!")

    print("\n" + "=" * 80)

    # ---- 4. Check specific Carton ID in ODM_Packing and IMEI ----
    print(f"📦 4. Checking Carton ID: {MID_CARTON_ID}")
    
    # Get IMEI numbers from ODM_Packing
    cursor.execute("SELECT IMEI FROM ODM_Packing WHERE MidCartonID = ?", (MID_CARTON_ID,))
    packing_imeis = [row[0] for row in cursor.fetchall() if row[0]]
    print(f"   ODM_Packing IMEI count: {len(packing_imeis)}")
    if packing_imeis:
        print(f"   Sample IMEI: {packing_imeis[:3]}")

    # Check these IMEIs in IMEI table
    if packing_imeis:
        # Check in IMEI1 column
        placeholders = ','.join(['?'] * len(packing_imeis))
        query1 = f"SELECT IMEI1, IMEI2, CartonNo FROM IMEI WHERE IMEI1 IN ({placeholders})"
        cursor.execute(query1, packing_imeis)
        imei1_results = cursor.fetchall()
        
        query2 = f"SELECT IMEI1, IMEI2, CartonNo FROM IMEI WHERE IMEI2 IN ({placeholders})"
        cursor.execute(query2, packing_imeis)
        imei2_results = cursor.fetchall()
        
        if imei1_results:
            print(f"   ✅ Found {len(imei1_results)} match in IMEI1 column!")
            for row in imei1_results:
                print(f"      IMEI1: {row[0]}, IMEI2: {row[1]}, CartonNo: {row[2]}")
        else:
            print("   ❌ No matches found in IMEI1 column")
        
        if imei2_results:
            print(f"   ✅ Found {len(imei2_results)} match in IMEI2 column!")
            for row in imei2_results:
                print(f"      IMEI1: {row[0]}, IMEI2: {row[1]}, CartonNo: {row[2]}")
        else:
            print("   ❌ No matches found in IMEI2 column")

    print("\n" + "=" * 80)

    # ---- 5. Search IMEI table by CartonNo (since that column exists) ----
    print("📦 5. Searching IMEI table by CartonNo:")
    cursor.execute("SELECT IMEI1, IMEI2, CartonNo FROM IMEI WHERE CartonNo = ? OR CartonNo = ?", 
                   (MID_CARTON_ID, "PLT240310286"))
    carton_results = cursor.fetchall()
    if carton_results:
        print(f"   ✅ Found {len(carton_results)} records with matching CartonNo!")
        for row in carton_results:
            print(f"      IMEI1: {row[0]}, IMEI2: {row[1]}, CartonNo: {row[2]}")
    else:
        print("   ❌ No records found with matching CartonNo (either Mid or Big Carton ID)")

    conn.close()
    print("\n✅ Done!")

except Exception as e:
    print(f"❌ Error: {e}")