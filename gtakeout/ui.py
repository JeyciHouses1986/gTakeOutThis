from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
	QApplication,
	QComboBox,
	QFileDialog,
	QGridLayout,
	QHBoxLayout,
	QLabel,
	QLineEdit,
	QMainWindow,
	QPushButton,
	QStatusBar,
	QTextEdit,
	QVBoxLayout,
	QWidget,
	QSystemTrayIcon,
	QMenu,
	QProgressBar,
	QMessageBox,
	QSpinBox,
)
from PySide6.QtGui import QIcon, QPixmap, QColor, QAction, QCloseEvent

from .downloader import download_all, CancelToken
from .extractor import extract_all
from .organizer import organize_photos
from .utils import format_bytes, format_duration, estimate_eta_from_counts, estimate_eta_from_bytes, set_process_priority, set_language, t
from .report import SessionReport
from .updater import get_latest_release, open_releases_page
from .branding import APP_NAME, APP_VERSION, GITHUB_OWNER, GITHUB_REPO, WINDOW_TITLE


class Worker(QObject):
	progress = Signal(dict)
	finished = Signal(bool, str)

	def __init__(self, fn, *args, **kwargs):
		super().__init__()
		self.fn = fn
		self.args = args
		self.kwargs = kwargs
		self.kwargs.setdefault("progress_cb", self._emit_progress)

	def _emit_progress(self, payload: Dict[str, Any]) -> None:
		self.progress.emit(payload)

	@Slot()
	def run(self) -> None:
		try:
			self.fn(*self.args, **self.kwargs)
			self.finished.emit(True, "Done")
		except Exception as e:
			self.finished.emit(False, str(e))


class AsyncWorker(QObject):
	progress = Signal(dict)
	finished = Signal(bool, str)

	def __init__(self, coro_fn, *args, **kwargs):
		super().__init__()
		self.coro_fn = coro_fn
		self.args = args
		self.kwargs = kwargs
		self.kwargs.setdefault("progress_cb", self._emit_progress)

	def _emit_progress(self, payload: Dict[str, Any]) -> None:
		self.progress.emit(payload)

	@Slot()
	def run(self) -> None:
		try:
			asyncio.run(self.coro_fn(*self.args, **self.kwargs))
			self.finished.emit(True, "Done")
		except Exception as e:
			self.finished.emit(False, str(e))


class MainWindow(QMainWindow):
	def __init__(self) -> None:
		super().__init__()
		self.setWindowTitle(WINDOW_TITLE)

		central = QWidget()
		self.setCentralWidget(central)

		layout = QVBoxLayout(central)

		# URL + Browser + Download dir
		grid = QGridLayout()
		layout.addLayout(grid)

		self.url_edit = QLineEdit()
		self.browser_combo = QComboBox()
		self.browser_combo.addItems(["chromium", "firefox", "webkit"])
		self.download_edit = QLineEdit()
		btn_pick_download = QPushButton("Browse…")
		btn_pick_download.clicked.connect(self.pick_download_dir)

		grid.addWidget(QLabel("Takeout URL:"), 0, 0)
		grid.addWidget(self.url_edit, 0, 1, 1, 3)
		grid.addWidget(QLabel("Browser:"), 1, 0)
		grid.addWidget(self.browser_combo, 1, 1)
		grid.addWidget(QLabel("Download folder:"), 2, 0)
		grid.addWidget(self.download_edit, 2, 1, 1, 2)
		grid.addWidget(btn_pick_download, 2, 3)

		# Priority + Language + Worker limits
		grid.addWidget(QLabel("CPU Priority:"), 3, 0)
		self.priority_combo = QComboBox()
		self.priority_combo.addItems(["low", "normal", "high"])
		self.priority_combo.currentTextChanged.connect(set_process_priority)
		grid.addWidget(self.priority_combo, 3, 1)

		grid.addWidget(QLabel("Language:"), 3, 2)
		self.lang_combo = QComboBox()
		self.lang_combo.addItems(["en", "es"])
		self.lang_combo.currentTextChanged.connect(self._on_lang_changed)
		grid.addWidget(self.lang_combo, 3, 3)

		grid.addWidget(QLabel("Extract workers:"), 4, 0)
		self.spn_extract_workers = QSpinBox()
		self.spn_extract_workers.setRange(1, 16)
		self.spn_extract_workers.setValue(4)
		grid.addWidget(self.spn_extract_workers, 4, 1)

		grid.addWidget(QLabel("Organize workers:"), 4, 2)
		self.spn_organize_workers = QSpinBox()
		self.spn_organize_workers.setRange(1, 32)
		self.spn_organize_workers.setValue(8)
		grid.addWidget(self.spn_organize_workers, 4, 3)

		row = QHBoxLayout()
		self.btn_download = QPushButton(t("download_archives"))
		self.btn_pause = QPushButton(t("pause"))
		self.btn_pause.setEnabled(False)
		row.addWidget(self.btn_download)
		row.addWidget(self.btn_pause)
		layout.addLayout(row)
		self.btn_download.clicked.connect(self.start_download)
		self.btn_pause.clicked.connect(self.pause_download)

		# Progress labels + bars
		self.lbl_download = QLabel("Download: 0/0 files, 0 bytes")
		self.pb_download = QProgressBar()
		self.pb_download.setRange(0, 100)
		self.pb_download.setValue(0)
		self.lbl_extract = QLabel("Extract: 0/0 archives, 0/0 bytes")
		self.pb_extract = QProgressBar()
		self.pb_extract.setRange(0, 100)
		self.pb_extract.setValue(0)
		self.lbl_organize = QLabel("Organize: 0/0 files")
		self.pb_organize = QProgressBar()
		self.pb_organize.setRange(0, 100)
		self.pb_organize.setValue(0)
		layout.addWidget(self.lbl_download)
		layout.addWidget(self.pb_download)
		layout.addWidget(self.lbl_extract)
		layout.addWidget(self.pb_extract)
		layout.addWidget(self.lbl_organize)
		layout.addWidget(self.pb_organize)

		# Export + Update buttons
		export_row = QHBoxLayout()
		self.btn_export_csv = QPushButton(t("export_csv"))
		self.btn_export_html = QPushButton(t("export_html"))
		self.btn_check_update = QPushButton("Check for Updates")
		export_row.addWidget(self.btn_export_csv)
		export_row.addWidget(self.btn_export_html)
		export_row.addWidget(self.btn_check_update)
		layout.addLayout(export_row)
		self.btn_export_csv.clicked.connect(self.export_csv)
		self.btn_export_html.clicked.connect(self.export_html)
		self.btn_check_update.clicked.connect(self.check_updates)

		# Extract
		grid2 = QGridLayout()
		layout.addLayout(grid2)
		self.extract_src_edit = QLineEdit()
		self.extract_dst_edit = QLineEdit()
		btn_pick_ex_src = QPushButton("Browse…")
		btn_pick_ex_dst = QPushButton("Browse…")
		btn_pick_ex_src.clicked.connect(lambda: self.pick_folder_into(self.extract_src_edit))
		btn_pick_ex_dst.clicked.connect(lambda: self.pick_folder_into(self.extract_dst_edit))
		grid2.addWidget(QLabel("ZIPs folder:"), 0, 0)
		grid2.addWidget(self.extract_src_edit, 0, 1)
		grid2.addWidget(btn_pick_ex_src, 0, 2)
		grid2.addWidget(QLabel("Extract to:"), 1, 0)
		grid2.addWidget(self.extract_dst_edit, 1, 1)
		grid2.addWidget(btn_pick_ex_dst, 1, 2)
		btn_extract = QPushButton("Extract ZIPs")
		btn_extract.clicked.connect(self.start_extract)
		layout.addWidget(btn_extract)

		# Organize
		grid3 = QGridLayout()
		layout.addLayout(grid3)
		self.org_src_edit = QLineEdit()
		self.org_dst_edit = QLineEdit()
		btn_pick_org_src = QPushButton("Browse…")
		btn_pick_org_dst = QPushButton("Browse…")
		btn_pick_org_src.clicked.connect(lambda: self.pick_folder_into(self.org_src_edit))
		btn_pick_org_dst.clicked.connect(lambda: self.pick_folder_into(self.org_dst_edit))
		grid3.addWidget(QLabel("Photos folder:"), 0, 0)
		grid3.addWidget(self.org_src_edit, 0, 1)
		grid3.addWidget(btn_pick_org_src, 0, 2)
		grid3.addWidget(QLabel("Organize into:"), 1, 0)
		grid3.addWidget(self.org_dst_edit, 1, 1)
		grid3.addWidget(btn_pick_org_dst, 1, 2)
		btn_organize = QPushButton("Organize Photos")
		btn_organize.clicked.connect(self.start_organize)
		layout.addWidget(btn_organize)

		# Log output
		self.log = QTextEdit(readOnly=True)
		layout.addWidget(self.log)

		self.setStatusBar(QStatusBar())

		self._cancel_token: Optional[CancelToken] = None
		self._download_thread: Optional[QThread] = None
		self._download_worker: Optional[AsyncWorker] = None
		self._download_total: int = 0
		self._download_completed: int = 0
		self._download_bytes: int = 0
		self._download_start_ts: Optional[float] = None

		self._tray: Optional[QSystemTrayIcon] = None
		self._create_tray_icon()

		self._report = SessionReport()

	def check_updates(self) -> None:
		latest = get_latest_release(GITHUB_OWNER, GITHUB_REPO)
		if not latest:
			QMessageBox.information(self, "Updates", "Could not determine latest release.")
			return
		if latest.lstrip("v") != APP_VERSION:
			ret = QMessageBox.question(self, "Updates", f"New version {latest} available. Open releases page?")
			if ret == QMessageBox.Yes:
				open_releases_page(GITHUB_OWNER, GITHUB_REPO)
		else:
			QMessageBox.information(self, "Updates", "You are on the latest version.")

	def _on_lang_changed(self, lang: str) -> None:
		set_language(lang)
		self.btn_download.setText(t("download_archives"))
		self.btn_pause.setText(t("pause"))
		self.btn_export_csv.setText(t("export_csv"))
		self.btn_export_html.setText(t("export_html"))

	def _create_tray_icon(self) -> None:
		pix = QPixmap(16, 16)
		pix.fill(QColor("#2d7ef7"))
		icon = QIcon(pix)
		tray = QSystemTrayIcon(icon, self)
		tray.setToolTip(APP_NAME)

		menu = QMenu(self)
		a_show = QAction("Show", self)
		a_pause = QAction("Pause Download", self)
		a_exit = QAction("Exit", self)
		a_show.triggered.connect(self._tray_show)
		a_pause.triggered.connect(self.pause_download)
		a_exit.triggered.connect(QApplication.instance().quit)
		menu.addAction(a_show)
		menu.addAction(a_pause)
		menu.addSeparator()
		menu.addAction(a_exit)
		tray.setContextMenu(menu)
		tray.activated.connect(self._tray_activated)
		tray.show()
		self._tray = tray

	def _tray_show(self) -> None:
		self.showNormal()
		self.raise_()
		self.activateWindow()

	def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
		if reason == QSystemTrayIcon.Trigger:
			if self.isHidden():
				self._tray_show()
			else:
				self.hide()

	def _update_tray_tooltip(self) -> None:
		if not self._tray:
			return
		self._tray.setToolTip(f"{APP_NAME}: {self._download_completed}/{self._download_total} files, {format_bytes(self._download_bytes)}")

	def append_log(self, text: str) -> None:
		self.log.append(text)
		self.statusBar().showMessage(text, 5000)

	def pick_download_dir(self) -> None:
		p = QFileDialog.getExistingDirectory(self, "Select download folder")
		if p:
			self.download_edit.setText(p)

	def pick_folder_into(self, line_edit: QLineEdit) -> None:
		p = QFileDialog.getExistingDirectory(self, "Select folder")
		if p:
			line_edit.setText(p)

	def start_download(self) -> None:
		url = self.url_edit.text().strip()
		dir_path = Path(self.download_edit.text().strip())
		browser = self.browser_combo.currentText()
		if not url or not dir_path:
			self.append_log("Please provide URL and download folder")
			return
		self.btn_download.setEnabled(False)
		self.btn_pause.setEnabled(True)
		self._cancel_token = CancelToken()
		self._download_start_ts = time.time()
		worker = AsyncWorker(download_all, url, dir_path, browser, self._cancel_token, True, self._on_progress)
		self._start_download_worker(worker)
		self.hide()
		if self._tray:
			self._tray.showMessage("Downloading", "Downloads in progress. Click to show/hide.", QSystemTrayIcon.Information, 2000)

	def pause_download(self) -> None:
		if self._cancel_token:
			self._cancel_token.cancel()
			self.append_log("Paused. You can close the app and resume later.")

	def _start_download_worker(self, worker: AsyncWorker) -> None:
		thread = QThread(self)
		self._download_thread = thread
		self._download_worker = worker
		worker.moveToThread(thread)
		thread.started.connect(worker.run)
		worker.progress.connect(self._on_progress)
		worker.finished.connect(lambda ok, msg: self.append_log(msg))
		worker.finished.connect(self._on_download_finished)
		worker.finished.connect(worker.deleteLater)
		thread.finished.connect(thread.deleteLater)
		thread.start()

	def _on_download_finished(self, ok: bool, msg: str) -> None:
		self.btn_download.setEnabled(True)
		self.btn_pause.setEnabled(False)
		self._cancel_token = None
		self._download_start_ts = None
		self._tray_show()
		if self._tray:
			self._tray.showMessage("Download finished", msg or "", QSystemTrayIcon.Information, 3000)
		s = self._report.summarize()
		QMessageBox.information(self, t("summary_title"), f"Downloaded: {s['download_completed']} (skipped {s['download_skipped']}), Errors: {s['download_errors']}\nExtracted: {s['extract_completed']} (errors {s['extract_errors']})\nOrganized: {s['organize_completed']} (errors {s['organize_errors']})")

	def start_extract(self) -> None:
		src = Path(self.extract_src_edit.text().strip())
		dst = Path(self.extract_dst_edit.text().strip())
		if not src or not dst:
			self.append_log("Please provide ZIPs folder and destination")
			return
		worker = Worker(extract_all, src, dst, max_workers=self.spn_extract_workers.value())
		self._start_worker(worker)
		worker.progress.connect(self._on_progress)

	def start_organize(self) -> None:
		src = Path(self.org_src_edit.text().strip())
		dst = Path(self.org_dst_edit.text().strip())
		if not src or not dst:
			self.append_log("Please provide source and destination")
			return
		worker = Worker(organize_photos, src, dst, max_workers=self.spn_organize_workers.value())
		self._start_worker(worker)
		worker.progress.connect(self._on_progress)

	def _start_worker(self, worker: QObject) -> None:
		thread = QThread(self)
		worker.moveToThread(thread)
		thread.started.connect(worker.run)
		worker.finished.connect(lambda ok, msg: self.append_log(msg))
		worker.finished.connect(thread.quit)
		worker.finished.connect(worker.deleteLater)
		thread.finished.connect(thread.deleteLater)
		thread.start()

	def export_csv(self) -> None:
		path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "session_report.csv", "CSV Files (*.csv)")
		if not path:
			return
		self._report.export_csv(Path(path))
		QMessageBox.information(self, "Export", "CSV report saved.")

	def export_html(self) -> None:
		path, _ = QFileDialog.getSaveFileName(self, "Save HTML", "session_report.html", "HTML Files (*.html)")
		if not path:
			return
		self._report.export_html(Path(path))
		QMessageBox.information(self, "Export", "HTML report saved.")

	@Slot(dict)
	def _on_progress(self, payload: Dict[str, Any]) -> None:
		self._report.add_event(payload)
		phase = payload.get("phase")
		if phase == "download":
			if payload.get("event") == "start":
				self._download_total = payload.get("total_files", 0)
				self._download_completed = payload.get("completed_files", 0)
				self._download_bytes = payload.get("bytes_completed", 0) or 0
				self._download_start_ts = self._download_start_ts or time.time()
			elif payload.get("event") in {"file_complete", "file_skipped"}:
				self._download_completed = payload.get("completed_files", self._download_completed)
				self._download_bytes = payload.get("bytes_completed", self._download_bytes) or self._download_bytes
			from .utils import estimate_eta_from_counts
			elapsed = 0.0 if not self._download_start_ts else (time.time() - self._download_start_ts)
			eta_items = estimate_eta_from_counts(self._download_completed, self._download_total, elapsed)
			speed_str = f" at {format_bytes(int(self._download_bytes/elapsed))}/s" if elapsed > 0 and self._download_bytes > 0 else ""
			eta_str = f", ETA {format_duration(eta_items)}" if eta_items is not None else ""
			self.lbl_download.setText(f"Download: {self._download_completed}/{self._download_total} files, {format_bytes(self._download_bytes)}{speed_str}{eta_str}")
			pct = 0 if self._download_total == 0 else int(100 * self._download_completed / max(1, self._download_total))
			self.pb_download.setValue(pct)
			self._update_tray_tooltip()
		elif phase == "extract":
			evt = payload.get("event")
			if evt == "start":
				self._extract_total = payload.get("total_files", 0)
				self._extract_done = 0
				self._extract_bytes_done = 0
				self._extract_bytes_total = 0
				self._extract_start_ts = time.time()
			elif evt == "file_progress":
				self._extract_bytes_done = payload.get("bytes_done", 0)
				self._extract_bytes_total = payload.get("bytes_total", 0)
			elif evt == "file_complete":
				self._extract_done = getattr(self, "_extract_done", 0) + 1
			from .utils import estimate_eta_from_bytes
			elapsed = max(0.0, time.time() - getattr(self, "_extract_start_ts", time.time()))
			speed = 0 if elapsed <= 0 else int(self._extract_bytes_done / elapsed)
			eta = estimate_eta_from_bytes(self._extract_bytes_done, max(1, self._extract_bytes_total), elapsed)
			eta_str = f", ETA {format_duration(eta)}" if eta is not None else ""
			self.lbl_extract.setText(
				f"Extract: {getattr(self, '_extract_done', 0)}/{getattr(self, '_extract_total', 0)} archives, {format_bytes(getattr(self, '_extract_bytes_done', 0))}/{format_bytes(max(1, getattr(self, '_extract_bytes_total', 0)))} at {format_bytes(speed)}/s{eta_str}"
			)
			pct = 0 if getattr(self, "_extract_bytes_total", 0) == 0 else int(100 * getattr(self, "_extract_bytes_done", 0) / max(1, getattr(self, "_extract_bytes_total", 0)))
			self.pb_extract.setValue(pct)
		elif phase == "organize":
			evt = payload.get("event")
			if evt == "start":
				self._org_total = payload.get("total_files", 0)
				self._org_done = 0
				self._org_start_ts = time.time()
			elif evt == "file_complete":
				self._org_done = payload.get("completed_files", self._org_done)
			elapsed = max(0.0, time.time() - getattr(self, "_org_start_ts", time.time()))
			eta_items = estimate_eta_from_counts(getattr(self, "_org_done", 0), max(1, getattr(self, "_org_total", 0)), elapsed)
			eta_str = f", ETA {format_duration(eta_items)}" if eta_items is not None else ""
			self.lbl_organize.setText(f"Organize: {getattr(self, '_org_done', 0)}/{getattr(self, '_org_total', 0)} files{eta_str}")
			pct = 0 if getattr(self, "_org_total", 0) == 0 else int(100 * getattr(self, "_org_done", 0) / max(1, self._org_total))
			self.pb_organize.setValue(pct)

	def closeEvent(self, event) -> None:
		if self.btn_pause.isEnabled():
			self.hide()
			if self._tray:
				self._tray.showMessage("Still downloading", "App minimized to tray.", QSystemTrayIcon.Information, 2000)
			event.ignore()
			return
		event.accept()


def run_gui() -> None:
	app = QApplication([])
	win = MainWindow()
	win.resize(900, 820)
	win.show()
	app.exec()
