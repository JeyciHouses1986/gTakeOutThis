## gTakeOutThis

A simple Windows app to help you download your Google Takeout photos, unzip them, and organize them by date into folders.

### What you need
- A Windows 10/11 PC
- Your Google Takeout photos download link (from `takeout.google.com`)
- Enough free disk space (the app makes an organized copy)

### Download the app
1) Go to the Releases page and download `gTakeOutThis-windows.zip`:
   - Releases: https://github.com/JeyciHouses1986/gTakeOutThis/releases
2) Right‑click the ZIP → Extract All… → choose a folder (e.g., `C:\Users\<you>\Downloads\gTakeOutThis`).
3) Open the extracted folder and double‑click `gTakeOutThis.exe`.

Note: The first time you use the Download feature, the app will automatically download a browser engine (Playwright) in the background. This is normal and only needs to happen once.

### The app has three main steps
- Download: it opens a browser window and clicks each Takeout part link, one by one. It waits for each to finish before starting the next.
- Extract: it unzips the downloaded files into a folder.
- Organize: it sorts photos into folders by date: Year/Month/Day. If a photo has no date inside, it uses Google’s sidecar JSON or the file’s modified time.

### Step‑by‑step guide
1) Download
   - Copy your Google Takeout download page URL.
   - Open the app and paste the URL into the “Takeout URL” box.
   - Pick a “Download folder” (create one if needed).
   - Click “Download Archives”. A browser window appears — sign in to Google if asked.
   - The app clicks each download link and waits for each to complete. You can click “Pause” any time to stop and continue later.
   - You can minimize the app to the system tray; it keeps working.

2) Extract
   - After downloads finish, set “ZIPs folder” to the same download folder you used above.
   - Pick an “Extract to” folder (for example, add `\extracted` after your download folder).
   - Click “Extract ZIPs”. The app unzips all archives there.

3) Organize
   - Set “Photos folder” to the extraction folder from the previous step.
   - Pick “Organize into” — choose where you want your final organized photos to be (e.g., `Pictures\Organized`).
   - Click “Organize Photos”. Files are moved into Year/Month/Day folders.

### Progress and reports
- You’ll see progress bars, total sizes, download speeds, and ETA.
- When finished, the app shows a summary.
- You can export a report (CSV or HTML) at any time with the Export buttons.

### Pause/Resume & safety
- Click “Pause” during downloads to free bandwidth.
- You can close the app or even shut down the PC. When you start the app again and click Download, it continues and skips files already finished.

### Settings
- Language: switch between English and Spanish in the top area.
- CPU Priority: choose Low/Normal/High if you want the app to use fewer or more PC resources.
- Workers: you can increase or reduce the number of parallel workers for extracting and organizing (advanced; defaults are fine for most users).

### Where your files go
- Downloaded archives: the “Download folder” you selected.
- Extracted files: the “Extract to” folder.
- Final organized photos: the “Organize into” folder, sorted into Year/Month/Day.

### Updates
- The app can check for updates from your GitHub repository.
- To update: download the new ZIP from Releases, extract it, and run the new `gTakeOutThis.exe`.

### Troubleshooting
- Windows SmartScreen warns about running: click “More info” → “Run anyway” (you can also add the folder to Windows Defender exceptions if needed).
- Google sign‑in fails: ensure you’re logged into the correct Google account in the opened browser window.
- Not all links download: re‑run Download; the app continues where it left off and skips what’s already done.
- Not enough disk space: free up space on the drive or choose a different folder on another drive.
- Slow internet: use Pause and resume later; the app saves progress.

### FAQ
- Do I need to install Python? No. The `gTakeOutThis.exe` includes everything it needs.
- Can I move my photos later? Yes. The “Organize into” folder is your final library. You can copy or back it up anywhere.
- Does the app modify photos? It moves files into folders. It reads EXIF/JSON to determine dates; it does not edit the image contents.

### Advanced (optional)
- If you prefer the command line, you can still run:
  - Download: `python -m gtakeout.cli download --url "<URL>" --download-dir "C:\path\to\downloads"`
  - Extract: `python -m gtakeout.cli extract --download-dir "C:\path\to\downloads" --extract-dir "C:\path\to\downloads\extracted"`
  - Organize: `python -m gtakeout.cli organize --source-dir "C:\path\to\downloads\extracted" --dest-dir "C:\path\to\Organized"`

That’s it — just follow Download → Extract → Organize, and your Google Takeout photos will be ready in tidy folders.
