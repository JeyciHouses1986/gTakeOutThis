from __future__ import annotations

import csv
import html
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ReportEvent:
	timestamp: datetime
	phase: str
	event: str
	filename: Optional[str] = None
	archive: Optional[str] = None
	key: Optional[str] = None
	bytes_done: Optional[int] = None
	bytes_total: Optional[int] = None
	error: Optional[str] = None


@dataclass
class SessionReport:
	events: List[ReportEvent] = field(default_factory=list)

	def add_event(self, payload: Dict[str, Any], *, ts: Optional[datetime] = None) -> None:
		phase = payload.get("phase") or ""
		event = payload.get("event") or ""
		filename = payload.get("filename")
		archive = payload.get("archive")
		key = payload.get("key")
		bytes_done = payload.get("bytes_done") or payload.get("bytes_completed")
		bytes_total = payload.get("bytes_total")
		error = payload.get("error")
		self.events.append(
			ReportEvent(
				timestamp=ts or datetime.now(),
				phase=str(phase),
				event=str(event),
				filename=str(filename) if filename else None,
				archive=str(archive) if archive else None,
				key=str(key) if key else None,
				bytes_done=int(bytes_done) if isinstance(bytes_done, (int, float)) else None,
				bytes_total=int(bytes_total) if isinstance(bytes_total, (int, float)) else None,
				error=str(error) if error else None,
			)
		)

	def summarize(self) -> Dict[str, Any]:
		counts: Dict[str, int] = {
			"download_completed": 0,
			"download_skipped": 0,
			"download_errors": 0,
			"extract_completed": 0,
			"extract_errors": 0,
			"organize_completed": 0,
			"organize_errors": 0,
		}
		for e in self.events:
			if e.phase == "download":
				if e.event == "file_complete":
					counts["download_completed"] += 1
				elif e.event == "file_skipped":
					counts["download_skipped"] += 1
				elif e.event == "file_error":
					counts["download_errors"] += 1
			elif e.phase == "extract":
				if e.event == "file_complete":
					counts["extract_completed"] += 1
				elif e.event == "file_error":
					counts["extract_errors"] += 1
			elif e.phase == "organize":
				if e.event == "file_complete":
					counts["organize_completed"] += 1
				elif e.event == "file_error":
					counts["organize_errors"] += 1
		return counts

	def export_csv(self, path: Path) -> None:
		path = Path(path)
		path.parent.mkdir(parents=True, exist_ok=True)
		with path.open("w", newline="", encoding="utf-8") as f:
			writer = csv.writer(f)
			writer.writerow(["timestamp", "phase", "event", "filename", "archive", "key", "bytes_done", "bytes_total", "error"])
			for e in self.events:
				writer.writerow([
					e.timestamp.isoformat(timespec="seconds"),
					e.phase,
					e.event,
					e.filename or "",
					e.archive or "",
					e.key or "",
					e.bytes_done if e.bytes_done is not None else "",
					e.bytes_total if e.bytes_total is not None else "",
					e.error or "",
				])

	def export_html(self, path: Path) -> None:
		path = Path(path)
		path.parent.mkdir(parents=True, exist_ok=True)
		rows: List[str] = []
		for e in self.events:
			rows.append(
				"<tr>"+
				f"<td>{html.escape(e.timestamp.isoformat(timespec='seconds'))}</td>"+
				f"<td>{html.escape(e.phase)}</td>"+
				f"<td>{html.escape(e.event)}</td>"+
				f"<td>{html.escape(e.filename or '')}</td>"+
				f"<td>{html.escape(e.archive or '')}</td>"+
				f"<td>{html.escape(e.key or '')}</td>"+
				f"<td>{'' if e.bytes_done is None else e.bytes_done}</td>"+
				f"<td>{'' if e.bytes_total is None else e.bytes_total}</td>"+
				f"<td>{html.escape(e.error or '')}</td>"+
				"</tr>"
			)
		html_doc = (
			"<!doctype html><html><head><meta charset='utf-8'><title>Session Report</title>"
			"<style>table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:4px 8px;font-family:system-ui,Segoe UI,Arial}</style>"
			"</head><body>"
			"<h2>Session Report</h2>"
			"<table>"
			"<thead><tr><th>Timestamp</th><th>Phase</th><th>Event</th><th>Filename</th><th>Archive</th><th>Key</th><th>Bytes Done</th><th>Bytes Total</th><th>Error</th></tr></thead>"
			f"<tbody>{''.join(rows)}</tbody>"
			"</table></body></html>"
		)
		path.write_text(html_doc, encoding="utf-8")
