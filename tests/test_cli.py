from src import cli
from src.cli import build_parser, default_model_name, find_ffmpeg


def test_cli_defaults_to_faster_whisper_large_v3_turbo() -> None:
    parser = build_parser()
    args = parser.parse_args(["https://b23.tv/MJoM0cX"])

    assert args.backend == "faster-whisper"
    assert args.model == "large-v3-turbo"
    assert args.device == "auto"
    assert args.compute_type == "int8"
    assert default_model_name() == "large-v3-turbo"


def test_cli_still_accepts_openai_whisper_fallback() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--backend",
            "openai-whisper",
            "--model",
            "small",
            "https://b23.tv/MJoM0cX",
        ]
    )

    assert args.backend == "openai-whisper"
    assert args.model == "small"


def test_cli_accepts_cookie_file_for_bilibili() -> None:
    parser = build_parser()
    args = parser.parse_args(["--cookies", "C:/tmp/bilibili-cookies.txt", "https://b23.tv/MJoM0cX"])

    assert args.cookies == "C:/tmp/bilibili-cookies.txt"


def test_cli_model_help_mentions_faster_whisper_default() -> None:
    parser = build_parser()

    help_text = parser.format_help()

    assert "faster-whisper 后端填模型名" in help_text


def test_find_ffmpeg_uses_pyinstaller_internal_bundle(monkeypatch, tmp_path) -> None:
    app_dir = tmp_path / "transcriber"
    internal_dir = app_dir / "_internal"
    internal_dir.mkdir(parents=True)
    bundled_ffmpeg = internal_dir / "ffmpeg.exe"
    bundled_ffmpeg.write_text("fake", encoding="utf-8")

    monkeypatch.setattr(cli.sys, "frozen", True, raising=False)
    monkeypatch.setattr(cli.sys, "executable", str(app_dir / "transcriber.exe"))
    monkeypatch.setattr(cli.shutil, "which", lambda _name: None)

    assert find_ffmpeg() == str(bundled_ffmpeg)
