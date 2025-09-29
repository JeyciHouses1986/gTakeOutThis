## gTakeOutThis

A small CLI/GUI to help download Google Takeout photo archives sequentially, extract ZIPs, and organize photos by date using EXIF data (and Google Takeout JSON sidecars as a fallback).

### App info
- Name: gTakeOutThis
- Version: 0.1.0
- Branding config: see `gtakeout/branding.py` for `APP_NAME`, `APP_VERSION`, `GITHUB_OWNER`, `GITHUB_REPO`.

### Requirements
- Python 3.10+
- Google account with a prepared Takeout download link
- Windows PowerShell (works cross‑platform, but paths below use Windows examples)

### Setup
```bash
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

### Usage (GUI)
Launch the desktop app:
```bash
python -c "from gtakeout.ui import run_gui; run_gui()"
```

### Packaging
- Build executable with PyInstaller:
```bash
pyinstaller installer/gtakeout.spec
```
- Build Windows installer with Inno Setup: open `installer/setup.iss` and compile.
- Set GitHub values in `gtakeout/branding.py` to enable update checks.

Other usage details (CLI and notes) remain the same as above.
