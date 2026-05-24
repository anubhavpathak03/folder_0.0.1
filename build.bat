@echo off
echo Installing in venv...
myvenv\Scripts\pip install websockets psutil pystray Pillow python-dotenv pyinstaller

echo Building master.exe...
myvenv\Scripts\python -m PyInstaller --onefile --windowed --name "PCMonitor_Master" master.py

echo Building client.exe...
myvenv\Scripts\python -m PyInstaller --onefile --windowed --name "PCMonitor_Client" client.py

echo Done!
pause