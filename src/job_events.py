from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class JobStatus(StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    DOWNLOADING = "downloading"
    MERGING = "merging"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    WRITING_FILES = "writing_files"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CANCELLATION_REQUESTED = "cancellation_requested"


@dataclass(frozen=True)
class JobRequest:
    url: str
    platform: str
    index: int
    output_dir: Path
    backend: str
    model: str
    ffmpeg: str
    keep_wav: bool
    cookies_from_browser: tuple[str, str | None, str | None, str | None] | None = None

    @property
    def job_id(self) -> str:
        return f"{self.platform}-{self.index:03d}"


@dataclass(frozen=True)
class JobEvent:
    job_id: str
    status: JobStatus
    message: str
    progress: float | None = None
    detail: str | None = None


@dataclass(frozen=True)
class JobResult:
    markdown_path: Path
    raw_path: Path
    video_path: Path
    wav_path: Path | None
    info_path: Path
    title: str
    duration: str

    @property
    def files(self) -> list[Path]:
        paths = [self.markdown_path, self.raw_path, self.video_path, self.info_path]
        if self.wav_path is not None:
            paths.append(self.wav_path)
        return [path for path in paths if path.exists()]


@dataclass(frozen=True)
class UserFacingError:
    kind: str
    message: str
    detail: str
