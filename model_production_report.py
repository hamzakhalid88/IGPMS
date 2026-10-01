"""
Model Production Report - SIMPLE & ACCURATE
Sirf IMEI1 count karega, jo bhi model database mein ho
No filters, no restrictions!
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import pyodbc
import csv
from datetime import datetime, timedelta
import re
import os
import threading
from collections import defaultdict

# ============ DATABASE CONFIG ============
DB_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=192.168.10.98,2433;"
    "DATABASE=cpms;"
    "UID=python_app;"
    "PWD=Python@2024#;"
    "Encrypt=no;"
    "Timeout=30;"
)

# ============ NO MODEL LIST - SABHI MODELS COUNT HONGE ============

def extract_model_from_workorder(workorder):
    """
    WorkOrder se model name extract karega
    Example: "VGOTEL-New 15 (12345)" -> "New 15"
    """
    if not workorder:
        return 'Unknown'
    
    workorder_clean = workorder.strip()
    
    # Pattern 1: VGOTEL-ModelName
    match = re.search(r'VGOTEL-([^(]+)', workorder_clean, re.IGNORECASE)
    if not match:
        # Pattern 2: VGOTEL ModelName
        match = re.search(r'VGOTEL\s+([^(]+)', workorder_clean, re.IGNORECASE)
    
    if match:
        model = match.group(1).strip()
        # Remove any trailing lot numbers like (12345)
        model = re.sub(r'\s*\(.*\)$', '', model)
        return model.strip()
    
    # Agar VGOTEL nahi mila to workorder hi return kar do
    return workorder_clean


class SimpleModelReportApp:
    def __init__(self, root):
        self.root = root
        self.root.title("📊 Model Production Report - IMEI1 Count")
        self.root.geometry("1300x800")
        self.root.minsize(1100, 650)
        self.root.configure(bg='#f0f4f8')
        
        # Variables
        self.start_date = tk.StringVar(value="2025-07-01")
        self.end_date = tk.StringVar(value="2026-06-30")
        self.is_generating = False
        self.model_data = {}
        self.total_records = 0
        self.skipped_records = 0
        self.duplicate_count = 0
        
        # Build UI
        self._build_ui()
        self._setup_styles()
        self._bind_shortcuts()
        
        self.status_label.config(text="✅ Ready - All models will be counted by IMEI1")
        self._log_message("🚀 Application started - IMEI1 Based Counting")
        self._log_message(f"📅 Date Range: {self.start_date.get()} to {self.end_date.get()}")
        self._log_message("📊 Counting: All models by unique IMEI1")
        
    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure("Treeview", font=('Segoe UI', 9), rowheight=28)
        style.configure("Treeview.Heading", font=('Segoe UI', 9, 'bold'))
        
    def _build_ui(self):
        # Main Container
        main_frame = tk.Frame(self.root, bg='#f0f4f8')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # ===== HEADER =====
        header_frame = tk.Frame(main_frame, bg='#f0f4f8', height=60)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        header_frame.pack_propagate(False)
        
        header_bg = tk.Frame(header_frame, bg='#1a73e8', height=60)
        header_bg.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(header_bg, text="📊 Model Production Report", 
                font=('Segoe UI', 18, 'bold'), fg='white', bg='#1a73e8').pack(side=tk.LEFT, padx=20)
        
        tk.Label(header_bg, text="IMEI1 Based Counting | All Models", 
                font=('Segoe UI', 10), fg='#d4e2fc', bg='#1a73e8').pack(side=tk.RIGHT, padx=20)
        
        # ===== CONTROL PANEL =====
        control_frame = tk.LabelFrame(main_frame, text="⚙️ Report Settings", 
                                     font=('Segoe UI', 11, 'bold'),
                                     bg='white', fg='#1a73e8',
                                     padx=20, pady=15, relief=tk.GROOVE, bd=2)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Row 1: Date Range
        row1 = tk.Frame(control_frame, bg='white')
        row1.pack(fill=tk.X, pady=5)
        
        tk.Label(row1, text="📅 Date Range:", font=('Segoe UI', 10, 'bold'), 
                bg='white', fg='#2c3e50').pack(side=tk.LEFT, padx=(0, 15))
        
        tk.Label(row1, text="From:", font=('Segoe UI', 9), bg='white', fg='#2c3e50').pack(side=tk.LEFT, padx=(0, 5))
        tk.Entry(row1, textvariable=self.start_date, width=14, 
                font=('Segoe UI', 9), relief=tk.SUNKEN, bd=1,
                bg='#f8f9fa').pack(side=tk.LEFT, padx=(0, 15))
        
        tk.Label(row1, text="To:", font=('Segoe UI', 9), bg='white', fg='#2c3e50').pack(side=tk.LEFT, padx=(0, 5))
        tk.Entry(row1, textvariable=self.end_date, width=14, 
                font=('Segoe UI', 9), relief=tk.SUNKEN, bd=1,
                bg='#f8f9fa').pack(side=tk.LEFT, padx=(0, 15))
        
        # Quick Date Buttons
        btn_frame = tk.Frame(row1, bg='white')
        btn_frame.pack(side=tk.LEFT, padx=10)
        
        for text, cmd in [
            ("📅 This Month", self.set_this_month),
            ("📅 Last Month", self.set_last_month),
            ("📅 Full Year", self.set_full_year),
        ]:
            tk.Button(btn_frame, text=text, command=cmd,
                     bg='#e8f0fe', fg='#1a73e8', font=('Segoe UI', 8),
                     relief=tk.FLAT, cursor='hand2',
                     padx=8, pady=2).pack(side=tk.LEFT, padx=2)
        
        # Row 2: Info
        row2 = tk.Frame(control_frame, bg='white')
        row2.pack(fill=tk.X, pady=8)
        
        tk.Label(row2, text="📊 Counting Method:", font=('Segoe UI', 10, 'bold'), 
                bg='white', fg='#2c3e50').pack(side=tk.LEFT, padx=(0, 15))
        
        tk.Label(row2, text="✅ Unique IMEI1 (PhysicsNo) per Model", 
                bg='#e8f0fe', fg='#1a73e8',
                font=('Segoe UI', 9, 'bold'),
                padx=10, pady=3, relief=tk.GROOVE).pack(side=tk.LEFT)
        
        tk.Label(row2, text="| All Models Counted (No Filter)", 
                bg='white', fg='#dc3545',
                font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=10)
        
        # Row 3: Generate Button + Progress
        row3 = tk.Frame(control_frame, bg='white')
        row3.pack(fill=tk.X, pady=10)
        
        btn_left = tk.Frame(row3, bg='white')
        btn_left.pack(side=tk.LEFT)
        
        self.btn_generate = tk.Button(btn_left, text="🚀 Generate Report", 
                                     command=self.generate_report,
                                     bg='#1a73e8', fg='white',
                                     font=('Segoe UI', 11, 'bold'),
                                     padx=30, pady=10, relief=tk.RAISED,
                                     cursor='hand2')
        self.btn_generate.pack(side=tk.LEFT, padx=(0, 10))
        
        self.btn_export = tk.Button(btn_left, text="💾 Export CSV", 
                                   command=self.export_csv,
                                   bg='#28a745', fg='white',
                                   font=('Segoe UI', 10, 'bold'),
                                   padx=20, pady=10, relief=tk.RAISED,
                                   state=tk.DISABLED, cursor='hand2')
        self.btn_export.pack(side=tk.LEFT, padx=(0, 10))
        
        # Progress
        progress_frame = tk.Frame(row3, bg='white')
        progress_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=10)
        
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                       maximum=100, length=200,
                                       style="green.Horizontal.TProgressbar")
        self.progress.pack(side=tk.LEFT, padx=(0, 10))
        
        self.progress_label = tk.Label(progress_frame, text="0%", 
                                      font=('Segoe UI', 9, 'bold'),
                                      bg='white', fg='#1a73e8')
        self.progress_label.pack(side=tk.LEFT)
        
        # Stats Display
        row4 = tk.Frame(control_frame, bg='white')
        row4.pack(fill=tk.X, pady=5)
        
        self.stats_label = tk.Label(row4, 
                                   text="📊 Total Unique IMEIs: 0 | 📋 Models: 0 | ⚠️ Skipped: 0 | 🔄 Duplicates: 0",
                                   font=('Segoe UI', 9), bg='white', fg='#2c3e50')
        self.stats_label.pack(side=tk.LEFT)
        
        # ===== RESULTS TABLE =====
        table_frame = tk.LabelFrame(main_frame, text="📋 Results - IMEI1 Count by Model", 
                                   font=('Segoe UI', 11, 'bold'),
                                   bg='white', fg='#1a73e8',
                                   padx=10, pady=10, relief=tk.GROOVE, bd=2)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Treeview with Scrollbars
        tree_container = tk.Frame(table_frame, bg='white')
        tree_container.pack(fill=tk.BOTH, expand=True)
        
        vsb = ttk.Scrollbar(tree_container, orient="vertical")
        hsb = ttk.Scrollbar(tree_container, orient="horizontal")
        
        columns = ("S.No", "Model Name", "Unique IMEI1 Count", "Percentage")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings",
                                yscrollcommand=vsb.set, xscrollcommand=hsb.set,
                                height=20)
        
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)
        
        col_config = {
            "S.No": ("#", 50, "center"),
            "Model Name": ("Model Name", 450, "w"),
            "Unique IMEI1 Count": ("Unique IMEI1 Count", 180, "center"),
            "Percentage": ("%", 100, "center")
        }
        
        for col, (heading, width, anchor) in col_config.items():
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, anchor=anchor)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)
        
        # ===== LOG VIEWER =====
        log_frame = tk.LabelFrame(main_frame, text="📋 Processing Log", 
                                 font=('Segoe UI', 10, 'bold'),
                                 bg='white', fg='#1a73e8',
                                 padx=10, pady=5, relief=tk.GROOVE, bd=2)
        log_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=4,
                                                 font=('Consolas', 8),
                                                 bg='#1e1e1e', fg='#d4d4d4',
                                                 relief=tk.SUNKEN, bd=1)
        self.log_text.pack(fill=tk.X, pady=2)
        
        # ===== STATUS BAR =====
        self.status_label = tk.Label(self.root, text="✅ Ready - IMEI1 Based Counting", 
                                    bd=1, relief=tk.SUNKEN, anchor=tk.W,
                                    bg='#e9ecef', font=('Segoe UI', 10, 'bold'), 
                                    padx=10, fg='#1a73e8')
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
        
    def _bind_shortcuts(self):
        self.root.bind('<Control-g>', lambda e: self.generate_report())
        self.root.bind('<Control-e>', lambda e: self.export_csv())
        self.root.bind('<F5>', lambda e: self.generate_report())
        
    def set_this_month(self):
        today = datetime.now().date()
        start = today.replace(day=1)
        self.start_date.set(start.strftime('%Y-%m-%d'))
        self.end_date.set(today.strftime('%Y-%m-%d'))
        self._log_message(f"📅 Date range: This month ({start} to {today})")
        self.status_label.config(text=f"📅 This month: {start} to {today}")
        
    def set_last_month(self):
        today = datetime.now().date()
        first_day_current = today.replace(day=1)
        last_day_last = first_day_current - timedelta(days=1)
        first_day_last = last_day_last.replace(day=1)
        self.start_date.set(first_day_last.strftime('%Y-%m-%d'))
        self.end_date.set(last_day_last.strftime('%Y-%m-%d'))
        self._log_message(f"📅 Date range: Last month ({first_day_last} to {last_day_last})")
        self.status_label.config(text=f"📅 Last month: {first_day_last} to {last_day_last}")
        
    def set_full_year(self):
        self.start_date.set("2025-07-01")
        self.end_date.set("2026-06-30")
        self._log_message("📅 Date range: Full year (2025-07-01 to 2026-06-30)")
        self.status_label.config(text="📅 Full year: 2025-07-01 to 2026-06-30")
    
    def _log_message(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def generate_report(self):
        if self.is_generating:
            return
            
        start_date = self.start_date.get().strip()
        end_date = self.end_date.get().strip()
        
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            messagebox.showerror("Invalid Date", "Please use YYYY-MM-DD format")
            return
        
        if start_date > end_date:
            messagebox.showerror("Invalid Range", "Start date must be before end date")
            return
        
        self.is_generating = True
        self.btn_generate.config(state=tk.DISABLED, text="⏳ Generating...")
        self.btn_export.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.progress_label.config(text="0%")
        
        for row in self.tree.get_children():
            self.tree.delete(row)
        
        self._log_message(f"🚀 Starting report: {start_date} to {end_date}")
        self.status_label.config(text=f"🔄 Generating report...")
        
        thread = threading.Thread(target=self._generate_worker, 
                                 args=(start_date, end_date))
        thread.daemon = True
        thread.start()
        
    def _generate_worker(self, start_date, end_date):
        try:
            self.root.after(0, lambda: self._update_progress(5, "Connecting to database..."))
            
            conn = pyodbc.connect(DB_STR, timeout=30)
            cursor = conn.cursor()
            
            self.root.after(0, lambda: self._update_progress(20, "Fetching records..."))
            
            # Simple query - sirf IMEI1 count ke liye
            query = """
                SELECT 
                    p.WorkOrder,
                    l.PhysicsNo AS IMEI1
                FROM ODM_Packing p
                LEFT JOIN ODM_LinkListofPhysicsNo l ON p.IMEI = l.PhysicsNo
                WHERE CAST(p.RecordDate AS DATE) BETWEEN ? AND ?
            """
            
            cursor.execute(query, start_date, end_date)
            rows = cursor.fetchall()
            conn.close()
            
            total_fetched = len(rows)
            self._log_message(f"📊 Total records fetched: {total_fetched:,}")
            
            self.root.after(0, lambda: self._update_progress(30, f"Processing {total_fetched:,} records..."))
            
            # ===== SIMPLE COUNTING =====
            model_imei_set = defaultdict(set)
            skipped_records = 0
            duplicate_count = 0
            total_unique_imeis = 0
            
            for idx, row in enumerate(rows):
                if idx % 1000 == 0:
                    progress = 30 + (idx / total_fetched) * 60
                    self.root.after(0, lambda p=progress: self._update_progress(p, f"Processing {idx:,}/{total_fetched:,}..."))
                
                workorder = row[0] or ''
                imei1 = row[1] or ''
                
                if not workorder:
                    skipped_records += 1
                    continue
                
                # Model extract karo
                model = extract_model_from_workorder(workorder)
                
                # IMEI1 count
                if imei1:
                    imei_clean = imei1.strip()
                    if imei_clean in model_imei_set[model]:
                        duplicate_count += 1
                    else:
                        model_imei_set[model].add(imei_clean)
                        total_unique_imeis += 1
                else:
                    skipped_records += 1
            
            # Convert sets to counts
            model_counts = {model: len(imei_set) for model, imei_set in model_imei_set.items()}
            
            self.model_data = model_counts
            self.total_records = total_unique_imeis
            self.skipped_records = skipped_records
            self.duplicate_count = duplicate_count
            
            self._log_message(f"📊 Unique Models: {len(model_counts)}")
            self._log_message(f"📊 Unique IMEIs: {total_unique_imeis:,}")
            self._log_message(f"🔄 Duplicate IMEIs: {duplicate_count:,}")
            self._log_message(f"⚠️ Skipped: {skipped_records:,}")
            
            self.root.after(0, lambda: self._update_progress(95, "Displaying results..."))
            self.root.after(0, lambda: self._display_results(model_counts, total_unique_imeis))
            self.root.after(0, lambda: self._update_progress(100, "Complete!"))
            
        except Exception as e:
            self._log_message(f"❌ Error: {str(e)}")
            self.root.after(0, lambda: self._show_error(str(e)))
    
    def _display_results(self, model_counts, total_unique_imeis):
        sorted_models = sorted(model_counts.items(), key=lambda x: x[1], reverse=True)
        
        for idx, (model, count) in enumerate(sorted_models, 1):
            percentage = (count / total_unique_imeis * 100) if total_unique_imeis > 0 else 0
            
            # Color coding
            if count > 1000:
                tag = 'high'
            elif count > 500:
                tag = 'medium'
            else:
                tag = 'low'
            
            self.tree.insert("", tk.END, values=(
                idx,
                model,
                f"{count:,}",
                f"{percentage:.2f}%"
            ), tags=(tag,))
        
        # Configure tags
        self.tree.tag_configure('high', background='#d4edda')
        self.tree.tag_configure('medium', background='#fff3cd')
        self.tree.tag_configure('low', background='#f8f9fa')
        
        # Update stats
        self.stats_label.config(
            text=f"📊 Total Unique IMEIs: {total_unique_imeis:,} | 📋 Models: {len(model_counts)} | ⚠️ Skipped: {self.skipped_records:,} | 🔄 Duplicates: {self.duplicate_count:,}"
        )
        
        self.status_label.config(text=f"✅ Report generated! Total: {total_unique_imeis:,} unique IMEIs, {len(model_counts)} models")
        self.btn_export.config(state=tk.NORMAL)
        
        # Show completion message
        msg = f"✅ REPORT GENERATED!\n\n"
        msg += f"📊 Total Unique IMEIs: {total_unique_imeis:,}\n"
        msg += f"📋 Unique Models: {len(model_counts)}\n"
        msg += f"🔄 Duplicate IMEIs: {self.duplicate_count:,}\n"
        msg += f"⚠️ Skipped Records: {self.skipped_records:,}\n"
        msg += f"\n📅 Date Range: {self.start_date.get()} to {self.end_date.get()}"
        
        self._log_message("✅ Report displayed")
        messagebox.showinfo("✅ Report Generated", msg)
        
        self.is_generating = False
        self.btn_generate.config(state=tk.NORMAL, text="🚀 Generate Report")
        
    def _update_progress(self, value, text):
        self.progress_var.set(value)
        self.progress_label.config(text=f"{int(value)}%")
        self.status_label.config(text=text)
        self.root.update_idletasks()
        
    def _show_error(self, error_msg):
        self.status_label.config(text=f"❌ {error_msg}")
        self._log_message(f"❌ ERROR: {error_msg}")
        messagebox.showerror("Error", error_msg)
        self.is_generating = False
        self.btn_generate.config(state=tk.NORMAL, text="🚀 Generate Report")
        self.progress_var.set(0)
        self.progress_label.config(text="0%")
        
    def export_csv(self):
        if not self.model_data:
            messagebox.showinfo("No Data", "Please generate report first!")
            return
            
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"Model_IMEI_Report_{self.start_date.get()}_to_{self.end_date.get()}.csv"
        )
        
        if not filename:
            return
            
        try:
            sorted_models = sorted(self.model_data.items(), key=lambda x: x[1], reverse=True)
            total = self.total_records
            
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                writer.writerow(['Model Production Report - IMEI1 Based'])
                writer.writerow([f'Date Range: {self.start_date.get()} to {self.end_date.get()}'])
                writer.writerow([f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
                writer.writerow(['Counting Method: Unique IMEI1 (PhysicsNo)'])
                writer.writerow([])
                
                writer.writerow(['S.No', 'Model Name', 'Unique IMEI1 Count', 'Percentage (%)'])
                
                for idx, (model, count) in enumerate(sorted_models, 1):
                    percentage = (count / total * 100) if total > 0 else 0
                    writer.writerow([idx, model, count, f"{percentage:.2f}"])
                
                writer.writerow([])
                writer.writerow(['SUMMARY'])
                writer.writerow(['Total Unique IMEIs', self.total_records])
                writer.writerow(['Unique Models', len(self.model_data)])
                writer.writerow(['Duplicate IMEIs', self.duplicate_count])
                writer.writerow(['Skipped Records', self.skipped_records])
                writer.writerow(['Date Range', f"{self.start_date.get()} to {self.end_date.get()}"])
                writer.writerow(['Report Generated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            
            self.status_label.config(text=f"✅ CSV exported: {os.path.basename(filename)}")
            messagebox.showinfo("Export Successful", f"Report saved to:\n{filename}")
            
        except Exception as e:
            messagebox.showerror("Export Error", str(e))


def main():
    root = tk.Tk()
    app = SimpleModelReportApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()