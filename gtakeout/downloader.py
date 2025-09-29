from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import json
from pathlib import Path
from typing import List, Optional, Set, Dict, Any, Callable
from rich.console import Console
from rich.progress import Progress
from playwright.async_api import async_playwright, Page, BrowserContext

console = Console()


ProgressCallback = Callable[[Dict[str, Any]], None]


class CancelToken:
	def __init__(self) -> None:
		self._cancelled = False

	def cancel(self) -> None:
		self._cancelled = True

	@property
	def is_cancelled(self) -> bool:
		return self._cancelled


class DownloadState:
	def __init__(self, state_path: Path) -> None:
		self.state_path = state_path
		self.completed_keys: Set[str] = set()
		self.completed_files: Set[str] = set()
		self._loaded = False

	def load(self) -> None:
		if self.state_path.exists():
			try:
				data = json.loads(self.state_path.read_text(encoding="utf-8"))
				self.completed_keys = set(data.get("completed_keys", []))
				self.completed_files = set(data.get("completed_files", []))
				self._loaded = True
			except Exception:
				self._loaded = True
		else:
			self._loaded = True

	def save(self) -> None:
		data: Dict[str, Any] = {
			"completed_keys": sorted(self.completed_keys),
			"completed_files": sorted(self.completed_files),
		}
		self.state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

	def mark_completed(self, key: Optional[str], filename: Optional[str]) -> None:
		if key:
			self.completed_keys.add(key)
		if filename:
			self.completed_files.add(filename)
		self.save()


async def _collect_download_targets(page: Page) -> List[str]:
	# Collect clickable elements likely to trigger downloads, in DOM order
	selectors = [
		"a[download]",
		"a:has-text('Download')",
		"button:has-text('Download')",
		"a[href$='.zip']",
	]
	seen = set()
	targets: List[str] = []
	for sel in selectors:
		loc = page.locator(sel)
		count = await loc.count()
		for i in range(count):
			elem = loc.nth(i)
			try:
				href = await elem.get_attribute("href")
			except Exception:
				href = None
			key = f"{sel}:{i}:{href or ''}"
			if key in seen:
				continue
			seen.add(key)
			targets.append(key)
	return targets


async def _click_target(page: Page, key: str) -> None:
	# Re-materialize the element by index per selector
	sel, idx, _ = key.split(":", 2)
	idx = int(idx)
	elem = page.locator(sel).nth(idx)
	await elem.scroll_into_view_if_needed()
	await elem.click(delay=50)


def _ensure_persistent_browsers_path() -> None:
    # When frozen (PyInstaller), Playwright defaults under a temp folder that gets deleted.
    # Force a persistent per-user path so browsers survive across runs.
    try:
        if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
            return
        # Windows-friendly local app data location
        base = Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) / "gTakeOutThis" / "playwright-browsers"
        base.mkdir(parents=True, exist_ok=True)
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(base)
    except Exception:
        pass


def _install_browsers_programmatically(target_browser: str) -> None:
    # Always install via subprocess to avoid interfering with current asyncio loop
    env = os.environ.copy()
    for py_cmd in (sys.executable, "python", "py"):
        try:
            subprocess.run([py_cmd, "-m", "playwright", "install", target_browser], check=True, env=env)
            return
        except Exception:
            continue


async def _prepare_context(browser: str, download_dir: Path) -> BrowserContext:
    _ensure_persistent_browsers_path()
    p = await async_playwright().start()
    async def _launch() -> BrowserContext:
        if browser == "firefox":
            browser_obj = await p.firefox.launch(headless=False)
        elif browser == "webkit":
            browser_obj = await p.webkit.launch(headless=False)
        else:
            browser_obj = await p.chromium.launch(headless=False)
        context = await browser_obj.new_context(accept_downloads=True)
        return context

    try:
        return await _launch()
    except Exception as e:
        # Attempt first-run browser install if Playwright runtime is missing
        msg = str(e)
        need_install = (
            "Executable doesn't exist" in msg
            or "browserType.launch" in msg.lower()
            or "Please run the following command to download new browsers" in msg
        )
        if not need_install:
            raise
        # Install browsers to the persistent path and retry
        _install_browsers_programmatically(browser)
        # Retry once after install
        return await _launch()


async def download_all(
	url: str,
	download_dir: Path,
	browser: str = "chromium",
	cancel: Optional[CancelToken] = None,
	resume: bool = True,
	progress_cb: Optional[ProgressCallback] = None,
) -> None:
	download_path = Path(download_dir)
	download_path.mkdir(parents=True, exist_ok=True)

	# Initialize state
	state = DownloadState(download_path / "downloads_state.json")
	state.load()
	# Seed completed files from disk (helps after app restarts)
	for p in download_path.glob("*.zip"):
		state.completed_files.add(p.name)
	state.save()

	context = await _prepare_context(browser, download_path)
	page = await context.new_page()
	await page.goto(url)
	console.print("If prompted, please sign in to Google in the opened browser window.")
	await page.wait_for_timeout(2000)

	targets = await _collect_download_targets(page)
	total_files = len(targets)
	if progress_cb:
		progress_cb({"phase": "download", "event": "start", "total_files": total_files, "completed_files": len(state.completed_keys), "bytes_total": None, "bytes_completed": sum((download_path / f).stat().st_size for f in state.completed_files if (download_path / f).exists())})
	if not targets:
		console.print("[yellow]No download links found. Check the URL or sign-in status.[/]")
		await context.close()
		return

	console.rule("Downloading archives")
	with Progress() as progress:
		task = progress.add_task("Downloading...", total=total_files)
		completed_count = 0
		for key in targets:
			if cancel and cancel.is_cancelled:
				console.print("[yellow]Download paused/cancelled by user.[/]")
				break
			# Skip already completed keys when resuming
			if resume and key in state.completed_keys:
				completed_count += 1
				progress.update(task, completed=completed_count)
				if progress_cb:
					progress_cb({"phase": "download", "event": "file_skipped", "key": key, "completed_files": completed_count, "total_files": total_files})
				continue
			try:
				async with page.expect_download() as download_info:
					await _click_target(page, key)
				download = await download_info.value
				suggested = download.suggested_filename or "download.zip"
				dest_file = download_path / suggested
				if resume and dest_file.exists():
					state.mark_completed(key, suggested)
					completed_count += 1
					progress.update(task, completed=completed_count)
					if progress_cb:
						progress_cb({"phase": "download", "event": "file_complete", "filename": suggested, "completed_files": completed_count, "total_files": total_files, "bytes_completed": sum((download_path / f).stat().st_size for f in state.completed_files if (download_path / f).exists())})
					continue
				filepath = await download.path()
				await download.save_as(str(dest_file))
				state.mark_completed(key, suggested)
				completed_count += 1
				progress.update(task, completed=completed_count)
				if progress_cb:
					progress_cb({"phase": "download", "event": "file_complete", "filename": suggested, "completed_files": completed_count, "total_files": total_files, "bytes_completed": sum((download_path / f).stat().st_size for f in state.completed_files if (download_path / f).exists())})
			except Exception as e:
				console.print(f"[red]Failed to download for target {key}: {e}[/]")
				if progress_cb:
					progress_cb({"phase": "download", "event": "file_error", "key": key, "error": str(e)})
				continue
			finally:
				await asyncio.sleep(0)

	await context.close()
	if progress_cb:
		progress_cb({"phase": "download", "event": "end"})
	console.print("[green]Download session finished.[/]")
