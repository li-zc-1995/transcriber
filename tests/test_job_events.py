from pathlib import Path

from src.job_events import JobEvent, JobRequest, JobResult, JobStatus


def test_job_request_builds_stable_job_id_from_platform_and_index(tmp_path: Path) -> None:
    request = JobRequest(
        url="https://b23.tv/MJoM0cX",
        platform="bilibili",
        index=3,
        output_dir=tmp_path,
        backend="openai-whisper",
        model="small",
        ffmpeg="ffmpeg",
        keep_wav=False,
        cookies_from_browser=None,
    )

    assert request.job_id == "bilibili-003"


def test_job_event_defaults_to_no_progress_or_detail() -> None:
    event = JobEvent(job_id="douyin-001", status=JobStatus.QUEUED, message="等待中")

    assert event.progress is None
    assert event.detail is None


def test_job_result_lists_existing_output_files(tmp_path: Path) -> None:
    markdown = tmp_path / "demo.md"
    raw = tmp_path / "demo.raw.txt"
    video = tmp_path / "demo.mp4"
    info = tmp_path / "demo.info.json"
    for path in (markdown, raw, video, info):
        path.write_text("x", encoding="utf-8")

    result = JobResult(
        markdown_path=markdown,
        raw_path=raw,
        video_path=video,
        wav_path=None,
        info_path=info,
        title="demo",
        duration="01:00",
    )

    assert result.files == [markdown, raw, video, info]
