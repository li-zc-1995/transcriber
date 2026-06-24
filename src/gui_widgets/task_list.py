from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QProgressBar, QTableWidget, QTableWidgetItem

from src.job_events import JobEvent, JobStatus


STATUS_LABELS = {
    JobStatus.QUEUED: "等待中",
    JobStatus.PARSING: "解析中",
    JobStatus.DOWNLOADING: "下载中",
    JobStatus.MERGING: "合并中",
    JobStatus.EXTRACTING_AUDIO: "提取音频",
    JobStatus.TRANSCRIBING: "转写中",
    JobStatus.WRITING_FILES: "写入文件",
    JobStatus.DONE: "完成",
    JobStatus.FAILED: "失败",
    JobStatus.CANCELLED: "已取消",
    JobStatus.CANCELLATION_REQUESTED: "等待取消",
}


class TaskListWidget(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(0, 4, parent)
        self.setHorizontalHeaderLabels(["平台", "链接", "状态", "进度"])
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(True)
        self._rows_by_job_id: dict[str, int] = {}

    def add_task(self, job_id: str, platform: str, url: str) -> None:
        if job_id in self._rows_by_job_id:
            return
        row = self.rowCount()
        self.insertRow(row)
        self._rows_by_job_id[job_id] = row
        self.setItem(row, 0, QTableWidgetItem("Bilibili" if platform == "bilibili" else "抖音"))
        self.setItem(row, 1, QTableWidgetItem(url))
        self.setItem(row, 2, QTableWidgetItem(STATUS_LABELS[JobStatus.QUEUED]))
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(0)
        self.setCellWidget(row, 3, progress)

    def update_event(self, event: JobEvent) -> None:
        row = self._rows_by_job_id.get(event.job_id)
        if row is None:
            return
        label = STATUS_LABELS.get(event.status, event.status.value)
        if event.message:
            label = f"{label} - {event.message}"
        self.item(row, 2).setText(label)
        progress = self.cellWidget(row, 3)
        if isinstance(progress, QProgressBar) and event.progress is not None:
            progress.setValue(max(0, min(100, int(event.progress))))
