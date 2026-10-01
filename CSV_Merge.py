import pandas as pd
import os
import glob
from tkinter import Tk, filedialog, Button, Label, Checkbutton, BooleanVar, messagebox, ttk, StringVar, Radiobutton, Frame
from datetime import datetime

class AdvancedFileMerger:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced File Merger (CSV & Excel)")
        self.root.geometry("600x500")
        
        self.files = []
        self.folder_files = []
        self.save_location = ""  # Default save location
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tab 1: Select Files
        self.tab1 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1, text="Select Files")
        self.create_select_files_tab()
        
        # Tab 2: Folder Mode
        self.tab2 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab2, text="Folder Mode")
        self.create_folder_tab()
        
        # Tab 3: Merge Options
        self.tab3 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab3, text="Merge Options")
        self.create_merge_options_tab()
        
        # Status
        self.status_label = Label(root, text="Ready", font=("Arial", 10))
        self.status_label.pack(pady=5)
        
        # Merge Button at bottom
        self.merge_button = Button(root, text="MERGE ALL FILES", command=self.merge_files,
                                  bg="green", fg="white", font=("Arial", 12, "bold"), height=2)
        self.merge_button.pack(fill='x', padx=10, pady=10)
    
    def create_select_files_tab(self):
        Label(self.tab1, text="Select Multiple Files (CSV/Excel)", font=("Arial", 12)).pack(pady=10)
        
        Button(self.tab1, text="Add Files", command=self.select_files,
               bg="blue", fg="white", width=20).pack(pady=5)
        
        self.file_list = Label(self.tab1, text="No files selected", font=("Arial", 9), wraplength=450)
        self.file_list.pack(pady=10)
        
        Button(self.tab1, text="Clear Selected Files", command=self.clear_files,
               bg="orange", fg="white", width=20).pack(pady=5)
    
    def create_folder_tab(self):
        Label(self.tab2, text="Select Folder with Files", font=("Arial", 12)).pack(pady=10)
        
        Button(self.tab2, text="Select Folder", command=self.select_folder,
               bg="purple", fg="white", width=20).pack(pady=5)
        
        self.folder_label = Label(self.tab2, text="No folder selected", font=("Arial", 9), wraplength=450)
        self.folder_label.pack(pady=10)
        
        self.folder_count = Label(self.tab2, text="", font=("Arial", 9))
        self.folder_count.pack(pady=5)
    
    def create_merge_options_tab(self):
        Label(self.tab3, text="Merge Options", font=("Arial", 12)).pack(pady=10)
        
        self.include_headers = BooleanVar(value=True)
        Checkbutton(self.tab3, text="Include headers from each file", 
                   variable=self.include_headers).pack(pady=5)
        
        self.ignore_index = BooleanVar(value=True)
        Checkbutton(self.tab3, text="Reset index in merged file", 
                   variable=self.ignore_index).pack(pady=5)
        
        self.add_source = BooleanVar(value=False)
        Checkbutton(self.tab3, text="Add source filename column", 
                   variable=self.add_source).pack(pady=5)
        
        # Auto-save option
        self.auto_save = BooleanVar(value=False)
        Checkbutton(self.tab3, text="Auto-save without asking (with timestamp)", 
                   variable=self.auto_save).pack(pady=5)
        
        # File type selection for output
        Label(self.tab3, text="Output Format:", font=("Arial", 10)).pack(pady=(10, 0))
        self.output_format = StringVar(value="csv")
        format_frame = Frame(self.tab3)
        format_frame.pack(pady=5)
        Radiobutton(format_frame, text="CSV", variable=self.output_format, 
                   value="csv").pack(side='left', padx=10)
        Radiobutton(format_frame, text="Excel (.xlsx)", variable=self.output_format, 
                   value="xlsx").pack(side='left', padx=10)
    
    def select_files(self):
        self.files = filedialog.askopenfilenames(
            title="Select Files",
            filetypes=[
                ("All Supported Files", "*.csv;*.xlsx;*.xls"),
                ("CSV Files", "*.csv"),
                ("Excel Files", "*.xlsx;*.xls"),
                ("All Files", "*.*")
            ]
        )
        
        if self.files:
            # Show file names with extensions
            file_names = []
            for f in self.files:
                base = os.path.basename(f)
                # Truncate if too long
                if len(base) > 30:
                    base = base[:27] + "..."
                file_names.append(base)
            
            display_text = f"Selected: {len(self.files)} files\n" + "\n".join(file_names[:5])
            if len(self.files) > 5:
                display_text += f"\n... and {len(self.files) - 5} more"
            
            self.file_list.config(text=display_text)
            self.status_label.config(text=f"{len(self.files)} files selected")
            self.folder_files = []  # Clear folder files
            self.folder_label.config(text="No folder selected")
            self.folder_count.config(text="")
        else:
            self.file_list.config(text="No files selected")
            self.status_label.config(text="Ready")
    
    def clear_files(self):
        self.files = []
        self.file_list.config(text="No files selected")
        self.status_label.config(text="Cleared selection")
    
    def select_folder(self):
        folder = filedialog.askdirectory(title="Select Folder with Files")
        
        if folder:
            # Find both CSV and Excel files
            csv_files = glob.glob(os.path.join(folder, "*.csv"))
            excel_files = glob.glob(os.path.join(folder, "*.xlsx")) + glob.glob(os.path.join(folder, "*.xls"))
            all_files = csv_files + excel_files
            
            self.folder_files = all_files
            
            if all_files:
                file_types = []
                if csv_files:
                    file_types.append(f"{len(csv_files)} CSV")
                if excel_files:
                    file_types.append(f"{len(excel_files)} Excel")
                
                self.folder_label.config(text=f"Folder: {folder}")
                self.folder_count.config(text=f"Found {len(all_files)} files ({', '.join(file_types)})")
                self.status_label.config(text=f"{len(all_files)} files found in folder")
            else:
                self.folder_label.config(text=f"Folder: {folder}")
                self.folder_count.config(text="No supported files found in this folder")
                self.status_label.config(text="No supported files found")
                
            self.files = []  # Clear manually selected files
            self.file_list.config(text="No files selected")
    
    def read_file(self, file_path):
        """Read CSV or Excel file based on extension"""
        try:
            if file_path.lower().endswith(('.xlsx', '.xls')):
                # For Excel files, read all sheets and combine them
                excel_file = pd.ExcelFile(file_path)
                dfs = []
                for sheet_name in excel_file.sheet_names:
                    df = pd.read_excel(file_path, sheet_name=sheet_name)
                    if self.add_source.get():
                        df['Source'] = os.path.basename(file_path) + f" [{sheet_name}]"
                    dfs.append(df)
                return pd.concat(dfs, ignore_index=True)
            else:
                # For CSV files
                return pd.read_csv(file_path)
        except Exception as e:
            raise Exception(f"Error reading {os.path.basename(file_path)}: {str(e)}")
    
    def merge_files(self):
        all_files = list(self.files) + self.folder_files
        
        if not all_files:
            messagebox.showerror("Error", "No files selected!\nPlease select files or a folder with files.")
            return
        
        try:
            dfs = []
            total_rows = 0
            failed_files = []
            
            for file_path in all_files:
                try:
                    df = self.read_file(file_path)
                    
                    # Add source column if not already added (for CSV)
                    if self.add_source.get() and not file_path.lower().endswith(('.xlsx', '.xls')):
                        df['Source'] = os.path.basename(file_path)
                    
                    # Handle headers
                    if not self.include_headers.get() and len(dfs) > 0:
                        df.columns = dfs[0].columns
                    
                    dfs.append(df)
                    total_rows += len(df)
                    
                except Exception as e:
                    failed_files.append(os.path.basename(file_path))
                    continue
            
            if not dfs:
                messagebox.showerror("Error", "No valid files to merge!")
                return
            
            merged_df = pd.concat(dfs, ignore_index=self.ignore_index.get())
            
            # Determine output extension
            output_ext = self.output_format.get()
            
            # Check if auto-save is enabled
            if self.auto_save.get():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                
                if output_ext == "csv":
                    output_file = os.path.join(desktop, f"merged_file_{timestamp}.csv")
                    merged_df.to_csv(output_file, index=False)
                else:
                    output_file = os.path.join(desktop, f"merged_file_{timestamp}.xlsx")
                    merged_df.to_excel(output_file, index=False, engine='openpyxl')
                
                success_msg = f"Merged {len(all_files)} files successfully!\nTotal Rows: {len(merged_df):,}\nAuto-saved at: {output_file}"
                if failed_files:
                    success_msg += f"\n\n⚠️ Failed to read: {', '.join(failed_files)}"
                
                messagebox.showinfo("Success", success_msg)
                self.status_label.config(text=f"Merged {len(all_files)} files - Saved on Desktop")
            else:
                # Ask user where to save
                if output_ext == "csv":
                    output_file = filedialog.asksaveasfilename(
                        defaultextension=".csv",
                        filetypes=[("CSV Files", "*.csv")],
                        title="Save Merged File As"
                    )
                else:
                    output_file = filedialog.asksaveasfilename(
                        defaultextension=".xlsx",
                        filetypes=[("Excel Files", "*.xlsx")],
                        title="Save Merged File As"
                    )
                
                if output_file:
                    if output_ext == "csv":
                        merged_df.to_csv(output_file, index=False)
                    else:
                        merged_df.to_excel(output_file, index=False, engine='openpyxl')
                    
                    success_msg = f"Merged {len(all_files)} files successfully!\nTotal Rows: {len(merged_df):,}\nSaved as: {output_file}"
                    if failed_files:
                        success_msg += f"\n\n⚠️ Failed to read: {', '.join(failed_files)}"
                    
                    messagebox.showinfo("Success", success_msg)
                    self.status_label.config(text=f"Merged {len(all_files)} files")
                else:
                    messagebox.showinfo("Cancelled", "Merge cancelled!")
                
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred:\n{str(e)}")

if __name__ == "__main__":
    root = Tk()
    app = AdvancedFileMerger(root)
    root.mainloop()