## Changelog

### v0.1.3 - 2025-09-29
- Added "Use system Chrome profile" option in GUI to sign in with existing Chrome session
- Fixed Unicode encoding errors in console output (Windows)
- Updated README with troubleshooting guidance for Google sign-in security warnings
- CLI now supports `--chrome-profile-dir` argument for authenticated downloads

### v0.1.2 - 2025-09-29
- Fixed missing export_csv and export_html methods in GUI
- Improved Playwright browser installation and persistent storage
- Added retry logic for browser launch and Google sign-in
- Enhanced download link detection with broader selectors

### v0.1.1 - 2025-09-29
- Simplified UI to a single root folder (auto-derives Zips/Extracted/Google Fotos Backup)
- Added "Save Error Log" diagnostics export
- Fixed duplicate progress callback error during downloads

### v0.1.0 - 2025-09-29
- Initial release of gTakeOutThis
- GUI with Playwright-based sequential downloader (resume + pause)
- ZIP extraction and photo organizer (EXIF/JSON), parallelized
- Progress bars, humanized sizes/speeds, ETA
- Tray minimization, session report with CSV/HTML export
- i18n (EN/ES), CPU priority, worker controls
- PyInstaller spec and Inno Setup installer script
