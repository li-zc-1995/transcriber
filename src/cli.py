from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL

from src.core import (
    clean_transcript_text,
    escape_ffmpeg_filter_value,
    extract_urls,
    render_markdown,
    safe_stem,
)


SUPPORTED_COOKIE_BROWSERS = {
    "brave",
    "chrome",
    "chromium",
    "edge",
    "firefox",
    "opera",
    "safari",
    "vivaldi",
    "whale",
}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def default_model_name() -> str:
    return "small"


def default_output_dir() -> Path:
    return app_dir() / "outputs"


def find_ffmpeg(explicit: str | None = None) -> str:
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    candidates.append(str(app_dir() / "ffmpeg.exe"))
    found = shutil.which("ffmpeg")
    if found:
        candidates.append(found)

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise FileNotFoundError("找不到 ffmpeg.exe。请把 ffmpeg.exe 放到 exe 同目录，或加入 PATH。")


def run_command(command: list[str]) -> None:
    print("运行：", " ".join(command))
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


def read_urls_interactively() -> list[str]:
    print("请粘贴 B 站视频链接或分享文本，一行一条；输入空行后开始处理：")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip():
            break
        lines.append(line)
    return extract_urls("\n".join(lines))


def parse_cookies_from_browser(value: str | None) -> tuple[str, str | None, str | None, str | None] | None:
    if not value:
        return None

    match = re.fullmatch(
        r"(?P<name>[^+:]+)(?:\s*\+\s*(?P<keyring>[^:]+))?(?:\s*:\s*(?!:)(?P<profile>.+?))?(?:\s*::\s*(?P<container>.+))?",
        value,
    )
    if not match:
        raise ValueError(f"无效的浏览器 cookies 参数：{value}")

    browser_name, keyring, profile, container = match.group("name", "keyring", "profile", "container")
    browser_name = browser_name.lower()
    if browser_name not in SUPPORTED_COOKIE_BROWSERS:
        supported = "、".join(sorted(SUPPORTED_COOKIE_BROWSERS))
        raise ValueError(f"不支持的浏览器：{browser_name}。支持：{supported}")

    return browser_name, profile, keyring.upper() if keyring else None, container


def pause_if_interactive() -> None:
    if sys.stdin.isatty():
        try:
            input("按回车退出...")
        except EOFError:
            pass


def download_video(
    url: str,
    output_dir: Path,
    index: int,
    cookies_from_browser: tuple[str, str | None, str | None, str | None] | None = None,
) -> tuple[Path, dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    template = str(output_dir / f"{index:02d}_%(id)s.%(ext)s")
    options = {
        "format": "bv*+ba/b",
        "outtmpl": template,
        "noplaylist": True,
        "windowsfilenames": True,
        "quiet": False,
        "no_warnings": False,
    }
    if cookies_from_browser:
        options["cookiesfrombrowser"] = cookies_from_browser
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


def transcribe_audio_with_openai_whisper(wav_path: Path, model_name: str, transcript_path: Path) -> str:
    print(f"加载 Whisper 模型：{model_name}")
    import whisper

    model = whisper.load_model(model_name)
    result = model.transcribe(str(wav_path), language="zh", task="transcribe", fp16=False, verbose=False)
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


def process_url(
    *,
    url: str,
    index: int,
    output_dir: Path,
    backend: str,
    model: str,
    ffmpeg: str,
    keep_wav: bool,
    cookies_from_browser: tuple[str, str | None, str | None, str | None] | None,
) -> Path:
    print(f"\n[{index}] 开始处理：{url}")
    video_path, info = download_video(url, output_dir, index, cookies_from_browser)
    title = info.get("title") or info.get("fulltitle") or info.get("id") or f"video_{index}"
    stem = f"{index:02d}_{safe_stem(title)[:80]}"

    target_video = output_dir / f"{stem}{video_path.suffix}"
    if video_path != target_video and not target_video.exists():
        video_path.rename(target_video)
        video_path = target_video

    wav_path = output_dir / f"{stem}.wav"
    raw_path = output_dir / f"{stem}.raw.txt"
    md_path = output_dir / f"{stem}.校对稿.md"
    info_path = output_dir / f"{stem}.info.json"

    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    extract_audio(ffmpeg, video_path, wav_path)

    if backend == "ffmpeg-whisper":
        model_path = Path(model).expanduser().resolve()
        transcribe_audio_with_ffmpeg_whisper(ffmpeg, wav_path, model_path, raw_path)
        raw_text = raw_path.read_text(encoding="utf-8", errors="ignore")
        clean_text = clean_transcript_text(raw_text)
    else:
        clean_source = transcribe_audio_with_openai_whisper(wav_path, model, raw_path)
        raw_text = raw_path.read_text(encoding="utf-8", errors="ignore")
        clean_text = clean_transcript_text(clean_source)

    markdown = render_markdown(
        title=str(title),
        source_url=url,
        duration=duration_string(info.get("duration")),
        clean_text=clean_text,
        raw_transcript=raw_text,
        generation_note=(
            f"yt-dlp 下载视频，ffmpeg 提取音频，openai-whisper {model} 模型转写。"
            if backend == "openai-whisper"
            else f"yt-dlp 下载视频，ffmpeg 提取音频，ffmpeg whisper filter 使用 {model} 转写。"
        ),
    )
    md_path.write_text(markdown, encoding="utf-8")

    if not keep_wav:
        wav_path.unlink(missing_ok=True)

    print(f"[{index}] 完成：{md_path}")
    return md_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="批量下载 B 站视频并生成转写校对稿。")
    parser.add_argument("links", nargs="*", help="B 站视频链接；不传则进入粘贴输入模式。")
    parser.add_argument("--out", default=str(default_output_dir()), help="输出目录。")
    parser.add_argument(
        "--backend",
        choices=["openai-whisper", "ffmpeg-whisper"],
        default="openai-whisper",
        help="转写后端。默认 openai-whisper，使用本机缓存的 small.pt。",
    )
    parser.add_argument(
        "--model",
        default=default_model_name(),
        help="openai-whisper 后端填模型名，如 small；ffmpeg-whisper 后端填 ggml 模型路径。",
    )
    parser.add_argument("--ffmpeg", default=None, help="ffmpeg.exe 路径。")
    parser.add_argument("--keep-wav", action="store_true", help="保留中间 wav 音频文件。")
    parser.add_argument(
        "--cookies-from-browser",
        default=None,
        help="从浏览器读取 cookies，例如 chrome 或 edge。用于处理 B 站 412/登录态限制。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    urls = extract_urls("\n".join(args.links)) if args.links else read_urls_interactively()
    if not urls:
        print("没有识别到 B 站视频链接。")
        pause_if_interactive()
        return 1

    if args.backend == "ffmpeg-whisper":
        model_path = Path(args.model).expanduser().resolve()
        if not model_path.exists():
            print(f"找不到模型文件：{model_path}")
            print("ffmpeg-whisper 后端需要 whisper.cpp 的 ggml 模型，例如 models\\ggml-small.bin。")
            pause_if_interactive()
            return 1

    try:
        cookies_from_browser = parse_cookies_from_browser(args.cookies_from_browser)
    except ValueError as exc:
        print(exc)
        pause_if_interactive()
        return 1

    try:
        ffmpeg = find_ffmpeg(args.ffmpeg)
    except FileNotFoundError as exc:
        print(exc)
        pause_if_interactive()
        return 1

    output_dir = Path(args.out).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    failures: list[tuple[str, str]] = []
    for index, url in enumerate(urls, start=1):
        try:
            process_url(
                url=url,
                index=index,
                output_dir=output_dir,
                backend=args.backend,
                model=args.model,
                ffmpeg=ffmpeg,
                keep_wav=args.keep_wav,
                cookies_from_browser=cookies_from_browser,
            )
        except Exception as exc:
            failures.append((url, str(exc)))
            print(f"[{index}] 失败：{exc}")

    if failures:
        print("\n以下链接处理失败：")
        for url, error in failures:
            print(f"- {url}\n  {error}")
        pause_if_interactive()
        return 2

    print(f"\n全部完成。输出目录：{output_dir}")
    pause_if_interactive()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
