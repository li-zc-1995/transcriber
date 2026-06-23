from __future__ import annotations

import re
from pathlib import Path


URL_RE = re.compile(r"https?://[^\s，。；、）)]+", re.IGNORECASE)
UNSAFE_FILENAME_RE = re.compile(r'[<>:"/\\|?*#]+')
WHITESPACE_RE = re.compile(r"\s+")
SUPPORTED_URL_DOMAINS = (
    "bilibili.com",
    "b23.tv",
    "bili2233.cn",
)


def extract_urls(text: str) -> list[str]:
    """Extract unique supported Bilibili URLs from pasted share text."""
    urls: list[str] = []
    seen: set[str] = set()
    for match in URL_RE.finditer(text):
        url = match.group(0).strip().rstrip(".,;，。；、)")
        if not any(domain in url.lower() for domain in SUPPORTED_URL_DOMAINS):
            continue
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def safe_stem(value: str, fallback: str = "video") -> str:
    """Return a Windows-safe filename stem."""
    cleaned = UNSAFE_FILENAME_RE.sub("_", value)
    cleaned = WHITESPACE_RE.sub("_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip(" ._")
    return cleaned or fallback


def escape_ffmpeg_filter_value(value: str | Path) -> str:
    """Escape a path/value for ffmpeg filter option syntax."""
    text = str(value).replace("\\", "/")
    text = text.replace(":", r"\:")
    text = text.replace("'", r"\'")
    return text


def clean_transcript_text(text: str) -> str:
    """Apply conservative cleanup for common ASR mistakes in this workflow."""
    replacements = {
        "鸡肉再卸": "基础代谢",
        "技术代谢": "基础代谢",
        "技术呆泄": "基础代谢",
        "基础呆泄": "基础代谢",
        "设注量": "摄入量",
        "设计量": "摄入量",
        "设计的热量": "摄入的热量",
        "这辆差": "热量差",
        "眼时": "饮食",
        "隐时": "饮食",
        "演识": "饮食",
        "升高": "身高",
        "上网收": "上网搜",
        "移不到位": "一步到位",
    }
    cleaned = text
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    return cleaned


def render_markdown(
    *,
    title: str,
    source_url: str,
    duration: str,
    clean_text: str,
    raw_transcript: str,
    generation_note: str = "yt-dlp 下载视频，ffmpeg 提取音频，Whisper 转写。",
) -> str:
    return f"""# {title} - 视频转写校对稿

来源链接：{source_url}
视频时长：{duration}
生成方式：{generation_note}

## 准确度说明

这是自动生成的校对稿。清洗版文案只做了常见同音错字修正，数字、专有名词和口语停顿仍建议对照视频复听确认。

## 清洗版文案

{clean_text.strip()}

## 原始 ASR 转写

```text
{raw_transcript.strip()}
```
"""
