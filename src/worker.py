from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from src.job_events import JobEvent, JobRequest, JobResult
from src.transcriber_job import TranscriberJob


class JobWorker(QObject):
    event = Signal(object)
    result = Signal(object)
    failed = Signal(object, object)
    finished = Signal()

    def __init__(self, requests: list[JobRequest]):
        super().__init__()
        self.requests = requests
        self._current_job: TranscriberJob | None = None

    @Slot()
    def run(self) -> None:
        try:
            for request in self.requests:
                self._current_job = TranscriberJob(request, self._emit_event)
                try:
                    result = self._current_job.run()
                except Exception as exc:
                    self.failed.emit(request.job_id, str(exc))
                    continue
                self.result.emit(result)
        finally:
            self._current_job = None
            self.finished.emit()

    def request_cancel(self) -> None:
        if self._current_job is not None:
            self._current_job.request_cancel()

    def _emit_event(self, event: JobEvent) -> None:
        self.event.emit(event)
