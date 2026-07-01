from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QThread
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.cli import find_ffmpeg
from src.config import AppSettings, load_settings, save_settings
from src.gui_widgets.platform_input import PlatformInputWidget
from src.gui_widgets.result_panel import ResultPanel
from src.gui_widgets.settings_dialog import SettingsDialog
from src.gui_widgets.task_list import TaskListWidget
from src.job_events import JobRequest
from src.transcriber_job import classify_error
from src.worker import JobWorker


BROWSER_PROCESS_NAMES = {
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
}


def close_browser_processes(browser: str) -> None:
    process_name = BROWSER_PROCESS_NAMES.get(browser)
    if process_name is None:
        return
    subprocess.run(["taskkill", "/IM", process_name, "/T", "/F"], check=False, capture_output=True, text=True)


class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.settings = settings or load_settings()
        self.setWindowTitle("Transcriber")
        self.setFont(QFont("Microsoft YaHei UI", 9))
        self.resize(self.settings.window_width, self.settings.window_height)
        self._url_to_job_id: dict[str, str] = {}
        self._requests_by_job_id: dict[str, JobRequest] = {}
        self._thread: QThread | None = None
        self._worker: JobWorker | None = None
        self._last_failed_job_id: str | None = None

        self.output_dir_edit = QLineEdit(self.settings.output_dir)
        self.output_dir_edit.setReadOnly(True)
        self.select_output_button = QPushButton("选择目录")
        self.open_output_button = QPushButton("打开目录")
        self.cancel_button = QPushButton("取消当前任务")
        self.cancel_button.setEnabled(False)
        self.settings_button = QPushButton("设置")

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.output_dir_edit, 1)
        top_layout.addWidget(self.select_output_button)
        top_layout.addWidget(self.open_output_button)
        top_layout.addWidget(self.cancel_button)
        top_layout.addWidget(self.settings_button)

        self.platform_tabs = QTabWidget()
        self.douyin_input = PlatformInputWidget("douyin")
        self.bilibili_input = PlatformInputWidget("bilibili", self.settings.bilibili_cookies_browser)
        self.platform_tabs.addTab(self.douyin_input, "抖音")
        self.platform_tabs.addTab(self.bilibili_input, "Bilibili")

        self.task_list = TaskListWidget()
        self.result_panel = ResultPanel()

        splitter = QSplitter()
        splitter.addWidget(self.platform_tabs)
        splitter.addWidget(self.task_list)
        splitter.addWidget(self.result_panel)
        splitter.setSizes([320, 430, 520])

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(top_layout)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self.douyin_input.parse_requested.connect(self.add_tasks)
        self.bilibili_input.parse_requested.connect(self.add_tasks)
        self.douyin_input.start_requested.connect(self.start_from_input)
        self.bilibili_input.start_requested.connect(self.start_from_input)
        self.select_output_button.clicked.connect(self.select_output_dir)
        self.open_output_button.clicked.connect(self.open_output_dir)
        self.cancel_button.clicked.connect(self.cancel_current_job)
        self.settings_button.clicked.connect(self.open_settings)
        self.result_panel.failure_action_requested.connect(self.handle_failure_action)

    def add_tasks(self, platform: str, urls: list[str], cookies_browser: str | None) -> None:
        if not urls:
            QMessageBox.information(self, "没有识别到链接", "当前输入区没有识别到该平台支持的视频链接。")
            return
        for url in urls:
            if url in self._url_to_job_id:
                continue
            index = len(self._url_to_job_id) + 1
            job_id = f"{platform}-{index:03d}"
            request = JobRequest(
                url=url,
                platform=platform,
                index=index,
                output_dir=Path(self.output_dir_edit.text()).expanduser().resolve(),
                backend=self.settings.transcription_backend,
                model=self.settings.whisper_model,
                ffmpeg=self.settings.ffmpeg_path or "ffmpeg",
                keep_wav=self.settings.keep_wav,
                cookies_from_browser=(cookies_browser, None, None, None) if cookies_browser else None,
                device=self.settings.whisper_device,
                compute_type=self.settings.whisper_compute_type,
            )
            self._url_to_job_id[url] = job_id
            self._requests_by_job_id[job_id] = request
            self.task_list.add_task(job_id, platform, url)

    def start_from_input(self, platform: str, urls: list[str], cookies_browser: str | None) -> None:
        self.add_tasks(platform, urls, cookies_browser)
        self.start_processing()

    def start_processing(self) -> None:
        if self._thread is not None:
            QMessageBox.information(self, "任务运行中", "当前已有任务在运行。")
            return
        if not self._requests_by_job_id:
            QMessageBox.information(self, "没有任务", "请先解析链接。")
            return
        try:
            ffmpeg = find_ffmpeg(self.settings.ffmpeg_path or None)
        except FileNotFoundError as exc:
            QMessageBox.warning(self, "缺少 ffmpeg", str(exc))
            return

        requests = [self._with_runtime_settings(request, ffmpeg) for request in self._requests_by_job_id.values()]
        self._run_requests(requests)

    def _run_requests(self, requests: list[JobRequest]) -> None:
        if not requests:
            return
        if self._thread is not None:
            QMessageBox.information(self, "任务运行中", "当前已有任务在运行。")
            return
        self._thread = QThread(self)
        self._worker = JobWorker(requests)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.event.connect(self.task_list.update_event)
        self._worker.event.connect(self.result_panel.append_event)
        self._worker.result.connect(self.result_panel.show_result)
        self._worker.failed.connect(self.handle_job_failed)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._clear_worker)
        self.cancel_button.setEnabled(True)
        self._thread.start()

    def select_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_dir_edit.text())
        if directory:
            self.output_dir_edit.setText(directory)
            self.settings = AppSettings(
                output_dir=directory,
                ffmpeg_path=self.settings.ffmpeg_path,
                transcription_backend=self.settings.transcription_backend,
                whisper_model=self.settings.whisper_model,
                whisper_device=self.settings.whisper_device,
                whisper_compute_type=self.settings.whisper_compute_type,
                keep_wav=self.settings.keep_wav,
                bilibili_cookies_browser=self.settings.bilibili_cookies_browser,
                window_width=self.width(),
                window_height=self.height(),
            )
            save_settings(self.settings)

    def open_output_dir(self) -> None:
        path = Path(self.output_dir_edit.text()).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(path)  # type: ignore[attr-defined]

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = dialog.settings(self.width(), self.height())
            self.output_dir_edit.setText(self.settings.output_dir)
            save_settings(self.settings)

    def choose_ffmpeg_path(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 ffmpeg.exe", "", "ffmpeg.exe (ffmpeg.exe);;Executables (*.exe)")
        if not path:
            return
        self.settings = AppSettings(
            output_dir=self.output_dir_edit.text(),
            ffmpeg_path=path,
            transcription_backend=self.settings.transcription_backend,
            whisper_model=self.settings.whisper_model,
            whisper_device=self.settings.whisper_device,
            whisper_compute_type=self.settings.whisper_compute_type,
            keep_wav=self.settings.keep_wav,
            bilibili_cookies_browser=self.settings.bilibili_cookies_browser,
            window_width=self.width(),
            window_height=self.height(),
        )
        save_settings(self.settings)

    def cancel_current_job(self) -> None:
        if self._worker is not None:
            self._worker.request_cancel()
            self.cancel_button.setEnabled(False)

    def handle_job_failed(self, job_id: str, error_text: str) -> None:
        self._last_failed_job_id = job_id
        error = classify_error(Exception(error_text))
        self.result_panel.show_failure_actions(error.kind, error.message, browser=self._failed_cookie_browser(job_id))

    def handle_failure_action(self, action: str) -> None:
        if action in {"chrome", "edge"}:
            index = self.bilibili_input.cookies_combo.findData(action)
            if index >= 0:
                self.bilibili_input.cookies_combo.setCurrentIndex(index)
            self.retry_failed_job()
            return
        if action == "close_browser_retry":
            browser = self._failed_cookie_browser(self._last_failed_job_id)
            if browser:
                index = self.bilibili_input.cookies_combo.findData(browser)
                if index >= 0:
                    self.bilibili_input.cookies_combo.setCurrentIndex(index)
                close_browser_processes(browser)
            self.retry_failed_job()
            return
        if action == "choose_ffmpeg":
            self.choose_ffmpeg_path()

    def retry_failed_job(self) -> None:
        if self._last_failed_job_id is None:
            return
        request = self._requests_by_job_id.get(self._last_failed_job_id)
        if request is None:
            return
        try:
            ffmpeg = find_ffmpeg(self.settings.ffmpeg_path or None)
        except FileNotFoundError as exc:
            QMessageBox.warning(self, "缺少 ffmpeg", str(exc))
            return
        self._run_requests([self._with_runtime_settings(request, ffmpeg)])

    def closeEvent(self, event) -> None:
        self.settings = AppSettings(
            output_dir=self.output_dir_edit.text(),
            ffmpeg_path=self.settings.ffmpeg_path,
            transcription_backend=self.settings.transcription_backend,
            whisper_model=self.settings.whisper_model,
            whisper_device=self.settings.whisper_device,
            whisper_compute_type=self.settings.whisper_compute_type,
            keep_wav=self.settings.keep_wav,
            bilibili_cookies_browser=self.settings.bilibili_cookies_browser,
            window_width=self.width(),
            window_height=self.height(),
        )
        save_settings(self.settings)
        super().closeEvent(event)

    def _with_runtime_settings(self, request: JobRequest, ffmpeg: str) -> JobRequest:
        cookies_from_browser = request.cookies_from_browser
        if request.platform == "bilibili":
            browser = self.bilibili_input.cookies_browser()
            cookies_from_browser = (browser, None, None, None) if browser else None
        return JobRequest(
            url=request.url,
            platform=request.platform,
            index=request.index,
            output_dir=Path(self.output_dir_edit.text()).expanduser().resolve(),
            backend=self.settings.transcription_backend,
            model=self.settings.whisper_model,
            ffmpeg=ffmpeg,
            keep_wav=self.settings.keep_wav,
            cookies_from_browser=cookies_from_browser,
            device=self.settings.whisper_device,
            compute_type=self.settings.whisper_compute_type,
        )

    def _failed_cookie_browser(self, job_id: str | None) -> str | None:
        if job_id is None:
            return None
        request = self._requests_by_job_id.get(job_id)
        if request is None or request.platform != "bilibili":
            return None
        if request.cookies_from_browser:
            return request.cookies_from_browser[0]
        return self.bilibili_input.cookies_browser()

    def _clear_worker(self) -> None:
        self._thread = None
        self._worker = None
        self.cancel_button.setEnabled(False)
