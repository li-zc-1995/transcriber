from pathlib import Path

from src.config import AppSettings, load_settings, save_settings


def test_settings_round_trip_json(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = AppSettings(
        output_dir=str(tmp_path / "out"),
        ffmpeg_path="C:/tools/ffmpeg.exe",
        transcription_backend="faster-whisper",
        whisper_model="large-v3-turbo",
        whisper_device="auto",
        whisper_compute_type="int8",
        keep_wav=True,
        bilibili_cookies_browser="chrome",
        bilibili_cookies_file=str(tmp_path / "bilibili-cookies.txt"),
        window_width=1440,
        window_height=900,
    )

    save_settings(settings, path)
    loaded = load_settings(path)

    assert loaded == settings


def test_default_settings_use_faster_whisper_large_v3_turbo() -> None:
    settings = AppSettings()

    assert settings.transcription_backend == "faster-whisper"
    assert settings.whisper_model == "large-v3-turbo"
    assert settings.whisper_device == "auto"
    assert settings.whisper_compute_type == "int8"


def test_load_settings_recovers_from_corrupt_json(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{broken", encoding="utf-8")

    loaded = load_settings(path)

    assert loaded == AppSettings()
