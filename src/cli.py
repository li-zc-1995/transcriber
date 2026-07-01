from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from src.core import extract_urls
from src.job_events import JobEvent, JobRequest
from src.transcriber_job import TranscriberJob


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
    return "large-v3-turbo"


def default_output_dir() -> Path:
    return app_dir() / "outputs"


def find_ffmpeg(explicit: str | None = None) -> str:
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    candidates.append(str(app_dir() / "ffmpeg.exe"))
    candidates.append(str(app_dir() / "_internal" / "ffmpeg.exe"))
    found = shutil.which("ffmpeg")
    if found:
        candidates.append(found)

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise FileNotFoundError("找不到 ffmpeg.exe。请把 ffmpeg.exe 放到 exe 同目录，或加入 PATH。")


def read_urls_interactively() -> list[str]:
    print("请粘贴 B 站或抖音视频链接/分享文本，一行一条；输入空行后开始处理：")
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


def print_job_event(event: JobEvent) -> None:
    suffix = f" {event.progress:.1f}%" if event.progress is not None else ""
    print(f"[{event.job_id}] {event.message}{suffix}")


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
    cookies_file: Path | None = None,
    device: str = "auto",
    compute_type: str = "int8",
) -> Path:
    platform = "bilibili" if any(domain in url.lower() for domain in ("bilibili.com", "b23.tv", "bili2233.cn")) else "douyin"
    request = JobRequest(
        url=url,
        platform=platform,
        index=index,
        output_dir=output_dir,
        backend=backend,
        model=model,
        ffmpeg=ffmpeg,
        keep_wav=keep_wav,
        cookies_from_browser=cookies_from_browser,
        cookies_file=cookies_file,
        device=device,
        compute_type=compute_type,
    )
    result = TranscriberJob(request, print_job_event).run()
    return result.markdown_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="批量下载 B 站/抖音视频并生成转写校对稿。")
    parser.add_argument("links", nargs="*", help="B 站或抖音视频链接；不传则进入粘贴输入模式。")
    parser.add_argument("--out", default=str(default_output_dir()), help="输出目录。")
    parser.add_argument(
        "--backend",
        choices=["faster-whisper", "openai-whisper", "ffmpeg-whisper"],
        default="faster-whisper",
        help="转写后端。默认 faster-whisper，使用 large-v3-turbo。",
    )
    parser.add_argument(
        "--model",
        default=default_model_name(),
        help="faster-whisper 后端填模型名或本地模型路径，如 large-v3-turbo；openai-whisper 后端填模型名，如 small；ffmpeg-whisper 后端填 ggml 模型路径。",
    )
    parser.add_argument("--device", default="auto", help="faster-whisper 设备，例如 auto、cpu、cuda。")
    parser.add_argument("--compute-type", default="int8", help="faster-whisper 计算类型，例如 int8、float16。")
    parser.add_argument("--ffmpeg", default=None, help="ffmpeg.exe 路径。")
    parser.add_argument("--keep-wav", action="store_true", help="保留中间 wav 音频文件。")
    parser.add_argument(
        "--cookies-from-browser",
        default=None,
        help="从浏览器读取 cookies，例如 chrome 或 edge。用于处理 B 站 412/登录态限制。",
    )
    parser.add_argument(
        "--cookies",
        default=None,
        help="读取 Netscape 格式 cookies.txt 文件。用于绕过新版 Chrome/Edge Cookies 解密失败。",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    urls = extract_urls("\n".join(args.links)) if args.links else read_urls_interactively()
    if not urls:
        print("没有识别到支持的视频链接。")
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
    cookies_file = Path(args.cookies).expanduser().resolve() if args.cookies else None
    if cookies_file is not None and not cookies_file.exists():
        print(f"找不到 cookies 文件：{cookies_file}")
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
                cookies_file=cookies_file,
                device=args.device,
                compute_type=args.compute_type,
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
