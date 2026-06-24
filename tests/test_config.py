from pathlib import Path

from src.config import AppSettings, load_settings, save_settings


def test_settings_round_trip_json(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    settings = AppSettings(
        output_dir=str(tmp_path / "out"),
        ffmpeg_path="C:/tools/ffmpeg.exe",
        whisper_model="base",
        keep_wav=True,
        bilibili_cookies_browser="chrome",
        window_width=1440,
        window_height=900,
    )

    save_settings(settings, path)
    loaded = load_settings(path)

    assert loaded == settings


def test_load_settings_recovers_from_corrupt_json(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{broken", encoding="utf-8")

    loaded = load_settings(path)

    assert loaded == AppSettings()
