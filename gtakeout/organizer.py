from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List, Tuple
from PIL import Image, ExifTags
from dateutil import tz
from rich.console import Console
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import threading

console = Console()

ProgressCallback = Callable[[Dict[str, Any]], None]


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".tif", ".tiff", ".gif"}


def _find_sidecar_date(photo_path: Path) -> Optional[datetime]:
	# Look for JSON sidecar: same stem + .json, or Google Takeout pattern
	candidates = [
		photo_path.with_suffix(photo_path.suffix + ".json"),  # e.g., IMG_1234.jpg.json
		photo_path.with_suffix(".json"),  # e.g., IMG_1234.json
	]
	for c in candidates:
		if not c.exists():
			continue
		try:
			data = json.loads(c.read_text(encoding="utf-8"))
			ts = None
			if isinstance(data, dict):
				if "photoTakenTime" in data and isinstance(data["photoTakenTime"], dict):
					val = data["photoTakenTime"].get("timestamp") or data["photoTakenTime"].get("seconds")
					ts = int(val) if val is not None else None
				elif "creationTime" in data and isinstance(data["creationTime"], dict):
					val = data["creationTime"].get("timestamp") or data["creationTime"].get("seconds")
					ts = int(val) if val is not None else None
			elif isinstance(data, list) and data and isinstance(data[0], dict):
				val = data[0].get("photoTakenTime", {}).get("timestamp")
				ts = int(val) if val is not None else None
			if ts:
				return datetime.fromtimestamp(ts, tz=tz.tzlocal())
		except Exception:
			continue
	return None


def _get_exif_date(photo_path: Path) -> Optional[datetime]:
	try:
		with Image.open(photo_path) as img:
			exif = img.getexif()
			if not exif:
				return None
			# Map EXIF tags
			tag_map = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
			for key in ("DateTimeOriginal", "DateTimeDigitized", "DateTime"):
				val = tag_map.get(key)
				if not val:
					continue
				# EXIF format: "YYYY:MM:DD HH:MM:SS"
				try:
					dt = datetime.strptime(str(val), "%Y:%m:%d %H:%M:%S")
					return dt
				except Exception:
					continue
	except Exception:
		return None
	return None


def _best_date(photo_path: Path) -> datetime:
	dt = _get_exif_date(photo_path)
	if not dt:
		dt = _find_sidecar_date(photo_path)
	if not dt:
		dt = datetime.fromtimestamp(photo_path.stat().st_mtime, tz=tz.tzlocal())
	return dt


def _ensure_unique_path(dest_dir: Path, filename: str) -> Path:
	target = dest_dir / filename
	if not target.exists():
		return target
	stem = Path(filename).stem
	suffix = Path(filename).suffix
	counter = 2
	while True:
		candidate = dest_dir / f"{stem}-{counter}{suffix}"
		if not candidate.exists():
			return candidate
		counter += 1


def _move_one(path: Path, dest_dir: Path) -> Tuple[str, int]:
	dt = _best_date(path)
	year = f"{dt.year:04d}"
	month = f"{dt.month:02d}"
	day = f"{dt.day:02d}"
	subdir = dest_dir / year / month / day
	subdir.mkdir(parents=True, exist_ok=True)
	target_name = path.name
	target_path = _ensure_unique_path(subdir, target_name)
	size_bytes = path.stat().st_size
	shutil.move(str(path), str(target_path))
	return (target_name, size_bytes)


def organize_photos(
	source_dir: Path,
	dest_dir: Path,
	progress_cb: Optional[ProgressCallback] = None,
	max_workers: Optional[int] = None,
) -> None:
	source_dir = Path(source_dir)
	dest_dir = Path(dest_dir)
	dest_dir.mkdir(parents=True, exist_ok=True)

	all_files = [p for p in source_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
	if progress_cb:
		progress_cb({"phase": "organize", "event": "start", "total_files": len(all_files)})
	if not all_files:
		console.print("[yellow]No photos found to organize.[/]")
		if progress_cb:
			progress_cb({"phase": "organize", "event": "end"})
		return

	# Determine workers
	if max_workers is None:
		try:
			max_workers = max(2, min(8, (os.cpu_count() or 2)))
		except Exception:
			max_workers = 2

	done = 0
	with ThreadPoolExecutor(max_workers=max_workers) as executor:
		futures = {executor.submit(_move_one, p, dest_dir): p for p in all_files}
		for fut in as_completed(futures):
			try:
				name, size_bytes = fut.result()
				done += 1
				if progress_cb:
					progress_cb({"phase": "organize", "event": "file_complete", "filename": name, "file_bytes": size_bytes, "completed_files": done, "total_files": len(all_files)})
			except Exception as e:
				if progress_cb:
					progress_cb({"phase": "organize", "event": "file_error", "error": str(e)})

	console.print(f"[green]Organized {done} photos into {dest_dir}[/]")
	if progress_cb:
		progress_cb({"phase": "organize", "event": "end"})
