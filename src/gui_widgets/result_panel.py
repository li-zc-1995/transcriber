from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.job_events import JobEvent, JobResult


def open_path(path: Path) -> None:
    os.startfile(path)  # type: ignore[attr-defined]


def locate_path(path: Path) -> None:
    subprocess.run(["explorer", f"/select,{path}"], check=False)


class ResultPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.tabs = QTabWidget()
        self.clean_text = QTextEdit()
        self.raw_text = QTextEdit()
        self.log_text = QTextEdit()
        self.files_table = QTableWidget(0, 5)

        for edit in (self.clean_text, self.raw_text, self.log_text):
            edit.setReadOnly(True)

        self.files_table.setHorizontalHeaderLabels(["类型", "路径", "打开", "定位", "复制路径"])
        self.files_table.horizontalHeader().setStretchLastSection(True)
        self.files_table.verticalHeader().setVisible(False)

        self.copy_button = QPushButton("复制当前文案")
        self.copy_button.clicked.connect(self.copy_current_text)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(self.copy_button)

        self.tabs.addTab(self.clean_text, "清洗版")
        self.tabs.addTab(self.raw_text, "原始 ASR")
        self.tabs.addTab(self.log_text, "日志")
        self.tabs.addTab(self.files_table, "文件")

    def append_event(self, event: JobEvent) -> None:
        line = f"[{event.job_id}] {event.status.value} {event.message}"
        if event.detail:
            line = f"{line}\n{event.detail}"
        self.log_text.append(line)

    def show_result(self, result: JobResult) -> None:
        markdown_text = result.markdown_path.read_text(encoding="utf-8", errors="ignore")
        raw_text = result.raw_path.read_text(encoding="utf-8", errors="ignore")
        self.clean_text.setPlainText(markdown_text)
        self.raw_text.setPlainText(raw_text)
        self._show_files(result)

    def copy_current_text(self) -> None:
        current = self.tabs.currentWidget()
        if isinstance(current, QTextEdit):
            QApplication.clipboard().setText(current.toPlainText())

    def _show_files(self, result: JobResult) -> None:
        rows = [
            ("Markdown", result.markdown_path),
            ("Raw", result.raw_path),
            ("视频", result.video_path),
            ("Info JSON", result.info_path),
        ]
        if result.wav_path is not None:
            rows.append(("WAV", result.wav_path))

        self.files_table.setRowCount(0)
        for label, path in rows:
            row = self.files_table.rowCount()
            self.files_table.insertRow(row)
            self.files_table.setItem(row, 0, QTableWidgetItem(label))
            item = QTableWidgetItem(str(path))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsSelectable)
            self.files_table.setItem(row, 1, item)
            self.files_table.setCellWidget(row, 2, self._file_buttons(path, locate=False))
            self.files_table.setCellWidget(row, 3, self._file_buttons(path, locate=True))
            self.files_table.setCellWidget(row, 4, self._copy_path_button(path))

    def _file_buttons(self, path: Path, locate: bool) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton("定位" if locate else "打开")
        button.setEnabled(path.exists())
        button.clicked.connect(lambda: locate_path(path) if locate else open_path(path))
        layout.addWidget(button)
        return container

    def _copy_path_button(self, path: Path) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        button = QPushButton("复制")
        button.setEnabled(path.exists())
        button.clicked.connect(lambda: QApplication.clipboard().setText(str(path)))
        layout.addWidget(button)
        return container
