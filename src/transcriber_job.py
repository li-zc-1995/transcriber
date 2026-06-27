from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from yt_dlp import YoutubeDL

from src.core import clean_transcript_text, escape_ffmpeg_filter_value, render_markdown, safe_stem
from src.job_events import JobEvent, JobRequest, JobResult, JobStatus, UserFacingError


EventCallback = Callable[[JobEvent], None]


class JobCancelled(RuntimeError):
    pass


def run_command(command: list[str]) -> None:
    subprocess.run(command, check=True)


def duration_string(seconds: int | float | None) -> str:
    if seconds is None:
        return "未知"
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def download_video(
    url: str,
    output_dir: Path,
    index: int,
    cookies_from_browser: tuple[str, str | None, str | None, str | None] | None = None,
    progress_hook: Callable[[dict[str, Any]], None] | None = None,
    ffmpeg: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    template = str(output_dir / f"{index:02d}_%(id)s.%(ext)s")
    options: dict[str, Any] = {
        "format": "bv*+ba/b",
        "outtmpl": template,
        "noplaylist": True,
        "windowsfilenames": True,
        "quiet": False,
        "no_warnings": False,
    }
    if ffmpeg:
        options["ffmpeg_location"] = ffmpeg
    if cookies_from_browser:
        options["cookiesfrombrowser"] = cookies_from_browser
    if progress_hook:
        options["progress_hooks"] = [progress_hook]
    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        video_path = Path(ydl.prepare_filename(info))
    return video_path, info


def extract_audio(ffmpeg: str, video_path: Path, wav_path: Path) -> None:
    run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(wav_path),
        ]
    )


def transcribe_audio_with_ffmpeg_whisper(ffmpeg: str, wav_path: Path, model_path: Path, transcript_path: Path) -> None:
    model = escape_ffmpeg_filter_value(model_path)
    destination = escape_ffmpeg_filter_value(transcript_path)
    filter_arg = f"whisper=model='{model}':language=zh:destination='{destination}':format=text"
    run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-y",
            "-i",
            str(wav_path),
            "-af",
            filter_arg,
            "-f",
            "null",
            "NUL",
        ]
    )


def transcribe_audio_with_openai_whisper(
    wav_path: Path,
    model_name: str,
    transcript_path: Path,
    ffmpeg: str | None = None,
) -> str:
    import whisper

    old_path = os.environ.get("PATH", "")
    ffmpeg_path = Path(ffmpeg) if ffmpeg else None
    if ffmpeg_path and ffmpeg_path.exists():
        os.environ["PATH"] = f"{ffmpeg_path.parent}{os.pathsep}{old_path}"
    try:
        model = whisper.load_model(model_name)
        result = model.transcribe(str(wav_path), language="zh", task="transcribe", fp16=False, verbose=False)
    finally:
        os.environ["PATH"] = old_path
    lines: list[str] = []
    clean_parts: list[str] = []
    for segment in result.get("segments", []):
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", 0.0))
        lines.append(f"[{start:.2f}-{end:.2f}] {text}")
        clean_parts.append(text)
    transcript_path.write_text("\n".join(lines), encoding="utf-8")
    return "\n".join(clean_parts)


def classify_error(exc: Exception) -> UserFacingError:
    detail = str(exc)
    lowered = detail.lower()
    if "412" in detail or "precondition failed" in lowered:
        return UserFacingError(
            kind="bilibili_requires_cookies",
            message="B 站需要浏览器 Cookies，请使用 Chrome 或 Edge Cookies 重试。",
            detail=detail,
        )
    if (
        "unexpected_eof_while_reading" in lowered
        or "eof occurred in violation of protocol" in lowered
        or "基础连接已经关闭" in detail
        or "connection was reset" in lowered
    ):
        return UserFacingError(
            kind="network_ssl_failed",
            message="B 站网络连接失败，请检查网络、代理/VPN 或稍后重试。",
            detail=detail,
        )
    if "failed to decrypt with dpapi" in lowered or (
        ("cookie" in lowered or "cookies" in lowered)
        and any(marker in lowered for marker in ("decrypt", "database", "keyring", "dpapi"))
    ):
        return UserFacingError(
            kind="browser_cookies_failed",
            message="浏览器 Cookies 读取失败，请关闭浏览器后重试，或切换 Chrome/Edge Cookies。",
            detail=detail,
        )
    if isinstance(exc, FileNotFoundError) or "ffmpeg" in lowered and "找不到" in detail:
        return UserFacingError(kind="ffmpeg_missing", message="未找到 ffmpeg，请选择 ffmpeg.exe。", detail=detail)
    if isinstance(exc, subprocess.CalledProcessError):
        return UserFacingError(kind="ffmpeg_failed", message="ffmpeg 处理失败，请查看日志详情。", detail=detail)
    if "whisper" in lowered or "model" in lowered:
        return UserFacingError(kind="whisper_model_failed", message="Whisper 模型加载或转写失败。", detail=detail)
    if "permission" in lowered or "access" in lowered or "denied" in lowered:
        return UserFacingError(kind="output_path_failed", message="输出目录不可写，请重新选择目录。", detail=detail)
    return UserFacingError(kind="unknown", message="任务处理失败，请查看日志详情。", detail=detail)


class TranscriberJob:
    def __init__(self, request: JobRequest, on_event: EventCallback | None = None):
        self.request = request
        self.on_event = on_event
        self._cancel_requested = False

    def request_cancel(self) -> None:
        self._cancel_requested = True
        self._emit(JobStatus.CANCELLATION_REQUESTED, "已请求取消")

    def run(self) -> JobResult:
        try:
            self._ensure_not_cancelled()
            self._emit(JobStatus.PARSING, "解析链接中")
            request = self.request
            request.output_dir.mkdir(parents=True, exist_ok=True)

            self._emit(JobStatus.DOWNLOADING, "下载视频中")
            video_path, info = download_video(
                request.url,
                request.output_dir,
                request.index,
                request.cookies_from_browser,
                self._on_download_progress,
                request.ffmpeg,
            )
            self._ensure_not_cancelled()
            self._emit(JobStatus.MERGING, "下载完成，准备整理文件")

            title = info.get("title") or info.get("fulltitle") or info.get("id") or f"video_{request.index}"
            stem = f"{request.index:02d}_{safe_stem(str(title))[:80]}"
            target_video = request.output_dir / f"{stem}{video_path.suffix}"
            if video_path != target_video and not target_video.exists():
                video_path.rename(target_video)
                video_path = target_video

            wav_path = request.output_dir / f"{stem}.wav"
            raw_path = request.output_dir / f"{stem}.raw.txt"
            md_path = request.output_dir / f"{stem}.校对稿.md"
            info_path = request.output_dir / f"{stem}.info.json"

            self._emit(JobStatus.EXTRACTING_AUDIO, "提取音频中")
            info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            extract_audio(request.ffmpeg, video_path, wav_path)

            self._ensure_not_cancelled()
            self._emit(JobStatus.TRANSCRIBING, f"转写中：{request.model}")
            if request.backend == "ffmpeg-whisper":
                model_path = Path(request.model).expanduser().resolve()
                transcribe_audio_with_ffmpeg_whisper(request.ffmpeg, wav_path, model_path, raw_path)
                raw_text = raw_path.read_text(encoding="utf-8", errors="ignore")
                clean_text = clean_transcript_text(raw_text)
                generation_note = f"yt-dlp 下载视频，ffmpeg 提取音频，ffmpeg whisper filter 使用 {request.model} 转写。"
            else:
                clean_source = transcribe_audio_with_openai_whisper(wav_path, request.model, raw_path, request.ffmpeg)
                raw_text = raw_path.read_text(encoding="utf-8", errors="ignore")
                clean_text = clean_transcript_text(clean_source)
                generation_note = f"yt-dlp 下载视频，ffmpeg 提取音频，openai-whisper {request.model} 模型转写。"

            self._ensure_not_cancelled()
            self._emit(JobStatus.WRITING_FILES, "生成校对稿中")
            markdown = render_markdown(
                title=str(title),
                source_url=request.url,
                duration=duration_string(info.get("duration")),
                clean_text=clean_text,
                raw_transcript=raw_text,
                generation_note=generation_note,
            )
            md_path.write_text(markdown, encoding="utf-8")

            kept_wav_path: Path | None = wav_path
            if not request.keep_wav:
                wav_path.unlink(missing_ok=True)
                kept_wav_path = None

            result = JobResult(
                markdown_path=md_path,
                raw_path=raw_path,
                video_path=video_path,
                wav_path=kept_wav_path,
                info_path=info_path,
                title=str(title),
                duration=duration_string(info.get("duration")),
            )
            self._emit(JobStatus.DONE, f"完成：{md_path}", progress=100)
            return result
        except JobCancelled:
            self._emit(JobStatus.CANCELLED, "任务已取消")
            raise
        except Exception as exc:
            error = classify_error(exc)
            self._emit(JobStatus.FAILED, error.message, detail=error.detail)
            raise

    def _on_download_progress(self, payload: dict[str, Any]) -> None:
        if self._cancel_requested:
            raise JobCancelled()
        if payload.get("status") == "finished":
            self._emit(JobStatus.MERGING, "下载完成，准备合并音视频")
            return
        downloaded = payload.get("downloaded_bytes") or 0
        total = payload.get("total_bytes") or payload.get("total_bytes_estimate") or 0
        progress = round(float(downloaded) / float(total) * 100, 1) if total else None
        self._emit(JobStatus.DOWNLOADING, "下载视频中", progress=progress)

    def _emit(
        self,
        status: JobStatus,
        message: str,
        progress: float | None = None,
        detail: str | None = None,
    ) -> None:
        if self.on_event is None:
            return
        self.on_event(
            JobEvent(
                job_id=self.request.job_id,
                status=status,
                message=message,
                progress=progress,
                detail=detail,
            )
        )

    def _ensure_not_cancelled(self) -> None:
        if self._cancel_requested:
            raise JobCancelled()
