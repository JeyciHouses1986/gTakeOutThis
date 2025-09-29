from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Iterable, Optional, Callable, Dict, Any, List, Tuple
from rich.console import Console
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import os

console = Console()

ProgressCallback = Callable[[Dict[str, Any]], None]


def _iter_zip_files(root: Path) -> Iterable[Path]:
	for p in root.rglob("*.zip"):
		yield p


def _calc_archive_sizes(archives: List[Path]) -> List[Tuple[Path, int]]:
	sizes: List[Tuple[Path, int]] = []
	for z in archives:
		try:
			with zipfile.ZipFile(z, 'r') as zf:
				total = sum(i.file_size for i in zf.infolist())
			sizes.append((z, total))
		except Exception:
			sizes.append((z, 0))
	return sizes


def _extract_archive(z: Path, extract_dir: Path) -> Tuple[str, int]:
	bytes_done = 0
	with zipfile.ZipFile(z, 'r') as zf:
		for info in zf.infolist():
			zf.extract(info, extract_dir)
			bytes_done += info.file_size
	return (z.name, bytes_done)


def extract_all(
	download_dir: Path,
	extract_dir: Path,
	progress_cb: Optional[ProgressCallback] = None,
	max_workers: Optional[int] = None,
) -> None:
	download_dir = Path(download_dir)
	extract_dir = Path(extract_dir)
	extract_dir.mkdir(parents=True, exist_ok=True)

	archives = list(_iter_zip_files(download_dir))
	if progress_cb:
		progress_cb({"phase": "extract", "event": "start", "total_files": len(archives)})
	if not archives:
		console.print("[yellow]No ZIP files found to extract.[/]")
		if progress_cb:
			progress_cb({"phase": "extract", "event": "end"})
		return

	# Determine workers
	if max_workers is None:
		try:
			max_workers = max(2, min(4, os.cpu_count() or 2))
		except Exception:
			max_workers = 2

	# Pre-calc sizes per archive and global totals
	archive_sizes = _calc_archive_sizes(archives)
	global_total_bytes = sum(s for _, s in archive_sizes)
	global_done_bytes = 0
	lock = threading.Lock()

	with ThreadPoolExecutor(max_workers=max_workers) as executor:
		futures = {executor.submit(_extract_archive, z, extract_dir): (z, size) for z, size in archive_sizes}
		with tqdm(total=len(futures), desc="Extracting archives", unit="archive") as pbar:
			for fut in as_completed(futures):
				z, size = futures[fut]
				try:
					name, bytes_done = fut.result()
					with lock:
						global_done_bytes += bytes_done
					pbar.update(1)
					if progress_cb:
						progress_cb({
							"phase": "extract",
							"event": "file_progress",
							"archive": name,
							"bytes_done": global_done_bytes,
							"bytes_total": global_total_bytes,
						})
					if progress_cb:
						progress_cb({"phase": "extract", "event": "file_complete", "archive": name})
				except Exception as e:
					if progress_cb:
						progress_cb({"phase": "extract", "event": "file_error", "archive": z.name, "error": str(e)})
	console.print("[green]Extraction complete.[/]")
	if progress_cb:
		progress_cb({"phase": "extract", "event": "end"})
