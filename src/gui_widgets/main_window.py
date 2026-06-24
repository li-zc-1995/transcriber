from __future__ import annotations

import os
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
from src.worker import JobWorker


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
                backend="openai-whisper",
                model=self.settings.whisper_model,
                ffmpeg=self.settings.ffmpeg_path or "ffmpeg",
                keep_wav=self.settings.keep_wav,
                cookies_from_browser=(cookies_browser, None, None, None) if cookies_browser else None,
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

        requests = [
            self._with_runtime_settings(request, ffmpeg)
            for request in self._requests_by_job_id.values()
        ]
        self._thread = QThread(self)
        self._worker = JobWorker(requests)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.event.connect(self.task_list.update_event)
        self._worker.event.connect(self.result_panel.append_event)
        self._worker.result.connect(self.result_panel.show_result)
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
                whisper_model=self.settings.whisper_model,
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

    def cancel_current_job(self) -> None:
        if self._worker is not None:
            self._worker.request_cancel()
            self.cancel_button.setEnabled(False)

    def closeEvent(self, event) -> None:
        self.settings = AppSettings(
            output_dir=self.output_dir_edit.text(),
            ffmpeg_path=self.settings.ffmpeg_path,
            whisper_model=self.settings.whisper_model,
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
            backend=request.backend,
            model=self.settings.whisper_model,
            ffmpeg=ffmpeg,
            keep_wav=self.settings.keep_wav,
            cookies_from_browser=cookies_from_browser,
        )

    def _clear_worker(self) -> None:
        self._thread = None
        self._worker = None
        self.cancel_button.setEnabled(False)
