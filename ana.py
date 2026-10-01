import pandas as pd
import os
from tkinter import *
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from datetime import datetime

class CSVDataAnalyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("CSV Data Analyzer")
        self.root.geometry("1000x700")
        self.root.configure(bg='#f0f0f0')
        
        self.df = None
        self.file_path = None
        
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        
        self.create_widgets()
        
    def create_widgets(self):
        # Top Frame - File Selection
        top_frame = Frame(self.root, bg='#2c3e50', height=100)
        top_frame.pack(fill='x', pady=(0, 10))
        top_frame.pack_propagate(False)
        
        # Title
        Label(top_frame, text="📊 CSV Data Analyzer", 
              font=("Arial", 18, "bold"), 
              fg='white', bg='#2c3e50').pack(pady=(15, 5))
        
        # File Selection Frame
        file_frame = Frame(top_frame, bg='#2c3e50')
        file_frame.pack(pady=5)
        
        self.file_label = Label(file_frame, text="No file selected", 
                                font=("Arial", 10), 
                                fg='#ecf0f1', bg='#2c3e50', 
                                width=50, anchor='w')
        self.file_label.pack(side=LEFT, padx=5)
        
        Button(file_frame, text="📂 Select CSV File", 
               command=self.select_file,
               bg='#3498db', fg='white', font=("Arial", 10, "bold"),
               padx=15, pady=5, cursor='hand2').pack(side=LEFT, padx=5)
        
        Button(file_frame, text="🔄 Refresh", 
               command=self.refresh_data,
               bg='#27ae60', fg='white', font=("Arial", 10, "bold"),
               padx=15, pady=5, cursor='hand2').pack(side=LEFT, padx=5)
        
        # Main Content - Notebook (Tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Tab 1: Summary
        self.summary_tab = Frame(self.notebook, bg='white')
        self.notebook.add(self.summary_tab, text="📊 Summary")
        self.create_summary_tab()
        
        # Tab 2: Detailed Data
        self.data_tab = Frame(self.notebook, bg='white')
        self.notebook.add(self.data_tab, text="📋 Detailed Data")
        self.create_data_tab()
        
        # Tab 3: Charts/Statistics
        self.stats_tab = Frame(self.notebook, bg='white')
        self.notebook.add(self.stats_tab, text="📈 Statistics")
        self.create_stats_tab()
        
        # Status Bar
        self.status_bar = Label(self.root, text="Ready", 
                                relief=SUNKEN, anchor=W,
                                font=("Arial", 9), bg='#ecf0f1')
        self.status_bar.pack(fill='x', side=BOTTOM)
        
    def create_summary_tab(self):
        """Create Summary Tab with all statistics"""
        # Left side - Summary Stats
        left_frame = Frame(self.summary_tab, bg='white')
        left_frame.pack(side=LEFT, fill='both', expand=True, padx=5, pady=5)
        
        # Scrollable text area
        self.summary_text = ScrolledText(left_frame, 
                                         font=("Consolas", 10),
                                         wrap=WORD,
                                         height=30,
                                         bg='#f8f9fa')
        self.summary_text.pack(fill='both', expand=True)
        
        # Right side - Quick Stats Cards
        right_frame = Frame(self.summary_tab, bg='white', width=300)
        right_frame.pack(side=RIGHT, fill='y', padx=5, pady=5)
        right_frame.pack_propagate(False)
        
        # Quick Stats
        Label(right_frame, text="📌 Quick Stats", 
              font=("Arial", 14, "bold"), 
              bg='white').pack(pady=10)
        
        self.stats_cards = {}
        stats = [
            ("Total Records", "0"),
            ("Total Models", "0"),
            ("Total IMEIs", "0"),
            ("Unique Cartons", "0")
        ]
        
        for stat, value in stats:
            card = Frame(right_frame, bg='white', relief=GROOVE, bd=2)
            card.pack(fill='x', padx=10, pady=5)
            
            Label(card, text=stat, font=("Arial", 10), 
                  bg='white', fg='#7f8c8d').pack(anchor=W, padx=10, pady=(5,0))
            
            self.stats_cards[stat] = Label(card, text=value, 
                                           font=("Arial", 16, "bold"),
                                           bg='white', fg='#2c3e50')
            self.stats_cards[stat].pack(anchor=W, padx=10, pady=(0,5))
        
        # Export Button
        Button(right_frame, text="💾 Export to Excel", 
               command=self.export_to_excel,
               bg='#27ae60', fg='white', font=("Arial", 12, "bold"),
               padx=20, pady=10, cursor='hand2').pack(pady=20)
        
        Button(right_frame, text="📋 Copy Summary", 
               command=self.copy_summary,
               bg='#3498db', fg='white', font=("Arial", 12, "bold"),
               padx=20, pady=10, cursor='hand2').pack(pady=5)
        
    def create_data_tab(self):
        """Create Data Tab with table view"""
        # Treeview Frame
        tree_frame = Frame(self.data_tab, bg='white')
        tree_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Scrollbars
        v_scroll = Scrollbar(tree_frame)
        v_scroll.pack(side=RIGHT, fill=Y)
        
        h_scroll = Scrollbar(tree_frame, orient=HORIZONTAL)
        h_scroll.pack(side=BOTTOM, fill=X)
        
        # Treeview
        self.tree = ttk.Treeview(tree_frame, 
                                 yscrollcommand=v_scroll.set,
                                 xscrollcommand=h_scroll.set,
                                 height=20)
        self.tree.pack(fill='both', expand=True)
        
        v_scroll.config(command=self.tree.yview)
        h_scroll.config(command=self.tree.xview)
        
    def create_stats_tab(self):
        """Create Statistics Tab"""
        stats_frame = Frame(self.stats_tab, bg='white')
        stats_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Model-wise statistics
        Label(stats_frame, text="📱 Model-wise Distribution", 
              font=("Arial", 14, "bold"), 
              bg='white').pack(pady=10)
        
        # Model stats table
        model_frame = Frame(stats_frame, bg='white')
        model_frame.pack(fill='both', expand=True)
        
        model_scroll = Scrollbar(model_frame)
        model_scroll.pack(side=RIGHT, fill=Y)
        
        self.model_tree = ttk.Treeview(model_frame, 
                                       columns=('Model', 'Quantity', 'Percentage'),
                                       show='headings',
                                       yscrollcommand=model_scroll.set,
                                       height=15)
        self.model_tree.pack(fill='both', expand=True)
        model_scroll.config(command=self.model_tree.yview)
        
        self.model_tree.heading('Model', text='Model')
        self.model_tree.heading('Quantity', text='Quantity')
        self.model_tree.heading('Percentage', text='Percentage (%)')
        
        self.model_tree.column('Model', width=200)
        self.model_tree.column('Quantity', width=100)
        self.model_tree.column('Percentage', width=100)
        
    def select_file(self):
        """Select CSV file"""
        file_path = filedialog.askopenfilename(
            title="Select CSV File",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )
        
        if file_path:
            self.file_path = file_path
            self.file_label.config(text=f"📁 {os.path.basename(file_path)}")
            self.load_data()
    
    def load_data(self):
        """Load and analyze CSV data"""
        try:
            self.status_bar.config(text="Loading data...")
            self.root.update()
            
            self.df = pd.read_csv(self.file_path)
            
            # Update Quick Stats
            self.update_summary()
            
            # Update Data Table
            self.update_data_table()
            
            # Update Model Stats
            self.update_model_stats()
            
            self.status_bar.config(text=f"Loaded: {os.path.basename(self.file_path)} - {len(self.df)} records")
            
            # Switch to summary tab
            self.notebook.select(self.summary_tab)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file:\n{str(e)}")
            self.status_bar.config(text="Error loading file")
    
    def update_summary(self):
        """Update summary text"""
        if self.df is None:
            return
        
        summary_lines = []
        
        # Header
        summary_lines.append("=" * 80)
        summary_lines.append(f"📊 DATA SUMMARY REPORT")
        summary_lines.append("=" * 80)
        summary_lines.append(f"\n📁 File: {os.path.basename(self.file_path)}")
        summary_lines.append(f"📅 Total Records: {len(self.df):,}")
        summary_lines.append(f"📊 Total Columns: {len(self.df.columns)}")
        
        # Model Summary
        summary_lines.append("\n" + "=" * 80)
        summary_lines.append("📱 MODEL-WISE SUMMARY")
        summary_lines.append("=" * 80)
        
        if 'Model' in self.df.columns:
            model_summary = self.df['Model'].value_counts()
            summary_lines.append(f"\nTotal Unique Models: {len(model_summary)}\n")
            summary_lines.append(f"{'Model':<30} {'Quantity':>15} {'Percentage':>10}")
            summary_lines.append("-" * 55)
            for model, count in model_summary.items():
                percentage = (count / len(self.df)) * 100
                summary_lines.append(f"{str(model)[:30]:<30} {count:>15,} {percentage:>9.1f}%")
            summary_lines.append("-" * 55)
            summary_lines.append(f"{'TOTAL':<30} {len(self.df):>15,} {100.0:>9.1f}%")
            
            # Update Quick Stats - Models
            self.stats_cards["Total Models"].config(text=str(len(model_summary)))
        
        # IMEI Summary
        summary_lines.append("\n" + "=" * 80)
        summary_lines.append("📱 IMEI SUMMARY")
        summary_lines.append("=" * 80)
        
        imei_columns = [col for col in self.df.columns if 'IMEI' in col]
        total_imeis = 0
        for col in imei_columns:
            imei_count = self.df[col].count()
            unique_imeis = self.df[col].nunique()
            total_imeis += imei_count
            summary_lines.append(f"\n📌 {col}:")
            summary_lines.append(f"   - Total: {imei_count:,}")
            summary_lines.append(f"   - Unique: {unique_imeis:,}")
            summary_lines.append(f"   - Duplicates: {imei_count - unique_imeis:,}")
        
        summary_lines.append(f"\n✅ GRAND TOTAL IMEIs: {total_imeis:,}")
        
        # Update Quick Stats
        self.stats_cards["Total IMEIs"].config(text=f"{total_imeis:,}")
        
        # Carton Summary
        summary_lines.append("\n" + "=" * 80)
        summary_lines.append("📦 CARTON ID SUMMARY")
        summary_lines.append("=" * 80)
        
        if 'MidCartonID' in self.df.columns:
            cid_data = self.df['MidCartonID'].dropna()
            cid_data = cid_data[cid_data != '']
            
            summary_lines.append(f"\n📌 Total Cartons: {len(cid_data):,}")
            summary_lines.append(f"📌 Unique Cartons: {cid_data.nunique():,}")
            
            # Update Quick Stats
            self.stats_cards["Unique Cartons"].config(text=str(cid_data.nunique()))
            
            # Top 10
            cid_summary = cid_data.value_counts().head(10)
            summary_lines.append("\n🏆 TOP 10 CARTONS:")
            summary_lines.append(f"{'Carton ID':<30} {'Items':>15} {'%':>10}")
            summary_lines.append("-" * 55)
            for cid, count in cid_summary.items():
                percentage = (count / len(cid_data)) * 100
                summary_lines.append(f"{str(cid)[:30]:<30} {count:>15,} {percentage:>9.1f}%")
        
        # Update Total Records
        self.stats_cards["Total Records"].config(text=f"{len(self.df):,}")
        
        # Update Text widget
        self.summary_text.delete(1.0, END)
        self.summary_text.insert(1.0, "\n".join(summary_lines))
        self.summary_text.config(state=NORMAL)
    
    def update_data_table(self):
        """Update data table with dataframe content"""
        if self.df is None:
            return
        
        # Clear existing data
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Set columns
        columns = list(self.df.columns)
        self.tree['columns'] = columns
        self.tree['show'] = 'headings'
        
        # Configure columns
        for col in columns:
            self.tree.heading(col, text=col)
            # Set column width based on content
            max_width = max(len(str(col)) * 10, 100)
            self.tree.column(col, width=min(max_width, 200))
        
        # Insert data (limit to 1000 rows for performance)
        for _, row in self.df.head(1000).iterrows():
            values = [str(v)[:50] for v in row]
            self.tree.insert('', END, values=values)
    
    def update_model_stats(self):
        """Update model statistics table"""
        if self.df is None or 'Model' not in self.df.columns:
            return
        
        # Clear existing data
        for item in self.model_tree.get_children():
            self.model_tree.delete(item)
        
        # Get model summary
        model_summary = self.df['Model'].value_counts()
        total = len(self.df)
        
        for model, count in model_summary.items():
            percentage = (count / total) * 100
            self.model_tree.insert('', END, values=(model, count, f"{percentage:.1f}%"))
    
    def export_to_excel(self):
        """Export summary to Excel"""
        if self.df is None:
            messagebox.showwarning("Warning", "No data loaded!")
            return
        
        try:
            output_file = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel Files", "*.xlsx")],
                title="Save Summary As"
            )
            
            if output_file:
                with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                    # Sheet 1: Model Summary
                    model_summary = self.df['Model'].value_counts().reset_index()
                    model_summary.columns = ['Model', 'Quantity']
                    model_summary['Percentage'] = (model_summary['Quantity'] / len(self.df) * 100).round(2)
                    model_summary.to_excel(writer, sheet_name='Model Summary', index=False)
                    
                    # Sheet 2: Carton Summary
                    if 'MidCartonID' in self.df.columns:
                        cid_summary = self.df['MidCartonID'].value_counts().reset_index()
                        cid_summary.columns = ['Carton ID', 'Quantity']
                        cid_summary['Percentage'] = (cid_summary['Quantity'] / len(self.df) * 100).round(2)
                        cid_summary.to_excel(writer, sheet_name='Carton Summary', index=False)
                    
                    # Sheet 3: Full Data
                    self.df.to_excel(writer, sheet_name='Full Data', index=False)
                
                messagebox.showinfo("Success", f"Summary exported to:\n{output_file}")
                self.status_bar.config(text=f"Exported to: {os.path.basename(output_file)}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Export failed:\n{str(e)}")
    
    def copy_summary(self):
        """Copy summary to clipboard"""
        summary_text = self.summary_text.get(1.0, END)
        self.root.clipboard_clear()
        self.root.clipboard_append(summary_text)
        self.status_bar.config(text="Summary copied to clipboard!")
        messagebox.showinfo("Success", "Summary copied to clipboard!")
    
    def refresh_data(self):
        """Refresh data"""
        if self.file_path:
            self.load_data()
        else:
            messagebox.showinfo("Info", "Please select a file first!")

# Main execution
if __name__ == "__main__":
    root = Tk()
    app = CSVDataAnalyzer(root)
    root.mainloop()