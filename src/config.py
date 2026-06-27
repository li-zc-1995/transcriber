from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path


def default_settings_path() -> Path:
    return Path.home() / "AppData" / "Roaming" / "Transcriber" / "settings.json"


@dataclass(frozen=True)
class AppSettings:
    output_dir: str = str(Path.cwd() / "outputs")
    ffmpeg_path: str = ""
    transcription_backend: str = "faster-whisper"
    whisper_model: str = "large-v3-turbo"
    whisper_device: str = "auto"
    whisper_compute_type: str = "int8"
    keep_wav: bool = False
    bilibili_cookies_browser: str = ""
    window_width: int = 1200
    window_height: int = 760


def _coerce_settings(data: dict[str, object]) -> AppSettings:
    allowed = {field.name for field in fields(AppSettings)}
    values = {key: value for key, value in data.items() if key in allowed}
    return AppSettings(**values)


def load_settings(path: Path | None = None) -> AppSettings:
    settings_path = path or default_settings_path()
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppSettings()
    if not isinstance(data, dict):
        return AppSettings()
    try:
        return _coerce_settings(data)
    except TypeError:
        return AppSettings()


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    settings_path = path or default_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
