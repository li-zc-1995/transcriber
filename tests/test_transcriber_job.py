import json
from pathlib import Path

from src.job_events import JobRequest, JobStatus
from src.transcriber_job import TranscriberJob, classify_error


def make_request(tmp_path: Path, keep_wav: bool = False) -> JobRequest:
    return JobRequest(
        url="https://b23.tv/MJoM0cX",
        platform="bilibili",
        index=1,
        output_dir=tmp_path,
        backend="openai-whisper",
        model="small",
        ffmpeg="ffmpeg",
        keep_wav=keep_wav,
        cookies_from_browser=("chrome", None, None, None),
    )


def test_transcriber_job_emits_events_and_writes_outputs(monkeypatch, tmp_path: Path) -> None:
    source_video = tmp_path / "01_BV.mp4"
    source_video.write_text("video", encoding="utf-8")

    def fake_download_video(url, output_dir, index, cookies_from_browser=None, progress_hook=None):
        assert url == "https://b23.tv/MJoM0cX"
        assert cookies_from_browser == ("chrome", None, None, None)
        if progress_hook:
            progress_hook({"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100})
        return source_video, {"title": "标题/测试", "duration": 65, "id": "BV"}

    def fake_extract_audio(ffmpeg, video_path, wav_path):
        wav_path.write_text("wav", encoding="utf-8")

    def fake_transcribe(wav_path, model, transcript_path):
        transcript_path.write_text("[0.00-1.00] 鸡肉再卸", encoding="utf-8")
        return "鸡肉再卸"

    monkeypatch.setattr("src.transcriber_job.download_video", fake_download_video)
    monkeypatch.setattr("src.transcriber_job.extract_audio", fake_extract_audio)
    monkeypatch.setattr("src.transcriber_job.transcribe_audio_with_openai_whisper", fake_transcribe)

    events = []
    result = TranscriberJob(make_request(tmp_path), events.append).run()

    statuses = [event.status for event in events]
    assert JobStatus.DOWNLOADING in statuses
    assert JobStatus.TRANSCRIBING in statuses
    assert statuses[-1] == JobStatus.DONE
    assert any(event.progress == 50 for event in events)
    assert result.markdown_path.exists()
    assert result.raw_path.exists()
    assert result.info_path.exists()
    assert result.wav_path is None
    assert "基础代谢" in result.markdown_path.read_text(encoding="utf-8")
    assert json.loads(result.info_path.read_text(encoding="utf-8"))["title"] == "标题/测试"


def test_classify_error_maps_bilibili_412_to_cookie_action() -> None:
    error = classify_error(Exception("HTTP Error 412: Precondition Failed"))

    assert error.kind == "bilibili_requires_cookies"
    assert "Cookies" in error.message


def test_classify_error_maps_ssl_eof_to_network_issue() -> None:
    error = classify_error(Exception("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol"))

    assert error.kind == "network_ssl_failed"
    assert "网络" in error.message
