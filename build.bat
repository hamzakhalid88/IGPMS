@echo off
echo Installing PyInstaller...
pip install pyinstaller

echo Building IMEI Lookup Tool...
pyinstaller --onefile --windowed --icon=icon.ico --name="IMEI_Lookup_Tool" --hidden-import=pyodbc --hidden-import=tkinter imei_lookup_app.py

echo Build complete! Check the 'dist' folder.
pause