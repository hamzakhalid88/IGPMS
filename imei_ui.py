import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import pyodbc
import csv
import re
import threading
import time
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import os
import schedule
import json

# ============ DATABASE CONFIG ============
# NOTE: Move these to environment variables / a .env file in production.
# Example:
#   import os
#   DB_STR = (
#       "DRIVER={ODBC Driver 17 for SQL Server};"
#       f"SERVER={os.environ['DB_SERVER']};"
#       f"DATABASE={os.environ['DB_NAME']};"
#       f"UID={os.environ['DB_USER']};"
#       f"PWD={os.environ['DB_PASSWORD']};"
#       "Encrypt=no;Timeout=30;"
#   )
DB_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=192.168.10.98,2433;"
    "DATABASE=cpms;"
    "UID=python_app;"
    "PWD=Python@2024#;"
    "Encrypt=no;"
    "Timeout=30;"
)

# ============ ALLOWED MODELS LIST ============
ALLOWED_MODELS = [
    "Beauty Max",
    "Beauty Pro",
    "Easy 200",
    "Easy 200 Lite",
    "Flex 2",
    "Flex 3",
    "i10",
    "i102",
    "i104",
    "i105",
    "i106",
    "i12",
    "i15",
    "i16",
    "i211",
    "i251",
    "i252",
    "i510",
    "i511",
    "i550",
    "i555",
    "i710",
    "i888",
    "iMusic",
    "iMusic Plus",
    "iMusic Pro",
    "iMusic Ultra",
    "New 10",
    "New 10 (2+64GB)",
    "New 12",
    "New 15",
    "New 15 Pro",
    "New 16",
    "New 16 Pro",
    "New 17",
    "New 24",
    "New 25",
    "New 26",
    "New 26 Lite",
    "Note 23",
    "NOTE 23",
    "Note 24",
    "S20",
    "S22",
    "S9",
    "Smart 12",
    "Smart 13",
    "Smart 8",
    "Smart 8 Go",
    "Smart 9 Pro"
]

# Normalized models for case-insensitive matching
NORMALIZED_MODELS = {model.lower().strip(): model for model in ALLOWED_MODELS}

# ============ DEFAULT EMAIL CONFIG ============
DEFAULT_EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "haamzakhan159@gmail.com",
    "sender_password": "qhcg ytgu xlkt niie",
    "receiver_email": "yasir_iqbal@vgotel.com,saqib.javed@vgotel.com,Suhail@vgotel.com",
    "use_tls": True,
    "subject_prefix": "IMEI Data Export",
    "email_body": "Auto-generated IMEI data export for {date}.\nTotal records: {count}"
}

# ============ AUTO EXPORT CONFIG ============
CONFIG_FILE = 'auto_export_config.json'
EMAIL_CONFIG_FILE = 'email_config.json'
DEFAULT_CONFIG = {
    "auto_export_enabled": False,
    "export_time": "08:01",
    "last_export_date": "",
    "export_folder": os.path.join(os.path.expanduser("~"), "Desktop", "IMEI_Exports"),
    "send_email": False
}

# ============ PERFORMANCE TUNING ============
# SQL Server allows ~2100 parameters per query. We keep a safety margin below that,
# especially since the multi-column IMEI search repeats the parameter list once per column.
SQL_CHUNK_SIZE = 1000          # for single-column IN(...) batch queries
SQL_MULTI_COL_CHUNK_SIZE = 400  # for OR-ed multi-column IN(...) queries (400 * up to 5 cols ~= 2000 params)
UI_LOG_FLUSH_EVERY = 20         # only refresh the log widget every N messages to avoid UI lag on big batches

# ============ FAST COLUMN CACHE ============
_imei_columns = None

def get_imei_columns(conn):
    """Get all IMEI columns from ODM_LinkListofPhysicsNo"""
    global _imei_columns
    if _imei_columns:
        return _imei_columns

    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'ODM_LinkListofPhysicsNo'
            ORDER BY ORDINAL_POSITION
        """)
        cols = [row[0] for row in cursor.fetchall()]
        
        # Find all IMEI columns
        imei_cols = []
        for col in cols:
            col_lower = col.lower()
            if 'imei' in col_lower or 'physicsno' in col_lower:
                imei_cols.append(col)
        
        # If no IMEI columns found, use all columns
        if not imei_cols:
            imei_cols = cols[:5]  # First 5 columns
        
        _imei_columns = imei_cols
        return _imei_columns
        
    except Exception as e:
        print(f"Warning: Could not fetch IMEI columns: {e}")
        _imei_columns = ['PhysicsNo', 'imei2', 'imei3', 'imei4']
        return _imei_columns

def get_imei2_column(conn):
    """Get primary IMEI2 column (for backward compatibility)"""
    cols = get_imei_columns(conn)
    if len(cols) >= 2:
        return cols[1]
    return 'imei2'

# ============ MODEL MATCHING FUNCTION ============
def match_model(workorder):
    if not workorder:
        return ''
    
    workorder_clean = workorder.strip()
    
    # Try to extract model from VGOTEL-{model} pattern
    match = re.search(r'VGOTEL-([^(]+)', workorder_clean, re.IGNORECASE)
    if not match:
        # Try with space: VGOTEL {model}
        match = re.search(r'VGOTEL\s+([^(]+)', workorder_clean, re.IGNORECASE)
    
    if match:
        extracted = match.group(1).strip()
        extracted_lower = extracted.lower()
        
        # ===== STEP 1: EXACT MATCH (Case-Insensitive) =====
        for normalized, original in NORMALIZED_MODELS.items():
            if extracted_lower == normalized:
                return original
        
        # ===== STEP 2: STARTS WITH MATCH =====
        for normalized, original in NORMALIZED_MODELS.items():
            if extracted_lower.startswith(normalized):
                if len(extracted_lower) == len(normalized):
                    return original
                next_char = extracted_lower[len(normalized):].strip()
                if next_char and not next_char[0].isalnum():
                    return original
        
        # ===== STEP 3: CONTAINS MATCH =====
        for normalized, original in NORMALIZED_MODELS.items():
            if normalized in extracted_lower:
                return original
        
        return extracted
    
    return workorder_clean

def extract_lot_from_workorder(workorder):
    """Extract lot number from WorkOrder string"""
    if not workorder:
        return '-'
    
    match = re.search(r'\((\d+)\)', workorder)
    if match:
        return match.group(1)
    
    parts = re.split(r'[-_]', workorder)
    for part in parts:
        if part.isdigit() and len(part) >= 2:
            return part
    
    return '-'

# ============ BATCH DB HELPERS (fast path for large item lists) ============
def chunked(seq, size):
    """Yield successive chunks from seq of length `size`."""
    for i in range(0, len(seq), size):
        yield seq[i:i + size]

# Below this size a plain OR-ed IN() query is cheap enough that a temp table
# is not worth the extra round trips. Above it, we switch to the temp-table
# JOIN strategy (see _create_and_fill_temp_table / batch_find_imeis_across_columns).
TEMP_TABLE_THRESHOLD = 25

def _create_and_fill_temp_table(cursor, values, temp_table_name="#SearchVals"):
    """
    Create a local (session-scoped) temp table with one NVARCHAR column and
    bulk-insert `values` into it in a single executemany() call.

    Why this matters for speed:
    - SQL Server allows only ~2100 parameters per query, so a plain IN(...)
      search on a list of 1000-2000 IMEIs/CIDs has to be split into many
      chunks -> many round trips to the DB.
    - Worse, the old IMEI search combined several columns with OR in ONE
      WHERE clause (imei2 IN(...) OR imei3 IN(...) OR ...). SQL Server
      generally can't use a separate index per column when they're OR-ed
      together like that, so it falls back to a full/near-full table scan,
      repeated once per chunk.
    A temp table removes the parameter limit entirely (bulk insert instead of
    inline params), so there's no chunking needed at all - one insert, one
    query, regardless of whether you paste 20 or 20,000 IMEIs. It also lets
    each column be searched with its own JOIN, so SQL Server can use a
    per-column index seek instead of a scan.
    """
    cursor.execute(f"IF OBJECT_ID('tempdb..{temp_table_name}') IS NOT NULL DROP TABLE {temp_table_name}")
    cursor.execute(f"CREATE TABLE {temp_table_name} (val NVARCHAR(100) COLLATE DATABASE_DEFAULT PRIMARY KEY)")

    try:
        cursor.fast_executemany = True
    except Exception:
        pass

    # De-dup first: the temp table's val column is a PRIMARY KEY, so duplicate
    # pasted IMEIs/CIDs would otherwise throw a PK violation on insert.
    unique_values = list(dict.fromkeys(str(v).strip() for v in values if str(v).strip()))
    if unique_values:
        cursor.executemany(f"INSERT INTO {temp_table_name} (val) VALUES (?)", [(v,) for v in unique_values])

    return temp_table_name

def batch_check_existence(cursor, items, table, column, chunk_size=SQL_CHUNK_SIZE):
    """
    Check which of `items` exist in `table.column`. Returns a set of matched
    raw values (stripped).

    Small lists: batched IN() queries (cheap, no need for temp-table overhead).
    Large lists: single temp-table JOIN instead of many chunked IN() round trips.
    """
    found = set()
    if not items:
        return found

    if len(items) <= TEMP_TABLE_THRESHOLD:
        for chunk in chunked(items, chunk_size):
            placeholders = ', '.join(['?'] * len(chunk))
            query = f"SELECT DISTINCT {column} FROM {table} WHERE {column} IN ({placeholders})"
            cursor.execute(query, chunk)
            for row in cursor.fetchall():
                if row[0] and str(row[0]).strip():
                    found.add(str(row[0]).strip())
        return found

    temp_table = _create_and_fill_temp_table(cursor, items, "#SearchExist")
    try:
        query = (
            f"SELECT DISTINCT t.{column} FROM {table} t "
            f"JOIN {temp_table} s ON s.val = t.{column}"
        )
        cursor.execute(query)
        for row in cursor.fetchall():
            if row[0] and str(row[0]).strip():
                found.add(str(row[0]).strip())
    finally:
        cursor.execute(f"IF OBJECT_ID('tempdb..{temp_table}') IS NOT NULL DROP TABLE {temp_table}")

    return found

def batch_find_imeis_across_columns(cursor, imeis, imei_cols):
    """
    Search for `imeis` across every column in `imei_cols` (imei2, imei3, imei4, ...).
    Returns set of matched PhysicsNo values.

    FAST PATH (this is the fix for the slow "IMEI checkbox" search): bulk-insert
    all IMEIs into a temp table once, then run ONE query that UNIONs a separate
    JOIN per column. This replaces the old approach of OR-ing all columns
    together inside a single WHERE clause, which is what was forcing SQL
    Server into a near full-table scan on every chunk. Because there's no
    parameter limit with a temp table, there's also no chunking anymore - one
    round trip no matter how many IMEIs are pasted.
    """
    found = set()
    if not imeis or not imei_cols:
        return found

    if len(imeis) <= TEMP_TABLE_THRESHOLD:
        # Tiny list: plain OR-ed IN() is fine, skip temp table overhead.
        placeholders = ', '.join(['?'] * len(imeis))
        or_clause = " OR ".join([f"{col} IN ({placeholders})" for col in imei_cols])
        params = list(imeis) * len(imei_cols)
        cursor.execute(
            f"SELECT DISTINCT PhysicsNo FROM ODM_LinkListofPhysicsNo WHERE {or_clause}",
            params
        )
        for row in cursor.fetchall():
            if row[0] and str(row[0]).strip():
                found.add(str(row[0]).strip())
        return found

    temp_table = _create_and_fill_temp_table(cursor, imeis, "#SearchIMEIs")
    try:
        union_parts = [
            f"SELECT l.PhysicsNo AS PhysicsNo FROM ODM_LinkListofPhysicsNo l "
            f"JOIN {temp_table} s ON s.val = l.{col}"
            for col in imei_cols
        ]
        query = "SELECT DISTINCT combined.PhysicsNo FROM (" + " UNION ALL ".join(union_parts) + ") AS combined"
        cursor.execute(query)
        for row in cursor.fetchall():
            if row[0] and str(row[0]).strip():
                found.add(str(row[0]).strip())
    finally:
        cursor.execute(f"IF OBJECT_ID('tempdb..{temp_table}') IS NOT NULL DROP TABLE {temp_table}")

    return found

def fetch_rows_by_column_batch(cursor, values, base_query_template, chunk_size=SQL_CHUNK_SIZE):
    """
    Generic helper: run base_query_template (must contain a single {placeholders} slot)
    across chunks of `values` and return all rows combined.
    Kept for small lists / callers that still pass a {placeholders} template.
    """
    all_rows = []
    for chunk in chunked(values, chunk_size):
        placeholders = ', '.join(['?'] * len(chunk))
        query = base_query_template.format(placeholders=placeholders)
        cursor.execute(query, chunk)
        all_rows.extend(cursor.fetchall())
    return all_rows

def fetch_rows_via_temp_table(cursor, values, query_template, temp_table_name="#SearchRowsVals"):
    """
    Faster alternative to fetch_rows_by_column_batch for large lists: bulk-inserts
    `values` into a temp table once and runs `query_template` ONE time (no chunking,
    no parameter limit). query_template must use the literal placeholder
    '{temp_table}' - typically inside a
    'WHERE some_col IN (SELECT val FROM {temp_table})' clause.
    """
    if not values:
        return []
    temp_table = _create_and_fill_temp_table(cursor, values, temp_table_name)
    try:
        query = query_template.format(temp_table=temp_table)
        cursor.execute(query)
        rows = cursor.fetchall()
    finally:
        cursor.execute(f"IF OBJECT_ID('tempdb..{temp_table}') IS NOT NULL DROP TABLE {temp_table}")
    return rows

# ============ EMAIL CONFIG FUNCTIONS ============
def load_email_config():
    """Load email configuration from file"""
    if os.path.exists(EMAIL_CONFIG_FILE):
        try:
            with open(EMAIL_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                for key in DEFAULT_EMAIL_CONFIG:
                    if key not in config:
                        config[key] = DEFAULT_EMAIL_CONFIG[key]
                return config
        except Exception as e:
            print(f"Warning: could not load email config ({e}), using defaults")
            return DEFAULT_EMAIL_CONFIG.copy()
    return DEFAULT_EMAIL_CONFIG.copy()

def save_email_config(config):
    """Save email configuration to file"""
    try:
        with open(EMAIL_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Error saving email config: {e}")
        return False

def send_email_with_attachment_dynamic(file_path, email_config, subject="IMEI Data Export", body="Please find attached the IMEI data export."):
    """Send email with CSV attachment using dynamic config"""
    try:
        msg = MIMEMultipart()
        msg['From'] = email_config['sender_email']
        
        receiver_raw = email_config['receiver_email']
        receiver_list = [email.strip() for email in receiver_raw.split(',') if email.strip()]
        msg['To'] = ','.join(receiver_list)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with open(file_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename={os.path.basename(file_path)}'
            )
            msg.attach(part)

        server = smtplib.SMTP(email_config['smtp_server'], int(email_config['smtp_port']))
        
        if email_config.get('use_tls', True):
            server.starttls()
        
        server.login(email_config['sender_email'], email_config['sender_password'])
        text = msg.as_string()
        server.sendmail(email_config['sender_email'], receiver_list, text)
        server.quit()
        
        return True, f"Email sent successfully to {len(receiver_list)} recipient(s): {', '.join(receiver_list)}"
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"

# ============ SCHEDULER THREAD ============
class SchedulerThread(threading.Thread):
    def __init__(self, auto_export_manager):
        super().__init__()
        self.auto_export = auto_export_manager
        self.running = True
        self.daemon = True
        
    def run(self):
        while self.running:
            schedule.run_pending()
            time.sleep(30)
            
    def stop(self):
        self.running = False

# ============ AUTO EXPORT MANAGER ============
class AutoExportManager:
    def __init__(self, app_instance):
        self.app = app_instance
        self.config = self.load_config()
        self.email_config = load_email_config()
        self.running = False
        self.scheduler_thread = None
        self.export_in_progress = False
        
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: could not load auto-export config ({e}), using defaults")
                return DEFAULT_CONFIG.copy()
        return DEFAULT_CONFIG.copy()
    
    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving auto-export config: {e}")
            return False
    
    def check_if_export_exists(self, export_date):
        try:
            export_folder = self.config.get('export_folder', os.path.expanduser('~/Desktop/IMEI_Exports'))
            date_str = export_date.strftime('%Y-%m-%d')
            
            if os.path.exists(export_folder):
                files = [f for f in os.listdir(export_folder) 
                        if f.startswith(f'Packing_Data_{date_str}') and f.endswith('.csv')]
                if files:
                    return True, files[0]
            return False, None
        except Exception as e:
            self.app.log_message(f"⚠️ Error checking existing exports: {str(e)}")
            return False, None
    
    def check_and_export(self):
        if self.export_in_progress:
            self.app.log_message("⏳ Export already in progress, skipping...")
            return False
            
        try:
            current_date = datetime.now().date()
            self.export_in_progress = True
            
            export_date = current_date - timedelta(days=1)
            date_str = export_date.strftime('%Y-%m-%d')
            
            exists, existing_file = self.check_if_export_exists(export_date)
            
            if exists:
                self.app.log_message(f"⏭️ Export already exists for {date_str}: {existing_file}")
                if self.config.get('last_export_date') != date_str:
                    self.config['last_export_date'] = date_str
                    self.save_config()
                return False
            
            last_export_str = self.config.get('last_export_date', '')
            if last_export_str == date_str:
                self.app.log_message(f"⏭️ Config says already exported for {date_str}, but file not found! Re-exporting...")
            
            self.app.log_message(f"🔄 Exporting data for {date_str}...")
            result = self.export_data_for_date(export_date)
            
            if result:
                self.config['last_export_date'] = date_str
                self.save_config()
                self.app.log_message(f"✅ Export completed for {date_str}")
                return True
            else:
                self.app.log_message(f"❌ Export failed for {date_str}")
                return False
                
        except Exception as e:
            self.app.log_message(f"❌ Auto-export error: {str(e)}")
            return False
        finally:
            self.export_in_progress = False
    
    def export_data_for_date(self, export_date):
        try:
            date_str = export_date.strftime('%Y-%m-%d')
            
            self.app.log_message(f"📊 Connecting to database for {date_str}...")
            conn = pyodbc.connect(DB_STR, timeout=30)
            cursor = conn.cursor()
            
            imei_cols = get_imei_columns(conn)
            imei2_col = imei_cols[1] if len(imei_cols) > 1 else 'imei2'
            imei3_col = imei_cols[2] if len(imei_cols) > 2 else 'imei3'
            imei4_col = imei_cols[3] if len(imei_cols) > 3 else 'imei4'
            
            query = f"""
                SELECT 
                    p.WorkOrder,
                    COALESCE(l.SN, '') AS SN,
                    COALESCE(l.PhysicsNo, '') AS IMEI,
                    COALESCE(l.{imei2_col}, '') AS imei2,
                    COALESCE(l.{imei3_col}, '') AS imei3,
                    COALESCE(l.{imei4_col}, '') AS imei4,
                    p.MidCartonID AS midcartonid,
                    p.RecordDate AS packingdate
                FROM ODM_Packing p
                LEFT JOIN ODM_LinkListofPhysicsNo l ON p.IMEI = l.PhysicsNo
                WHERE CAST(p.RecordDate AS DATE) = ?
                ORDER BY p.RecordDate ASC
            """
            
            cursor.execute(query, date_str)
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                self.app.log_message(f"⚠️ No data found for date: {date_str}")
                return False
            
            export_folder = self.config.get('export_folder', os.path.expanduser('~/Desktop/IMEI_Exports'))
            os.makedirs(export_folder, exist_ok=True)
            
            exists, existing_file = self.check_if_export_exists(export_date)
            if exists:
                self.app.log_message(f"⏭️ File was created by another process: {existing_file}")
                return True
            
            filename = f"Packing_Data_{date_str}_{datetime.now().strftime('%H%M%S')}.csv"
            filepath = os.path.join(export_folder, filename)
            
            self.app.log_message(f"💾 Saving {len(rows)} records to {filename}...")
            
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                writer.writerow([
                    'Model', 'WorkOrder', 'sn', 'IMEI', 'imei2', 'imei3', 'imei4', 
                    'midcartonid', 'packingdate', 'Lot'
                ])
                
                for row in rows:
                    workorder = row[0] or ''
                    model = match_model(workorder)
                    lot = extract_lot_from_workorder(workorder)
                    
                    writer.writerow([
                        model,
                        workorder,
                        row[1] or '',
                        row[2] or '',
                        row[3] or '',
                        row[4] or '',
                        row[5] or '',
                        row[6] or '',
                        row[7].strftime('%Y-%m-%d %H:%M:%S') if row[7] else '',
                        lot
                    ])
            
            self.app.log_message(f"✅ File created: {filename} ({len(rows)} records)")
            
            if self.config.get('send_email', False):
                self.email_config = load_email_config()
                
                subject = f"Packing Data Export - {date_str}"
                body = f"""Packing data export for {date_str}.
Total records: {len(rows)}

File Format:
Model, WorkOrder, SN, IMEI, imei2, imei3, imei4, midcartonid, packingdate, Lot

Please find attached CSV file."""
                
                success, msg = send_email_with_attachment_dynamic(filepath, self.email_config, subject, body)
                if success:
                    self.app.log_message(f"✅ Email sent successfully")
                else:
                    self.app.log_message(f"❌ Email failed: {msg}")
            
            self.app.root.after(0, lambda: self.app.update_export_status(f"Last export: {date_str}"))
            return True
            
        except pyodbc.Error as e:
            self.app.log_message(f"❌ Database error for {date_str}: {str(e)}")
            return False
        except Exception as e:
            self.app.log_message(f"❌ Export error for {date_str}: {str(e)}")
            return False
    
    def start_auto_export(self):
        if self.running:
            self.app.log_message("⚠️ Auto-export already running")
            return
        
        self.running = True
        self.config['auto_export_enabled'] = True
        self.save_config()
        
        self.app.log_message("🔄 Running initial auto-export check...")
        
        def delayed_check():
            self.check_and_export()
        
        self.app.root.after(2000, delayed_check)
        
        export_time = self.config.get('export_time', '08:01')
        schedule.every().day.at(export_time).do(self.check_and_export)
        
        self.scheduler_thread = SchedulerThread(self)
        self.scheduler_thread.start()
        
        self.app.log_message(f"✅ Auto-export started (scheduled at {export_time})")
        self.app.root.after(0, lambda: self.app.update_export_status(f"🟢 Auto-export running (next at {export_time})"))
    
    def stop_auto_export(self):
        self.running = False
        self.config['auto_export_enabled'] = False
        self.save_config()
        
        if self.scheduler_thread:
            self.scheduler_thread.stop()
            self.scheduler_thread = None
        
        schedule.clear()
        self.app.log_message("Auto-export stopped")
        self.app.root.after(0, lambda: self.app.update_export_status("🔴 Auto-export stopped"))
    
    def update_email_config(self, new_config):
        self.email_config = new_config
        return save_email_config(new_config)
    
    def test_email(self):
        try:
            self.email_config = load_email_config()
            subject = "Test Email from Packing Data Tool"
            body = "This is a test email to verify your email configuration.\n\nIf you received this, your email settings are correct!"
            
            test_file = os.path.join(os.path.dirname(__file__), 'test_attachment.txt')
            with open(test_file, 'w') as f:
                f.write("Test attachment - Packing Data Tool")
            
            success, msg = send_email_with_attachment_dynamic(test_file, self.email_config, subject, body)
            
            if os.path.exists(test_file):
                os.remove(test_file)
            
            return success, msg
        except Exception as e:
            return False, str(e)

# ============ MAIN APPLICATION ============
class IMEILookupApp:
    def __init__(self, root):
        self.root = root
        
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        
        width = int(screen_width * 0.85)
        height = int(screen_height * 0.85)
        
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        self.root.title("IMEI Lookup Tool - Smart Missing CID/IMEI Detector (Optimized)")
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(1024, 700)
        self.root.configure(bg='#f0f0f0')
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        self.search_thread = None
        self.is_searching = False
        self.missing_items = []
        self.found_items_map = {}
        self.all_requested_items = []
        self.db_existing_items = set()
        
        self.log_messages = []
        self._log_pending_count = 0
        self.auto_export = AutoExportManager(self)

        self._build_ui()
        self._setup_styles()
        self._bind_shortcuts()
        
        if self.auto_export.config.get('auto_export_enabled', False):
            self.auto_export.start_auto_export()
            self.auto_export_var.set(True)
            self.export_status_indicator.config(text="🟢 Auto-export running", fg='#28a745')
        
        self.log_messages = []

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure("Fast.Treeview",
                       background="#ffffff",
                       foreground="#2c3e50",
                       rowheight=25,
                       fieldbackground="#ffffff",
                       font=('Segoe UI', 9))
        style.configure("Fast.Treeview.Heading",
                       background="#0078D7",
                       foreground="white",
                       font=('Segoe UI', 9, 'bold'),
                       padding=3)
        style.map("Fast.Treeview",
                 background=[('selected', '#0078D7')],
                 foreground=[('selected', 'white')])

        style.configure("Fast.Horizontal.TProgressbar",
                       background='#0078D7',
                       troughcolor='#e0e0e0',
                       borderwidth=0)

    def _normalize_item(self, item):
        return str(item).strip().upper()

    def _build_ui(self):
        main_container = tk.Frame(self.root, bg='#f0f0f0')
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_columnconfigure(0, weight=1)
        
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        self.main_tab = tk.Frame(self.notebook, bg='#f0f0f0')
        self.notebook.add(self.main_tab, text="🔍 Main Search")
        
        self.export_tab = tk.Frame(self.notebook, bg='#f0f0f0')
        self.notebook.add(self.export_tab, text="📊 Auto Export")
        
        self.log_tab = tk.Frame(self.notebook, bg='#f0f0f0')
        self.notebook.add(self.log_tab, text="📋 Logs")
        
        self._build_main_tab()
        self._build_export_tab()
        self._build_log_tab()
        
        self.status_label = tk.Label(self.root, 
                                    text="Ready - Smart Missing CID/IMEI Detector",
                                    bd=1, relief=tk.SUNKEN, anchor=tk.W,
                                    bg='#e9ecef', font=('Segoe UI', 9), padx=5)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_main_tab(self):
        main_frame = tk.Frame(self.main_tab, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        input_frame = tk.Frame(main_frame, bg='#f0f0f0')
        input_frame.grid(row=0, column=0, sticky="ew", pady=5)
        input_frame.grid_columnconfigure(0, weight=1)
        
        search_type_frame = tk.Frame(input_frame, bg='#f0f0f0')
        search_type_frame.pack(fill=tk.X, pady=2)
        
        tk.Label(search_type_frame, text="Search by:", 
                bg='#f0f0f0', font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        
        self.search_type_var = tk.StringVar(value="both")
        tk.Radiobutton(search_type_frame, text="CID", variable=self.search_type_var, 
                      value="cid", bg='#f0f0f0', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(search_type_frame, text="IMEI", variable=self.search_type_var, 
                      value="imei", bg='#f0f0f0', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(search_type_frame, text="Both (Auto-Detect)", variable=self.search_type_var, 
                      value="both", bg='#f0f0f0', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        
        row1 = tk.Frame(input_frame, bg='#f0f0f0')
        row1.pack(fill=tk.X, pady=2)
        row1.grid_columnconfigure(1, weight=1)
        
        tk.Label(row1, text="CID(s) / IMEI(s):", 
                bg='#f0f0f0', font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)

        self.cid_text = tk.Text(row1, height=2, width=40,
                               font=('Segoe UI', 9),
                               relief=tk.SUNKEN, bd=2,
                               wrap=tk.WORD)
        self.cid_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.cid_text.focus_set()

        self.cid_count_label = tk.Label(row1, text="0 items",
                                       bg='#f0f0f0', fg='#0078D7',
                                       font=('Segoe UI', 9, 'bold'))
        self.cid_count_label.pack(side=tk.LEFT, padx=5)

        self.cid_text.bind('<KeyRelease>', self._update_cid_count)

        row2 = tk.Frame(input_frame, bg='#f0f0f0')
        row2.pack(fill=tk.X, pady=3)
        
        btn_frame = tk.Frame(row2, bg='#f0f0f0')
        btn_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.btn_search = tk.Button(btn_frame, text="🔍 Search",
                                   command=self._start_search,
                                   bg='#0078D7', fg='white',
                                   font=('Segoe UI', 9, 'bold'),
                                   padx=15, relief=tk.RAISED, bd=2,
                                   cursor='hand2')
        self.btn_search.pack(side=tk.LEFT, padx=2)

        self.btn_export = tk.Button(btn_frame, text="💾 Export",
                                   command=self.export_csv,
                                   bg='#28a745', fg='white',
                                   font=('Segoe UI', 9, 'bold'),
                                   padx=15, relief=tk.RAISED, bd=2,
                                   state=tk.DISABLED)
        self.btn_export.pack(side=tk.LEFT, padx=2)

        self.btn_export_missing = tk.Button(btn_frame, text="⚠️ Missing",
                                   command=self.export_missing_items,
                                   bg='#dc3545', fg='white',
                                   font=('Segoe UI', 9, 'bold'),
                                   padx=15, relief=tk.RAISED, bd=2,
                                   state=tk.DISABLED)
        self.btn_export_missing.pack(side=tk.LEFT, padx=2)

        self.btn_verify = tk.Button(btn_frame, text="🔎 Verify",
                                   command=self.verify_items_in_db,
                                   bg='#fd7e14', fg='white',
                                   font=('Segoe UI', 9, 'bold'),
                                   padx=15, relief=tk.RAISED, bd=2,
                                   state=tk.DISABLED,
                                   cursor='hand2')
        self.btn_verify.pack(side=tk.LEFT, padx=2)

        self.btn_clear = tk.Button(btn_frame, text="✖ Clear",
                                  command=self.clear_all,
                                  bg='#6c757d', fg='white',
                                  font=('Segoe UI', 9),
                                  padx=12, relief=tk.RAISED, bd=2,
                                  cursor='hand2')
        self.btn_clear.pack(side=tk.LEFT, padx=2)
        
        progress_frame = tk.Frame(row2, bg='#f0f0f0')
        progress_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=10)
        
        self.progress = ttk.Progressbar(progress_frame, mode='determinate',
                                       style="Fast.Horizontal.TProgressbar",
                                       length=150)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress_label = tk.Label(progress_frame, text="Ready",
                                      bg='#f0f0f0', fg='#0078D7',
                                      font=('Segoe UI', 8))
        self.progress_label.pack(side=tk.LEFT, padx=5)

        row3 = tk.Frame(input_frame, bg='#f0f0f0')
        row3.pack(fill=tk.X, pady=2)

        self.time_label = tk.Label(row3, text="⏱️ Time: 0.00s",
                                  bg='#f0f0f0', fg='#28a745',
                                  font=('Segoe UI', 8, 'bold'))
        self.time_label.pack(side=tk.LEFT, padx=5)

        self.result_label = tk.Label(row3, text="✅ Found: 0",
                                    bg='#f0f0f0', fg='#28a745',
                                    font=('Segoe UI', 8, 'bold'))
        self.result_label.pack(side=tk.LEFT, padx=10)

        self.missing_label = tk.Label(row3, text="❌ Missing: 0",
                                     bg='#f0f0f0', fg='#dc3545',
                                     font=('Segoe UI', 8, 'bold'))
        self.missing_label.pack(side=tk.LEFT, padx=10)

        self.dbexist_label = tk.Label(row3, text="📋 In DB: 0",
                                     bg='#f0f0f0', fg='#fd7e14',
                                     font=('Segoe UI', 8, 'bold'))
        self.dbexist_label.pack(side=tk.LEFT, padx=10)

        row4 = tk.Frame(input_frame, bg='#f0f0f0')
        row4.pack(fill=tk.X, pady=2)

        tk.Label(row4, text="❌ Missing:", 
                bg='#f0f0f0', fg='#dc3545',
                font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)

        self.missing_text = tk.Text(row4, height=1, width=30,
                                   font=('Consolas', 9),
                                   bg='#fff5f5', fg='#dc3545',
                                   relief=tk.SUNKEN, bd=2,
                                   wrap=tk.WORD, state=tk.DISABLED)
        self.missing_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        row5 = tk.Frame(input_frame, bg='#f0f0f0')
        row5.pack(fill=tk.X, pady=2)

        tk.Label(row5, text="📋 In DB:", 
                bg='#f0f0f0', fg='#fd7e14',
                font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)

        self.dbexist_text = tk.Text(row5, height=1, width=30,
                                   font=('Consolas', 9),
                                   bg='#fff8e1', fg='#fd7e14',
                                   relief=tk.SUNKEN, bd=2,
                                   wrap=tk.WORD, state=tk.DISABLED)
        self.dbexist_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        tree_frame = tk.Frame(main_frame, bg='#f0f0f0')
        tree_frame.grid(row=1, column=0, sticky="nsew", pady=5)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")

        columns = ("MidCartonID", "WorkOrder", "Model", "IMEI1", "IMEI2", "SN", "RecordDate")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                yscrollcommand=vsb.set, xscrollcommand=hsb.set,
                                style="Fast.Treeview")

        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)

        col_config = {
            "MidCartonID": ("📦 Carton ID", 140, "w"),
            "WorkOrder": ("🔧 Work Order", 150, "w"),
            "Model": ("📱 Model", 100, "w"),
            "IMEI1": ("IMEI1", 130, "center"),
            "IMEI2": ("IMEI2", 130, "center"),
            "SN": ("SN", 120, "center"),
            "RecordDate": ("📅 Record Date", 140, "center")
        }

        for col, (heading, width, anchor) in col_config.items():
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, anchor=anchor)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

    def _build_export_tab(self):
        export_notebook = ttk.Notebook(self.export_tab)
        export_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        settings_frame = tk.Frame(export_notebook, bg='#f0f0f0')
        export_notebook.add(settings_frame, text="⚙️ Export Settings")
        
        email_frame = tk.Frame(export_notebook, bg='#f0f0f0')
        export_notebook.add(email_frame, text="📧 Email Configuration")
        
        self._build_export_settings(settings_frame)
        self._build_email_config(email_frame)

    def _build_export_settings(self, frame):
        main_frame = tk.Frame(frame, bg='#f0f0f0', padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title = tk.Label(main_frame, text="📊 Auto Export Settings", 
                        bg='#f0f0f0', font=('Segoe UI', 14, 'bold'), fg='#0078D7')
        title.pack(pady=5)
        
        status_frame = tk.Frame(main_frame, bg='#f0f0f0')
        status_frame.pack(fill=tk.X, pady=5)
        
        self.export_status_indicator = tk.Label(status_frame, 
                                              text="🟢 Auto-export running" if self.auto_export.running else "🔴 Auto-export stopped",
                                              bg='#f0f0f0', font=('Segoe UI', 10, 'bold'),
                                              fg='#28a745' if self.auto_export.running else '#dc3545')
        self.export_status_indicator.pack(side=tk.LEFT)
        
        config_frame = tk.LabelFrame(main_frame, text="Export Configuration", 
                                     bg='#f0f0f0', font=('Segoe UI', 10, 'bold'),
                                     padx=10, pady=10)
        config_frame.pack(fill=tk.X, pady=5)
        
        row1 = tk.Frame(config_frame, bg='#f0f0f0')
        row1.pack(fill=tk.X, pady=3)
        
        self.auto_export_var = tk.BooleanVar(value=self.auto_export.config.get('auto_export_enabled', False))
        tk.Checkbutton(row1, text="Enable Automatic Daily Export", 
                      variable=self.auto_export_var,
                      bg='#f0f0f0', font=('Segoe UI', 9),
                      command=self.toggle_auto_export).pack(side=tk.LEFT)
        
        row2 = tk.Frame(config_frame, bg='#f0f0f0')
        row2.pack(fill=tk.X, pady=3)
        
        tk.Label(row2, text="Export Time (24h):", 
                bg='#f0f0f0', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        
        self.export_time_var = tk.StringVar(value=self.auto_export.config.get('export_time', '08:01'))
        tk.Entry(row2, textvariable=self.export_time_var, width=10, 
                font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        
        tk.Button(row2, text="Update", 
                 command=self.update_export_time,
                 bg='#0078D7', fg='white', font=('Segoe UI', 8, 'bold'),
                 padx=10).pack(side=tk.LEFT, padx=5)
        
        row3 = tk.Frame(config_frame, bg='#f0f0f0')
        row3.pack(fill=tk.X, pady=3)
        
        tk.Label(row3, text="Export Folder:", 
                bg='#f0f0f0', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        
        self.export_folder_var = tk.StringVar(value=self.auto_export.config.get('export_folder', 
                                                DEFAULT_CONFIG['export_folder']))
        tk.Entry(row3, textvariable=self.export_folder_var, width=30, 
                font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        tk.Button(row3, text="Browse", 
                 command=self.browse_folder,
                 bg='#6c757d', fg='white', font=('Segoe UI', 8),
                 padx=8).pack(side=tk.LEFT, padx=5)
        
        row4 = tk.Frame(config_frame, bg='#f0f0f0')
        row4.pack(fill=tk.X, pady=3)
        
        self.send_email_var = tk.BooleanVar(value=self.auto_export.config.get('send_email', False))
        tk.Checkbutton(row4, text="Send Email with Export", 
                      variable=self.send_email_var,
                      bg='#f0f0f0', font=('Segoe UI', 9),
                      command=self.update_email_setting).pack(side=tk.LEFT)
        
        status_frame2 = tk.LabelFrame(main_frame, text="Export Status", 
                                     bg='#f0f0f0', font=('Segoe UI', 10, 'bold'),
                                     padx=10, pady=10)
        status_frame2.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.export_status_text = tk.Text(status_frame2, height=8, 
                                         font=('Consolas', 9),
                                         bg='#f8f9fa', fg='#2c3e50',
                                         relief=tk.SUNKEN, bd=2,
                                         wrap=tk.WORD)
        self.export_status_text.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = tk.Frame(main_frame, bg='#f0f0f0')
        btn_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(btn_frame, text="📤 Export Yesterday", 
                 command=self.export_yesterday_data,
                 bg='#fd7e14', fg='white', font=('Segoe UI', 9, 'bold'),
                 padx=15).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="📊 History", 
                 command=self.view_export_history,
                 bg='#17a2b8', fg='white', font=('Segoe UI', 9, 'bold'),
                 padx=15).pack(side=tk.LEFT, padx=5)
        
        self.update_export_status("Auto-export configured")

    def _build_email_config(self, frame):
        main_frame = tk.Frame(frame, bg='#f0f0f0', padx=15, pady=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title = tk.Label(main_frame, text="📧 Dynamic Email Configuration", 
                        bg='#f0f0f0', font=('Segoe UI', 14, 'bold'), fg='#0078D7')
        title.pack(pady=5)
        
        email_config = load_email_config()
        
        canvas_frame = tk.Frame(main_frame, bg='#f0f0f0')
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(canvas_frame, bg='#f0f0f0', highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#f0f0f0')
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        config_frame = tk.LabelFrame(scrollable_frame, text="Email Settings", 
                                     bg='#f0f0f0', font=('Segoe UI', 10, 'bold'),
                                     padx=10, pady=10)
        config_frame.pack(fill=tk.X, pady=5)
        
        row1 = tk.Frame(config_frame, bg='#f0f0f0')
        row1.pack(fill=tk.X, pady=2)
        tk.Label(row1, text="SMTP Server:", width=15, anchor='w',
                bg='#f0f0f0', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        self.smtp_server_var = tk.StringVar(value=email_config.get('smtp_server', 'smtp.gmail.com'))
        tk.Entry(row1, textvariable=self.smtp_server_var, width=30, 
                font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        row2 = tk.Frame(config_frame, bg='#f0f0f0')
        row2.pack(fill=tk.X, pady=2)
        tk.Label(row2, text="SMTP Port:", width=15, anchor='w',
                bg='#f0f0f0', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        self.smtp_port_var = tk.StringVar(value=str(email_config.get('smtp_port', 587)))
        tk.Entry(row2, textvariable=self.smtp_port_var, width=10, 
                font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        
        row3 = tk.Frame(config_frame, bg='#f0f0f0')
        row3.pack(fill=tk.X, pady=2)
        self.use_tls_var = tk.BooleanVar(value=email_config.get('use_tls', True))
        tk.Checkbutton(row3, text="Use TLS/SSL", 
                      variable=self.use_tls_var,
                      bg='#f0f0f0', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=25)
        
        row4 = tk.Frame(config_frame, bg='#f0f0f0')
        row4.pack(fill=tk.X, pady=2)
        tk.Label(row4, text="Sender Email:", width=15, anchor='w',
                bg='#f0f0f0', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        self.sender_email_var = tk.StringVar(value=email_config.get('sender_email', 'haamzakhan159@gmail.com'))
        tk.Entry(row4, textvariable=self.sender_email_var, width=30, 
                font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        row5 = tk.Frame(config_frame, bg='#f0f0f0')
        row5.pack(fill=tk.X, pady=2)
        tk.Label(row5, text="Sender Password:", width=15, anchor='w',
                bg='#f0f0f0', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        self.sender_password_var = tk.StringVar(value=email_config.get('sender_password', ''))
        self.password_entry = tk.Entry(row5, textvariable=self.sender_password_var, width=25, 
                                      font=('Segoe UI', 9), show='*')
        self.password_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        def toggle_password():
            if self.password_entry.cget('show') == '*':
                self.password_entry.config(show='')
                show_btn.config(text='Hide')
            else:
                self.password_entry.config(show='*')
                show_btn.config(text='Show')
        
        show_btn = tk.Button(row5, text="Show", command=toggle_password,
                            bg='#6c757d', fg='white', font=('Segoe UI', 8),
                            padx=8)
        show_btn.pack(side=tk.LEFT, padx=2)
        
        row6 = tk.Frame(config_frame, bg='#f0f0f0')
        row6.pack(fill=tk.X, pady=2)
        tk.Label(row6, text="Receiver Email(s):", width=15, anchor='w',
                bg='#f0f0f0', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        self.receiver_email_var = tk.StringVar(value=email_config.get('receiver_email', 'yasir_iqbal@vgotel.com,saqib.javed@vgotel.com,Suhail@vgotel.com'))
        tk.Entry(row6, textvariable=self.receiver_email_var, width=30, 
                font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        tk.Label(row6, text="(comma separated)", 
                bg='#f0f0f0', font=('Segoe UI', 7), fg='#6c757d').pack(side=tk.LEFT, padx=2)
        
        row7 = tk.Frame(config_frame, bg='#f0f0f0')
        row7.pack(fill=tk.X, pady=2)
        tk.Label(row7, text="Subject Prefix:", width=15, anchor='w',
                bg='#f0f0f0', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        self.subject_prefix_var = tk.StringVar(value=email_config.get('subject_prefix', 'IMEI Data Export'))
        tk.Entry(row7, textvariable=self.subject_prefix_var, width=30, 
                font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        row8 = tk.Frame(config_frame, bg='#f0f0f0')
        row8.pack(fill=tk.X, pady=2)
        tk.Label(row8, text="Email Body:", width=15, anchor='w',
                bg='#f0f0f0', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5, anchor='n')
        
        self.email_body_var = tk.StringVar(value=email_config.get('email_body', 
                                           'Auto-generated IMEI data export for {date}.\nTotal records: {count}'))
        tk.Entry(row8, textvariable=self.email_body_var, width=40, 
                font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        info_label = tk.Label(scrollable_frame, 
                             text="💡 Use {date} and {count} in email body",
                             bg='#f0f0f0', fg='#6c757d', font=('Segoe UI', 8, 'italic'))
        info_label.pack(pady=2)
        
        btn_frame = tk.Frame(scrollable_frame, bg='#f0f0f0')
        btn_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(btn_frame, text="💾 Save Email", 
                 command=self.save_email_config,
                 bg='#28a745', fg='white', font=('Segoe UI', 9, 'bold'),
                 padx=15).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="📧 Test Email", 
                 command=self.send_test_email,
                 bg='#fd7e14', fg='white', font=('Segoe UI', 9, 'bold'),
                 padx=15).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="🔄 Defaults", 
                 command=self.load_default_email_config,
                 bg='#6c757d', fg='white', font=('Segoe UI', 9),
                 padx=15).pack(side=tk.LEFT, padx=5)
        
        self.email_status_text = tk.Text(scrollable_frame, height=3, 
                                        font=('Consolas', 9),
                                        bg='#f8f9fa', fg='#2c3e50',
                                        relief=tk.SUNKEN, bd=2,
                                        wrap=tk.WORD)
        self.email_status_text.pack(fill=tk.X, pady=5)
        self.email_status_text.insert('1.0', "Email configuration ready.\nClick 'Save Email' to save changes.")
        self.email_status_text.config(state=tk.DISABLED)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_log_tab(self):
        frame = tk.Frame(self.log_tab, bg='#f0f0f0', padx=5, pady=5)
        frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(frame, 
                                                 font=('Consolas', 9),
                                                 bg='#1e1e1e', fg='#d4d4d4',
                                                 relief=tk.SUNKEN, bd=2,
                                                 wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = tk.Frame(frame, bg='#f0f0f0')
        btn_frame.pack(fill=tk.X, pady=2)
        
        tk.Button(btn_frame, text="Clear Logs", 
                 command=self.clear_logs,
                 bg='#dc3545', fg='white', font=('Segoe UI', 8),
                 padx=10).pack(side=tk.RIGHT)
        
        self.log_message("🚀 Application started")
        self.log_message(f"📁 Export folder: {self.auto_export.config.get('export_folder', 'Default')}")
        self.log_message(f"⏰ Auto-export: {'Enabled' if self.auto_export.config.get('auto_export_enabled', False) else 'Disabled'}")

    # ===== EMAIL CONFIG FUNCTIONS =====
    
    def save_email_config(self):
        try:
            config = {
                'smtp_server': self.smtp_server_var.get().strip(),
                'smtp_port': int(self.smtp_port_var.get().strip()),
                'sender_email': self.sender_email_var.get().strip(),
                'sender_password': self.sender_password_var.get(),
                'receiver_email': self.receiver_email_var.get().strip(),
                'use_tls': self.use_tls_var.get(),
                'subject_prefix': self.subject_prefix_var.get().strip(),
                'email_body': self.email_body_var.get().strip()
            }
            
            if save_email_config(config):
                self.auto_export.email_config = config
                self.email_status_text.config(state=tk.NORMAL)
                self.email_status_text.delete('1.0', tk.END)
                self.email_status_text.insert('1.0', f"✅ Email configuration saved!\n"
                                                     f"Sender: {config['sender_email']}\n"
                                                     f"Receiver: {config['receiver_email']}")
                self.email_status_text.config(state=tk.DISABLED)
                self.log_message("✅ Email configuration saved")
                messagebox.showinfo("Success", "Email configuration saved!")
            else:
                raise Exception("Failed to save configuration")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {str(e)}")
            self.log_message(f"❌ Email save error: {str(e)}")
    
    def send_test_email(self):
        try:
            self.save_email_config()
            
            self.email_status_text.config(state=tk.NORMAL)
            self.email_status_text.delete('1.0', tk.END)
            self.email_status_text.insert('1.0', "⏳ Sending test email...")
            self.email_status_text.config(state=tk.DISABLED)
            
            def do_test():
                success, msg = self.auto_export.test_email()
                self.root.after(0, lambda: self._update_email_test_status(success, msg))
            
            threading.Thread(target=do_test, daemon=True).start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {str(e)}")
    
    def _update_email_test_status(self, success, msg):
        self.email_status_text.config(state=tk.NORMAL)
        self.email_status_text.delete('1.0', tk.END)
        if success:
            self.email_status_text.insert('1.0', f"✅ Test email sent successfully!\n{msg}")
            self.log_message("✅ Test email sent")
            messagebox.showinfo("Success", "Test email sent! Check your inbox.")
        else:
            self.email_status_text.insert('1.0', f"❌ Test email failed!\n{msg}")
            self.log_message(f"❌ Test email failed: {msg}")
            messagebox.showerror("Error", f"Failed: {msg}")
        self.email_status_text.config(state=tk.DISABLED)
    
    def load_default_email_config(self):
        if messagebox.askyesno("Confirm", "Load default email configuration?"):
            self.smtp_server_var.set(DEFAULT_EMAIL_CONFIG['smtp_server'])
            self.smtp_port_var.set(str(DEFAULT_EMAIL_CONFIG['smtp_port']))
            self.sender_email_var.set(DEFAULT_EMAIL_CONFIG['sender_email'])
            self.sender_password_var.set('')
            self.receiver_email_var.set(DEFAULT_EMAIL_CONFIG['receiver_email'])
            self.use_tls_var.set(DEFAULT_EMAIL_CONFIG.get('use_tls', True))
            self.subject_prefix_var.set(DEFAULT_EMAIL_CONFIG.get('subject_prefix', 'IMEI Data Export'))
            self.email_body_var.set(DEFAULT_EMAIL_CONFIG.get('email_body', 
                                   'Auto-generated IMEI data export for {date}.\nTotal records: {count}'))
            
            self.email_status_text.config(state=tk.NORMAL)
            self.email_status_text.delete('1.0', tk.END)
            self.email_status_text.insert('1.0', "Default config loaded.\nClick 'Save Email' to save.")
            self.email_status_text.config(state=tk.DISABLED)
            self.log_message("Default email config loaded")

    # ===== AUTO EXPORT FUNCTIONS =====
    
    def toggle_auto_export(self):
        if self.auto_export_var.get():
            self.auto_export.start_auto_export()
            self.log_message("✅ Auto-export enabled")
            self.export_status_indicator.config(text="🟢 Auto-export running", fg='#28a745')
        else:
            self.auto_export.stop_auto_export()
            self.log_message("Auto-export disabled")
            self.export_status_indicator.config(text="🔴 Auto-export stopped", fg='#dc3545')
    
    def update_export_time(self):
        new_time = self.export_time_var.get().strip()
        if re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', new_time):
            self.auto_export.config['export_time'] = new_time
            self.auto_export.save_config()
            self.log_message(f"⏰ Export time updated to: {new_time}")
            
            if self.auto_export.running:
                self.auto_export.stop_auto_export()
                self.auto_export.start_auto_export()
            
            messagebox.showinfo("Success", f"Export time updated to {new_time}")
        else:
            messagebox.showerror("Invalid", "Use HH:MM format (24h)")
    
    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select Export Folder")
        if folder:
            self.export_folder_var.set(folder)
            self.auto_export.config['export_folder'] = folder
            self.auto_export.save_config()
            self.log_message(f"📁 Folder updated: {folder}")
    
    def update_email_setting(self):
        self.auto_export.config['send_email'] = self.send_email_var.get()
        self.auto_export.save_config()
        status = "enabled" if self.send_email_var.get() else "disabled"
        self.log_message(f"📧 Email {status}")
    
    def export_yesterday_data(self):
        yesterday = datetime.now().date() - timedelta(days=1)
        self.log_message(f"📤 Exporting data for {yesterday}")
        
        def do_export():
            result = self.auto_export.export_data_for_date(yesterday)
            if result:
                self.log_message(f"✅ Export completed for {yesterday}")
                messagebox.showinfo("Complete", f"Data for {yesterday} exported!")
            else:
                self.log_message(f"❌ Export failed for {yesterday}")
                messagebox.showerror("Failed", f"Failed to export data for {yesterday}")
        
        threading.Thread(target=do_export, daemon=True).start()
    
    def view_export_history(self):
        folder = self.auto_export.config.get('export_folder', '')
        if not os.path.exists(folder):
            messagebox.showinfo("No History", "Folder doesn't exist.")
            return
        
        files = [f for f in os.listdir(folder) 
                if (f.startswith('Packing_Data_') or f.startswith('IMEI_Export_')) 
                and f.endswith('.csv')]
        files.sort(reverse=True)
        
        if not files:
            messagebox.showinfo("No History", "No export files found.")
            return
        
        hist_window = tk.Toplevel(self.root)
        hist_window.title("📊 Export History")
        hist_window.geometry("600x400")
        hist_window.configure(bg='#f0f0f0')
        
        listbox = tk.Listbox(hist_window, font=('Consolas', 9), selectmode=tk.EXTENDED)
        listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        for f in files:
            file_path = os.path.join(folder, f)
            size = os.path.getsize(file_path) / 1024
            listbox.insert(tk.END, f"{f} ({size:.1f} KB)")
        
        def open_selected():
            selection = listbox.curselection()
            if selection:
                idx = selection[0]
                filename = files[idx]
                filepath = os.path.join(folder, filename)
                os.startfile(filepath)
        
        btn_frame = tk.Frame(hist_window, bg='#f0f0f0')
        btn_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(btn_frame, text="📂 Open", 
                command=open_selected,
                bg='#0078D7', fg='white', font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="Close", 
                command=hist_window.destroy,
                bg='#6c757d', fg='white', font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        
    def update_export_status(self, status):
        self.export_status_text.delete('1.0', tk.END)
        self.export_status_text.insert('1.0', f"{status}\n\n")
        
        config = self.auto_export.config
        self.export_status_text.insert(tk.END, f"Configuration:\n")
        self.export_status_text.insert(tk.END, f"  • Auto-export: {'✅ Enabled' if config.get('auto_export_enabled', False) else '❌ Disabled'}\n")
        self.export_status_text.insert(tk.END, f"  • Export Time: {config.get('export_time', '08:01')}\n")
        self.export_status_text.insert(tk.END, f"  • Folder: {config.get('export_folder', 'Default')}\n")
        self.export_status_text.insert(tk.END, f"  • Email: {'✅ Yes' if config.get('send_email', False) else '❌ No'}\n")
        
        if config.get('last_export_date'):
            self.export_status_text.insert(tk.END, f"  • Last Export: {config['last_export_date']}\n")
    
    def log_message(self, message):
        """
        Append a log line. UI refresh (.see + update_idletasks) is throttled
        to every UI_LOG_FLUSH_EVERY messages so bulk searches (2000+ items) don't
        freeze/lag the interface with constant redraws.
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, log_entry)
        
        self.log_messages.append(log_entry)
        if len(self.log_messages) > 1000:
            self.log_messages.pop(0)
        
        self._log_pending_count += 1
        if self._log_pending_count >= UI_LOG_FLUSH_EVERY:
            self._log_pending_count = 0
            self.log_text.see(tk.END)
            self.root.update_idletasks()
    
    def clear_logs(self):
        self.log_text.delete('1.0', tk.END)
        self.log_message("🗑️ Logs cleared")

    # ===== SEARCH FUNCTIONS =====
    
    def _update_cid_count(self, event=None):
        text = self.cid_text.get('1.0', 'end-1c').strip()
        items = [p.strip() for p in re.split(r'[,\n;\r\|\t]+', text) if p.strip()]
        self.cid_count_label.config(text=f"{len(items)} items")

    def _bind_shortcuts(self):
        self.root.bind('<Return>', lambda e: self._start_search())
        self.root.bind('<F5>', lambda e: self._start_search())
        self.root.bind('<Control-e>', lambda e: self.export_csv())
        self.root.bind('<Control-m>', lambda e: self.export_missing_items())
        self.root.bind('<Control-v>', lambda e: self.verify_items_in_db())
        self.root.bind('<Escape>', lambda e: self.clear_all())

    def _start_search(self):
        if self.is_searching:
            return

        input_text = self.cid_text.get('1.0', 'end-1c').strip()
        self.all_requested_items = [p.strip() for p in re.split(r'[,\n;\r\|\t]+', input_text) if p.strip()]

        if not self.all_requested_items:
            self._set_status("Please enter CIDs or IMEIs!", "warning")
            return

        self._clear_tree()
        self.missing_items = []
        self.found_items_map = {}
        self.db_existing_items = set()
        self._update_missing_display()
        self._update_dbexist_display()

        self.btn_search.config(state=tk.DISABLED, text="⏳ Searching...")
        self.btn_export.config(state=tk.DISABLED)
        self.btn_export_missing.config(state=tk.DISABLED)
        self.btn_verify.config(state=tk.DISABLED)
        self.is_searching = True

        self.search_thread = threading.Thread(target=self._search_worker, args=(self.all_requested_items,))
        self.search_thread.daemon = True
        self.search_thread.start()

    def _search_worker(self, items):
        """
        Optimized bulk search:
        - No per-item queries. Every existence check is a batched IN(...) query.
        - IMEI columns (imei2, imei3, imei4, ...) are checked in a single OR-ed
          query per chunk instead of one query per column per chunk.
        - Row data fetches are also batched with IN(...).
        This keeps DB round-trips roughly constant regardless of whether you
        paste 20 items or 2000+ items (only the number of *chunks* grows).
        """
        start_time = time.time()
        conn = None

        try:
            self.root.after(0, lambda: self._update_progress(10, "Connecting..."))
            conn = pyodbc.connect(DB_STR, timeout=30)
            cursor = conn.cursor()

            self.root.after(0, lambda: self._update_progress(20, "Getting column info..."))
            imei_cols = get_imei_columns(conn)
            self.root.after(0, lambda: self.log_message(f"📋 Found IMEI columns: {', '.join(imei_cols)}"))

            self.root.after(0, lambda: self._update_progress(25, "Classifying items..."))

            search_type = self.search_type_var.get()

            # ===== Classify items as CID or IMEI based on search mode =====
            cids_to_search = []
            imeis_to_search = []
            skipped_count = 0

            for item in items:
                is_imei = bool(re.match(r'^\d{15}$', item))
                is_cid = not is_imei

                if search_type == "cid":
                    if is_cid:
                        cids_to_search.append(item)
                    else:
                        skipped_count += 1
                elif search_type == "imei":
                    if is_imei:
                        imeis_to_search.append(item)
                    else:
                        skipped_count += 1
                else:  # both
                    if is_imei:
                        imeis_to_search.append(item)
                    else:
                        cids_to_search.append(item)

            if skipped_count:
                self.root.after(0, lambda n=skipped_count: self.log_message(f"⚠️ Skipped {n} item(s) not matching {search_type.upper()} mode"))

            # ===== BATCH CHECK: CIDs in ODM_Packing (MidCartonID) =====
            self.root.after(0, lambda: self._update_progress(35, "Checking CIDs (batched)..."))
            found_cids_raw = set()
            if cids_to_search:
                self.root.after(0, lambda n=len(cids_to_search): self.log_message(f"🔍 Checking {n} CIDs (batched query)..."))
                found_cids_raw = batch_check_existence(cursor, cids_to_search, "ODM_Packing", "MidCartonID")
                found_cids = {self._normalize_item(v) for v in found_cids_raw}
                self.root.after(0, lambda n=len(found_cids): self.log_message(f"✅ Found {n} CIDs in ODM_Packing"))
            else:
                found_cids = set()

            # ===== BATCH CHECK: IMEIs across ALL imei columns in ONE query per chunk =====
            self.root.after(0, lambda: self._update_progress(45, "Checking IMEIs (batched)..."))
            found_imeis = set()
            if imeis_to_search:
                self.root.after(0, lambda n=len(imeis_to_search), c=len(imei_cols): self.log_message(f"🔍 Checking {n} IMEIs across {c} columns (batched query)..."))
                found_imeis = batch_find_imeis_across_columns(cursor, imeis_to_search, imei_cols)
                self.root.after(0, lambda n=len(found_imeis): self.log_message(f"✅ Total found {n} IMEIs in ODM_LinkListofPhysicsNo"))

            # ===== BATCH CHECK: leftover CIDs/IMEIs that might exist "cross-table" =====
            self.root.after(0, lambda: self._update_progress(55, "Cross-checking leftovers..."))

            unchecked_cids = [c for c in cids_to_search if self._normalize_item(c) not in found_cids]
            unchecked_imeis = [i for i in imeis_to_search if i not in found_imeis]

            # A CID that wasn't in ODM_Packing might still exist as a PhysicsNo
            cids_exist_as_physicsno = batch_check_existence(cursor, unchecked_cids, "ODM_LinkListofPhysicsNo", "PhysicsNo") if unchecked_cids else set()
            # An IMEI that wasn't in the link table might still exist as a MidCartonID in Packing
            imeis_exist_as_cartonid = batch_check_existence(cursor, unchecked_imeis, "ODM_Packing", "MidCartonID") if unchecked_imeis else set()

            truly_missing = []
            exists_in_db = []

            for cid in unchecked_cids:
                if self._normalize_item(cid) in {self._normalize_item(v) for v in cids_exist_as_physicsno}:
                    exists_in_db.append(cid)
                else:
                    truly_missing.append(cid)

            for imei in unchecked_imeis:
                if imei in imeis_exist_as_cartonid:
                    exists_in_db.append(imei)
                else:
                    truly_missing.append(imei)

            self.missing_items = truly_missing
            self.db_existing_items = set(exists_in_db)

            self.root.after(0, lambda: self.log_message(
                f"📊 Results: Found {len(found_cids)} CIDs + {len(found_imeis)} IMEIs, Missing: {len(self.missing_items)}"
            ))

            self.root.after(0, lambda: self._update_progress(65, "Fetching row data (batched)..."))

            # ===== BATCH FETCH: row data for found CIDs =====
            all_rows = []
            imei2_col = imei_cols[1] if len(imei_cols) > 1 else 'imei2'

            if found_cids_raw:
                cid_query_template = f"""
                    SELECT 
                        p.MidCartonID,
                        p.WorkOrder,
                        p.Model,
                        l.PhysicsNo AS IMEI1,
                        COALESCE(l.{imei2_col}, '') AS IMEI2,
                        COALESCE(l.SN, '') AS SN,
                        p.RecordDate
                    FROM ODM_Packing p
                    LEFT JOIN ODM_LinkListofPhysicsNo l ON p.IMEI = l.PhysicsNo
                    WHERE p.MidCartonID IN (SELECT val FROM {{temp_table}})
                    ORDER BY p.RecordDate ASC
                """
                cid_rows = fetch_rows_via_temp_table(cursor, list(found_cids_raw), cid_query_template, "#SearchCidRows")
                all_rows.extend(cid_rows)
                self.root.after(0, lambda p=70: self._update_progress(p, "Fetched CID rows..."))

            # ===== FAST FETCH (temp-table JOIN): row data for found IMEIs =====
            if found_imeis:
                imei_query_template = f"""
                    SELECT 
                        p.MidCartonID,
                        p.WorkOrder,
                        p.Model,
                        l.PhysicsNo AS IMEI1,
                        COALESCE(l.{imei2_col}, '') AS IMEI2,
                        COALESCE(l.SN, '') AS SN,
                        p.RecordDate
                    FROM ODM_LinkListofPhysicsNo l
                    LEFT JOIN ODM_Packing p ON p.IMEI = l.PhysicsNo
                    WHERE l.PhysicsNo IN (SELECT val FROM {{temp_table}})
                    ORDER BY p.RecordDate ASC
                """
                imei_rows = fetch_rows_via_temp_table(cursor, list(found_imeis), imei_query_template, "#SearchImeiRows")
                all_rows.extend(imei_rows)
                self.root.after(0, lambda p=90: self._update_progress(p, "Fetched IMEI rows..."))

            conn.close()

            elapsed = time.time() - start_time
            self.root.after(0, lambda: self._update_progress(95, "Loading results..."))
            self.root.after(0, lambda r=all_rows, t=elapsed: self._display_results(r, t))

        except Exception as error:
            error_msg = str(error)
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            self.root.after(0, lambda msg=error_msg: self._handle_error(msg))

    def _display_results(self, rows, elapsed_time):
        # Bulk-insert into the Treeview. For very large row counts this loop is
        # still the fastest reliable approach in Tkinter (no native bulk-insert API),
        # but since DB round-trips are now batched, this is no longer the bottleneck.
        for row in rows:
            workorder = row[1] or ''
            matched_model = match_model(workorder)
            
            date_str = row[6].strftime('%Y-%m-%d %H:%M:%S') if row[6] else ''
            self.tree.insert("", tk.END, values=(
                row[0] or 'N/A',
                workorder,
                matched_model,
                row[3] or '',
                row[4] or '',
                row[5] or '',
                date_str
            ))

        self._update_progress(100, "Done!")
        self.time_label.config(text=f"⏱️ Time: {elapsed_time:.2f}s")
        self.result_label.config(text=f"✅ Found: {len(rows)}")
        self.missing_label.config(text=f"❌ Missing: {len(self.missing_items)}")
        self.dbexist_label.config(text=f"📋 In DB: {len(self.db_existing_items)}")

        self._update_missing_display()
        self._update_dbexist_display()

        status_parts = [f"Found {len(rows)} records"]
        if self.missing_items:
            status_parts.append(f"❌ {len(self.missing_items)} missing")
        if self.db_existing_items:
            status_parts.append(f"📋 {len(self.db_existing_items)} in DB")
        status_parts.append(f"in {elapsed_time:.2f}s")

        status_type = "success"
        if self.missing_items:
            status_type = "warning"
        if len(self.missing_items) == len(self.all_requested_items):
            status_type = "error"

        self._set_status(" | ".join(status_parts), status_type)

        if rows:
            self.btn_export.config(state=tk.NORMAL)
        if self.missing_items:
            self.btn_export_missing.config(state=tk.NORMAL)
        if self.db_existing_items or self.missing_items:
            self.btn_verify.config(state=tk.NORMAL)

        self._reset_search_state()

    def _update_missing_display(self):
        self.missing_text.config(state=tk.NORMAL)
        self.missing_text.delete('1.0', tk.END)
        if self.missing_items:
            display = ', '.join(self.missing_items[:5])
            if len(self.missing_items) > 5:
                display += f"... (+{len(self.missing_items)-5} more)"
            self.missing_text.insert('1.0', display)
        else:
            self.missing_text.insert('1.0', 'None')
        self.missing_text.config(state=tk.DISABLED)

    def _update_dbexist_display(self):
        self.dbexist_text.config(state=tk.NORMAL)
        self.dbexist_text.delete('1.0', tk.END)
        if self.db_existing_items:
            display = ', '.join(list(self.db_existing_items)[:5])
            if len(self.db_existing_items) > 5:
                display += f"... (+{len(self.db_existing_items)-5} more)"
            self.dbexist_text.insert('1.0', display)
        else:
            self.dbexist_text.insert('1.0', 'None')
        self.dbexist_text.config(state=tk.DISABLED)

    def verify_items_in_db(self):
        """
        Deep verification report. Kept per-item here on purpose since it's a
        diagnostic tool the user opens for a handful of specific items, not for
        bulk 2000-item runs (where the batched search above is what matters).
        """
        if not self.missing_items and not self.db_existing_items:
            messagebox.showinfo("Verify", "No missing items to verify!")
            return

        verify_window = tk.Toplevel(self.root)
        verify_window.title("🔎 Deep Verification Report")
        verify_window.geometry("700x500")
        verify_window.configure(bg='#f0f0f0')

        text = tk.Text(verify_window, font=('Consolas', 9), wrap=tk.WORD,
                      bg='#ffffff', fg='#2c3e50', padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = ttk.Scrollbar(text, command=text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.config(yscrollcommand=scrollbar.set)

        def do_verify():
            try:
                conn = pyodbc.connect(DB_STR, timeout=30)
                cursor = conn.cursor()
                imei_cols = get_imei_columns(conn)

                text.insert(tk.END, "="*50 + "\n")
                text.insert(tk.END, "🔎 DEEP VERIFICATION REPORT\n")
                text.insert(tk.END, "="*50 + "\n\n")

                all_check_items = self.missing_items + list(self.db_existing_items)

                for item in all_check_items:
                    text.insert(tk.END, f"\n📦 Item: {item}\n")
                    text.insert(tk.END, "-"*30 + "\n")
                    
                    is_imei = bool(re.match(r'^\d{15}$', item))

                    if is_imei:
                        text.insert(tk.END, f"  Type: IMEI\n")
                        # Check in all IMEI columns
                        for col in imei_cols:
                            try:
                                cursor.execute(f"SELECT COUNT(*) FROM ODM_LinkListofPhysicsNo WHERE {col} = ?", item)
                                count = cursor.fetchone()[0]
                                text.insert(tk.END, f"  ODM_LinkList ({col}): {count} record(s)\n")
                            except Exception as e:
                                text.insert(tk.END, f"  ODM_LinkList ({col}): ERROR - {str(e)}\n")
                        
                        # Check in Packing
                        cursor.execute("SELECT COUNT(*) FROM ODM_Packing WHERE IMEI = ?", item)
                        packing = cursor.fetchone()[0]
                        text.insert(tk.END, f"  ODM_Packing (IMEI): {packing} record(s)\n")
                    else:
                        text.insert(tk.END, f"  Type: CID\n")
                        # Check in Packing
                        cursor.execute("SELECT COUNT(*) FROM ODM_Packing WHERE MidCartonID = ?", item)
                        packing = cursor.fetchone()[0]
                        text.insert(tk.END, f"  ODM_Packing (MidCartonID): {packing} record(s)\n")
                        
                        # Check in LinkList
                        cursor.execute("SELECT COUNT(*) FROM ODM_LinkListofPhysicsNo WHERE PhysicsNo = ?", item)
                        link1 = cursor.fetchone()[0]
                        text.insert(tk.END, f"  ODM_LinkList (PhysicsNo): {link1} record(s)\n")

                    text.insert(tk.END, "\n")
                    text.update_idletasks()

                conn.close()
                text.insert(tk.END, "\n✅ Complete!\n")

            except Exception as e:
                text.insert(tk.END, f"\n❌ Error: {str(e)}\n")

        threading.Thread(target=do_verify, daemon=True).start()

    def _handle_error(self, error_msg):
        self._set_status(f"Error: {error_msg[:150]}", "error")
        self._update_progress(0, "Error!")
        self._reset_search_state()

    def _reset_search_state(self):
        self.is_searching = False
        self.btn_search.config(state=tk.NORMAL, text="🔍 Search")

    def _update_progress(self, value, text):
        self.progress['value'] = value
        self.progress_label.config(text=text)
        self.root.update_idletasks()

    def _set_status(self, message, status_type="info"):
        colors = {"info": "#2c3e50", "success": "#28a745", "warning": "#f39c12", "error": "#dc3545"}
        self.status_label.config(text=f" {message}", fg=colors.get(status_type, "#2c3e50"))

    def _clear_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

    def clear_all(self):
        self.cid_text.delete('1.0', tk.END)
        self._clear_tree()
        self.missing_items = []
        self.found_items_map = {}
        self.db_existing_items = set()
        self.all_requested_items = []
        self._update_missing_display()
        self._update_dbexist_display()
        self.progress['value'] = 0
        self.progress_label.config(text="Ready")
        self.time_label.config(text="⏱️ Time: 0.00s")
        self.result_label.config(text="✅ Found: 0")
        self.missing_label.config(text="❌ Missing: 0")
        self.dbexist_label.config(text="📋 In DB: 0")
        self.cid_count_label.config(text="0 items")
        self.btn_export.config(state=tk.DISABLED)
        self.btn_export_missing.config(state=tk.DISABLED)
        self.btn_verify.config(state=tk.DISABLED)
        self._set_status("Ready - All cleared", "info")

    def export_csv(self):
        rows = []
        for child in self.tree.get_children():
            rows.append(self.tree.item(child)['values'])

        if not rows:
            messagebox.showinfo("No Data", "No data to export.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"IMEI_Export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if not filename:
            return

        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['MidCartonID', 'WorkOrder', 'Model', 'IMEI1', 'IMEI2', 'SN', 'RecordDate'])
                writer.writerows(rows)
            self._set_status(f"✅ Exported: {filename}", "success")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def export_missing_items(self):
        if not self.missing_items and not self.db_existing_items:
            messagebox.showinfo("No Missing Items", "All items were found!")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"Missing_Items_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if not filename:
            return

        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['Item', 'Status', 'Reason', 'Checked_Date'])

                for item in self.missing_items:
                    is_imei = bool(re.match(r'^\d{15}$', item))
                    item_type = "IMEI" if is_imei else "CID"
                    writer.writerow([item, 'TRULY MISSING', f'{item_type} not found in any database table', 
                                   datetime.now().strftime('%Y-%m-%d %H:%M:%S')])

                for item in self.db_existing_items:
                    is_imei = bool(re.match(r'^\d{15}$', item))
                    item_type = "IMEI" if is_imei else "CID"
                    writer.writerow([item, 'IN DB BUT NO PACKING', f'{item_type} exists in database but no packing record', 
                                   datetime.now().strftime('%Y-%m-%d %H:%M:%S')])

            total_missing = len(self.missing_items) + len(self.db_existing_items)
            self._set_status(f"⚠️ Exported {total_missing} items", "warning")

            messagebox.showwarning("Missing Items Exported", 
                f"⚠️ {len(self.missing_items)} Truly Missing\n"
                f"📋 {len(self.db_existing_items)} In DB no packing\n"
                f"Saved to: {filename}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = IMEILookupApp(root)
    root.mainloop()