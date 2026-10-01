import pyodbc
import pandas as pd
from datetime import datetime

# ---------- Connection String ----------
conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=192.168.10.98,2433;"
    "DATABASE=cpms;"
    "UID=python_app;"
    "PWD=Python@2024#;"
    "Encrypt=no;"
)

# Aap ki Carton ID (jo aap ne SQL mein use ki)
MID_CARTON_ID = "P302-SH3SHF2404150019"

try:
    conn = pyodbc.connect(conn_str)
    print("✅ Database se connect ho gaya!\n")
    print("=" * 80)

    # ----- Query to get IMEIs from ODM_Packing -----
    query = """
        SELECT IMEI, RecordDate 
        FROM ODM_Packing 
        WHERE MidCartonID = ?
        ORDER BY RecordDate ASC
    """
    
    cursor = conn.cursor()
    cursor.execute(query, (MID_CARTON_ID,))
    rows = cursor.fetchall()

    if rows:
        imei_list = [row[0] for row in rows if row[0]]  # Null values hatao
        count = len(imei_list)

        print(f"📦 Carton ID: {MID_CARTON_ID}")
        print(f"📱 Total IMEI Count: {count}")
        print("-" * 80)
        
        # Saare IMEI numbers print karein
        print("\n📋 IMEI List:")
        for idx, imei in enumerate(imei_list, 1):
            print(f"   {idx}. {imei}")
        
        # ---- Agar aapko Excel/CSV mein save karna hai toh ----
        save_option = input("\n💾 Kya aap IMEI list ko CSV file mein save karna chahte hain? (y/n): ").strip().lower()
        if save_option == 'y':
            df = pd.DataFrame(imei_list, columns=["IMEI_Number"])
            filename = f"IMEI_List_{MID_CARTON_ID}_{datetime.now().strftime('%Y%m%d')}.csv"
            df.to_csv(filename, index=False)
            print(f"✅ File save ho gayi: {filename}")
        
    else:
        print(f"❌ '{MID_CARTON_ID}' ke against ODM_Packing mein koi IMEI nahi mila.")

    conn.close()
    print("\n✅ Done!")

except pyodbc.Error as e:
    print(f"❌ Database Error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")