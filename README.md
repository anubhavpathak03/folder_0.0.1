# PCMonitor — Build & Requirements

This repository contains the PCMonitor project (Master and Client). This README explains the required tech stack and step-by-step instructions to create Windows executable(s) using PyInstaller.

**Tech Stack**
- **Python:** 3.10 or newer (3.11 recommended)
- **Virtual environment:** `venv` (Windows) or any virtualenv manager
- **Packaging:** PyInstaller (used to build the EXE)
- **Dependencies:** See [requirement.txt](requirement.txt)

**Why This Tech Stack**
- **Python:** fast to develop, cross-platform, and has a rich ecosystem of packages for networking and system monitoring. The Python standard library (e.g. `os`, `sys`, `subprocess`, `logging`, `threading`, `socket`, `json`, `pathlib`) provides many built-in capabilities so only a few external packages are required.
- **Virtual environment (`venv`):** isolates dependencies per project to avoid conflicts with global packages.
- **PyInstaller:** simple, widely-used tool to package Python apps into Windows executables without requiring users to install Python.

**Dependencies Explained**
Below are the packages listed in `requirement.txt` and why they are used in this project. All of these are external libraries (not part of the Python standard library) and must be installed into your virtual environment.

- **websockets:** Provides WebSocket client/server functionality for real-time bi-directional communication between `master.py` and `client.py`.
- **psutil:** Allows reading system metrics (CPU, memory, disk, process information) which is essential for monitoring a machine's resources.
- **pystray:** Creates a system tray icon and menu on Windows so the client can run in the background with a tray UI.
- **Pillow:** Image processing (PIL fork) used for handling icons, screenshots, or other image tasks.
- **python-dotenv:** Loads configuration from a `.env` or `config.env` file into environment variables so configuration isn't hard-coded.
- **pyinstaller:** Build-time tool to create standalone executables from the Python source. Note: `pyinstaller` is only required when you create the EXE; it does not need to be bundled into the final runtime.

How to tell what's built-in vs external
- Built-in modules are part of the Python standard library and do not appear in `requirement.txt`. If a module import works on a fresh Python install without `pip install`, it is likely built-in. External packages (above) must be installed via `pip` and are listed in `requirement.txt`.


**Files of interest**
- Specs: `PCMonitor_Master.spec`, `PCMonitor_Client.spec` (already present)
- Entrypoints: `master.py`, `client.py`
- Build outputs: `build/` (PyInstaller build artifacts) and `dist/` (final EXEs after PyInstaller run)

Getting started (Windows)
1. Open PowerShell and activate the virtual environment:

```powershell
(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& .\myvenv\Scripts\Activate.ps1)
```

2. Install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirement.txt
pip install pyinstaller
```

Create EXE using existing .spec files
- The repo already includes spec files. To build with them run:

```powershell
pyinstaller PCMonitor_Master.spec
pyinstaller PCMonitor_Client.spec
```

- After successful runs the executables are placed under `dist\` (e.g. `dist\PCMonitor_Master\`)

Create EXE from a Python script (generate a .spec automatically)
1. One-file console app:

```powershell
pyinstaller --onefile master.py
```

2. One-file, windowed (no console) app:

```powershell
pyinstaller --onefile --windowed client.py
```

3. Include additional data files or folders (example):

```powershell
pyinstaller --onefile --add-data "path\to\data;data" --add-data "templates;templates" master.py
```

Notes on `--add-data`: on Windows use a semicolon `;` separator between source and destination inside the bundle. Wrap the whole `source;dest` in quotes.

Where outputs go
- `dist/` — final bundled application (subfolder per bundle or single EXE for `--onefile`)
- `build/` — intermediate build files and logs
- `*.spec` — PyInstaller spec files (can be edited to customize builds)

Common troubleshooting
- Missing modules at runtime: add hidden imports via `--hidden-import package_name` or edit the `.spec` file to include them.
- Large EXE size: use `--onefile` for a single EXE; consider excluding unused packages in the spec.
- Antivirus flags: code-signed binaries reduce false positives; consider using an installer builder (Inno Setup) and signing the final binary.

Advanced: build a Windows installer (optional)
- Use Inno Setup or similar to package the EXE into an installer. Typical steps:
  - Build EXE(s) with PyInstaller
  - Create Inno Setup script that copies the EXE and required resources
  - Compile the installer with Inno Setup Compiler

Tips
- Keep `requirement.txt` up-to-date. To regenerate from your venv:

```powershell
pip freeze > requirement.txt
```

- Rebuild in a clean environment if you hit dependency-related issues.

If you want, I can:
- update this README with exact PyInstaller flags used to create the existing `PCMonitor_*` builds
- add a sample Inno Setup script
