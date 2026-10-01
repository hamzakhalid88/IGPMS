import pyodbc

# ---------- Connection String ----------
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=192.168.10.98,2433;"
    "DATABASE=cpms;"
    "UID=python_app;"
    "PWD=Python@2024#;"
    "Encrypt=no;"
)

# Aap ki di hui MidCartonID
MID_CARTON_ID = "P302-SH3SHF2404150019"

try:
    conn = pyodbc.connect(conn_str)
    cursor = conn.cursor()
    print("✅ Database se connect ho gaya!\n")
    print("=" * 80)

    # ---- Step 1: Packing table se BigCartonID nikaalein ----
    cursor.execute("""
        SELECT BigCartonID, WorkOrder 
        FROM ODM_BigCartonPacking 
        WHERE MidCartonID = ?
    """, (MID_CARTON_ID,))
    packing = cursor.fetchone()

    if not packing:
        print(f"❌ '{MID_CARTON_ID}' nahi mila.")
        conn.close()
        exit()

    BIG_CARTON_ID = packing[0]
    WORK_ORDER = packing[1]
    print(f"📦 Packing Record:")
    print(f"   BigCartonID : {BIG_CARTON_ID}")
    print(f"   WorkOrder   : {WORK_ORDER}")
    print("=" * 80)

    # ---- Step 2: IMEI table mein search karein (CartonNo column ke hisaab se) ----
    # BigCartonID aur MidCartonID dono try karte hain, kyunki kisi mein bhi store ho sakta hai
    print(f"\n📱 Searching IMEI table for CartonNo = '{BIG_CARTON_ID}' OR '{MID_CARTON_ID}'...")
    
    query = """
        SELECT IMEI1, IMEI2, SN, CartonNo, OrderNO, PROJECT 
        FROM IMEI 
        WHERE CartonNo = ? OR CartonNo = ?
    """
    cursor.execute(query, (BIG_CARTON_ID, MID_CARTON_ID))
    rows = cursor.fetchall()
    
    total_count = len(rows)

    if total_count > 0:
        print(f"\n✅ TOTAL IMEI COUNT: {total_count}")
        print("-" * 80)
        print(f"{'Sr.':<4} | {'IMEI1':<18} | {'IMEI2':<18} | {'SN':<15} | CartonNo")
        print("-" * 80)
        
        for idx, row in enumerate(rows, 1):
            imei1 = row[0] if row[0] else "N/A"
            imei2 = row[1] if row[1] else "N/A"
            sn = row[2] if row[2] else "N/A"
            carton = row[3] if row[3] else "N/A"
            print(f"{idx:<4} | {imei1:<18} | {imei2:<18} | {sn:<15} | {carton}")
        
        # ---- Bonus: Saare IMEI1 aur IMEI2 ko ek list mein collect karein ----
        all_imeis = []
        for row in rows:
            if row[0]:
                all_imeis.append(row[0])
            if row[1]:
                all_imeis.append(row[1])
        
        print("\n" + "=" * 80)
        print(f"📌 Total IMEI numbers (unique devices): {len(all_imeis)}")
        # Pehle 10 dikhayein
        if len(all_imeis) > 10:
            print(f"   Sample (pehle 10): {', '.join(all_imeis[:10])} ...")
        else:
            print(f"   All IMEIs: {', '.join(all_imeis)}")

    else:
        print(f"\n❌ Koi IMEI nahi mila.")
        print("   Check karein ke IMEI table mein data kaise store hai.")
        print("   SSMS mein yeh query chala kar dekh lein:")
        print(f"   SELECT TOP 5 * FROM IMEI WHERE CartonNo = '{BIG_CARTON_ID}' OR CartonNo = '{MID_CARTON_ID}';")

    conn.close()
    print("\n✅ Done!")

except pyodbc.Error as e:
    print(f"❌ Database Error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")