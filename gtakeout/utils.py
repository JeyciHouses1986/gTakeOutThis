from __future__ import annotations

from typing import Optional, Dict


def format_bytes(num_bytes: int) -> str:
	units = ["B", "KB", "MB", "GB", "TB"]
	size = float(num_bytes)
	unit_idx = 0
	while size >= 1024.0 and unit_idx < len(units) - 1:
		size /= 1024.0
		unit_idx += 1
	if unit_idx == 0:
		return f"{int(size)} {units[unit_idx]}"
	return f"{size:.2f} {units[unit_idx]}"


def format_duration(seconds: float) -> str:
	seconds = max(0.0, float(seconds))
	mins, secs = divmod(int(seconds), 60)
	hours, mins = divmod(mins, 60)
	if hours:
		return f"{hours}h {mins}m {secs}s"
	if mins:
		return f"{mins}m {secs}s"
	return f"{secs}s"


def estimate_eta_from_counts(completed: int, total: int, elapsed_seconds: float) -> Optional[float]:
	if completed <= 0 or total <= 0 or completed >= total or elapsed_seconds <= 0:
		return None
	per_item = elapsed_seconds / completed
	remaining = total - completed
	return per_item * remaining


def estimate_eta_from_bytes(bytes_done: int, bytes_total: int, elapsed_seconds: float) -> Optional[float]:
	if bytes_done <= 0 or bytes_total <= 0 or elapsed_seconds <= 0 or bytes_done >= bytes_total:
		return None
	rate = bytes_done / elapsed_seconds
	remaining = bytes_total - bytes_done
	if rate <= 0:
		return None
	return remaining / rate

# Process priority helpers (Windows-friendly)

def set_process_priority(level: str) -> None:
	try:
		import psutil, os
		p = psutil.Process(os.getpid())
		if level == "low":
			p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS if hasattr(psutil, 'BELOW_NORMAL_PRIORITY_CLASS') else 10)
		elif level == "normal":
			p.nice(psutil.NORMAL_PRIORITY_CLASS if hasattr(psutil, 'NORMAL_PRIORITY_CLASS') else 0)
		elif level == "high":
			p.nice(psutil.HIGH_PRIORITY_CLASS if hasattr(psutil, 'HIGH_PRIORITY_CLASS') else -10)
	except Exception:
		pass

# Simple i18n
_LANG = "en"
_STRINGS: Dict[str, Dict[str, str]] = {
	"en": {
		"download_archives": "Download Archives",
		"pause": "Pause",
		"zips_folder": "ZIPs folder:",
		"extract_to": "Extract to:",
		"extract_zips": "Extract ZIPs",
		"photos_folder": "Photos folder:",
		"organize_into": "Organize into:",
		"organize_photos": "Organize Photos",
		"export_csv": "Export CSV Report",
		"export_html": "Export HTML Report",
		"summary_title": "Summary",
	},
	"es": {
		"download_archives": "Descargar archivos",
		"pause": "Pausar",
		"zips_folder": "Carpeta de ZIPs:",
		"extract_to": "Extraer en:",
		"extract_zips": "Extraer ZIPs",
		"photos_folder": "Carpeta de fotos:",
		"organize_into": "Organizar en:",
		"organize_photos": "Organizar fotos",
		"export_csv": "Exportar informe CSV",
		"export_html": "Exportar informe HTML",
		"summary_title": "Resumen",
	},
}


def set_language(lang: str) -> None:
	global _LANG
	if lang in _STRINGS:
		_LANG = lang


def t(key: str) -> str:
	return _STRINGS.get(_LANG, {}).get(key, _STRINGS["en"].get(key, key))
