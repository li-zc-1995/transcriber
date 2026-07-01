import json
import os
import sys
import types
from pathlib import Path

from src.job_events import JobRequest, JobStatus
from src.transcriber_job import (
    TranscriberJob,
    classify_error,
    download_video,
    transcribe_audio_with_faster_whisper,
    transcribe_audio_with_openai_whisper,
)


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

    def fake_download_video(url, output_dir, index, cookies_from_browser=None, progress_hook=None, ffmpeg=None):
        assert url == "https://b23.tv/MJoM0cX"
        assert cookies_from_browser == ("chrome", None, None, None)
        assert ffmpeg == "ffmpeg"
        if progress_hook:
            progress_hook({"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100})
        return source_video, {"title": "标题/测试", "duration": 65, "id": "BV"}

    def fake_extract_audio(ffmpeg, video_path, wav_path):
        wav_path.write_text("wav", encoding="utf-8")

    def fake_transcribe(wav_path, model, transcript_path, ffmpeg=None):
        assert ffmpeg == "ffmpeg"
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


def test_download_video_passes_ffmpeg_location_to_yt_dlp(monkeypatch, tmp_path: Path) -> None:
    captured_options = {}

    class FakeYoutubeDL:
        def __init__(self, options):
            captured_options.update(options)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def extract_info(self, url, download):
            return {"id": "BV", "ext": "mp4"}

        def prepare_filename(self, info):
            return str(tmp_path / "01_BV.mp4")

    monkeypatch.setattr("src.transcriber_job.YoutubeDL", FakeYoutubeDL)

    download_video("https://b23.tv/MJoM0cX", tmp_path, 1, ffmpeg="C:/tools/ffmpeg.exe")

    assert captured_options["ffmpeg_location"] == "C:/tools/ffmpeg.exe"


def test_transcriber_job_uses_faster_whisper_backend(monkeypatch, tmp_path: Path) -> None:
    source_video = tmp_path / "01_BV.mp4"
    source_video.write_text("video", encoding="utf-8")

    def fake_download_video(url, output_dir, index, cookies_from_browser=None, progress_hook=None, ffmpeg=None):
        return source_video, {"title": "标题", "duration": 65, "id": "BV"}

    def fake_extract_audio(ffmpeg, video_path, wav_path):
        wav_path.write_text("wav", encoding="utf-8")

    calls = []

    def fake_faster_whisper(wav_path, model, transcript_path, device="auto", compute_type="int8"):
        calls.append((model, device, compute_type))
        transcript_path.write_text("[0.00-1.00] 大模型文本", encoding="utf-8")
        return "大模型文本"

    request = JobRequest(
        url="https://b23.tv/MJoM0cX",
        platform="bilibili",
        index=1,
        output_dir=tmp_path,
        backend="faster-whisper",
        model="large-v3-turbo",
        ffmpeg="ffmpeg",
        keep_wav=False,
        cookies_from_browser=None,
        device="auto",
        compute_type="int8",
    )

    monkeypatch.setattr("src.transcriber_job.download_video", fake_download_video)
    monkeypatch.setattr("src.transcriber_job.extract_audio", fake_extract_audio)
    monkeypatch.setattr("src.transcriber_job.transcribe_audio_with_faster_whisper", fake_faster_whisper)

    events = []
    result = TranscriberJob(request, events.append).run()

    assert calls == [("large-v3-turbo", "auto", "int8")]
    assert "大模型文本" in result.markdown_path.read_text(encoding="utf-8")
    assert any("faster-whisper large-v3-turbo int8" in event.message for event in events)


def test_openai_whisper_transcription_uses_selected_ffmpeg_on_path(monkeypatch, tmp_path: Path) -> None:
    original_path = os.environ.get("PATH", "")
    ffmpeg = tmp_path / "bin" / "ffmpeg.exe"
    ffmpeg.parent.mkdir()
    ffmpeg.write_text("", encoding="utf-8")
    wav_path = tmp_path / "audio.wav"
    transcript_path = tmp_path / "audio.raw.txt"
    wav_path.write_text("wav", encoding="utf-8")

    class FakeModel:
        def transcribe(self, wav, language, task, fp16, verbose):
            assert os.environ["PATH"].split(os.pathsep)[0] == str(ffmpeg.parent)
            return {"segments": [{"start": 0.0, "end": 1.0, "text": "测试"}]}

    fake_whisper = types.SimpleNamespace(load_model=lambda model_name: FakeModel())
    monkeypatch.setitem(sys.modules, "whisper", fake_whisper)

    result = transcribe_audio_with_openai_whisper(wav_path, "small", transcript_path, ffmpeg=str(ffmpeg))

    assert result == "测试"
    assert transcript_path.read_text(encoding="utf-8") == "[0.00-1.00] 测试"
    assert os.environ.get("PATH", "") == original_path


def test_faster_whisper_transcription_writes_timestamped_raw_text(monkeypatch, tmp_path: Path) -> None:
    wav_path = tmp_path / "audio.wav"
    transcript_path = tmp_path / "audio.raw.txt"
    wav_path.write_text("wav", encoding="utf-8")
    captured = {}

    class FakeSegment:
        start = 0.0
        end = 1.5
        text = " 测试文本 "

    class FakeWhisperModel:
        def __init__(self, model_name, device, compute_type):
            captured["model_name"] = model_name
            captured["device"] = device
            captured["compute_type"] = compute_type

        def transcribe(self, wav, language, task):
            captured["wav"] = wav
            captured["language"] = language
            captured["task"] = task
            return [FakeSegment()], object()

    fake_module = types.SimpleNamespace(WhisperModel=FakeWhisperModel)
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)

    result = transcribe_audio_with_faster_whisper(
        wav_path,
        "large-v3-turbo",
        transcript_path,
        device="auto",
        compute_type="int8",
    )

    assert captured == {
        "model_name": "large-v3-turbo",
        "device": "auto",
        "compute_type": "int8",
        "wav": str(wav_path),
        "language": "zh",
        "task": "transcribe",
    }
    assert result == "测试文本"
    assert transcript_path.read_text(encoding="utf-8") == "[0.00-1.50] 测试文本"


def test_classify_error_maps_bilibili_412_to_cookie_action() -> None:
    error = classify_error(Exception("HTTP Error 412: Precondition Failed"))

    assert error.kind == "bilibili_requires_cookies"
    assert "Cookies" in error.message


def test_classify_error_maps_ssl_eof_to_network_issue() -> None:
    error = classify_error(Exception("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol"))

    assert error.kind == "network_ssl_failed"
    assert "网络" in error.message


def test_classify_error_maps_browser_cookie_decryption_failure_to_cookie_issue() -> None:
    error = classify_error(Exception("ERROR: Failed to decrypt with DPAPI. See https://github.com/yt-dlp/yt-dlp/issues/10927"))

    assert error.kind == "browser_cookies_failed"
    assert "Cookies" in error.message


def test_classify_error_maps_browser_cookie_database_copy_failure_to_cookie_issue() -> None:
    error = classify_error(Exception("ERROR: Could not copy Chrome cookie database. See https://github.com/yt-dlp/yt-dlp/issues/7271"))

    assert error.kind == "browser_cookies_locked"
    assert "Cookies" in error.message
    assert "完全退出" in error.message
