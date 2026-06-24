# Transcriber Bilibili Migration Design

## Goal

Convert the existing `douyin_transcriber` tool into a generic `transcriber` tool that accepts Bilibili video links and Bilibili share text. The existing local workflow should remain intact: download a video with `yt-dlp`, extract audio with `ffmpeg`, transcribe Chinese audio with Whisper, and write local transcript artifacts.

## Scope

In scope:

- Rename user-facing tool references from `douyin_transcriber` to `transcriber`.
- Accept common Bilibili URL forms, including `b23.tv` short links and `www.bilibili.com/video/...` links.
- Update README, CLI prompts, argparse text, default fallback names, PyInstaller spec output name, and tests to match the new generic/Bilibili behavior.
- Preserve output artifact types: downloaded video, `.info.json`, `.raw.txt`, optional `.wav`, and `.校对稿.md`.

Out of scope:

- Adding a GUI.
- Supporting non-Bilibili platforms beyond the generic implementation already provided by `yt-dlp`.
- Reworking the transcription pipeline or changing the default Whisper model.
- Rebuilding or committing generated `dist/` and `build/` artifacts unless explicitly requested later.

## Architecture

The current architecture is kept because it is already narrow and suitable for the requested change.

- `src/core.py` owns pure helpers: URL extraction, Windows-safe filename stems, ffmpeg filter escaping, transcript cleanup, and Markdown rendering.
- `src/cli.py` owns IO and workflow orchestration: interactive input, argument parsing, ffmpeg discovery, video download, audio extraction, transcription, and per-link failure reporting.
- `tests/test_core.py` covers helper behavior without requiring network, ffmpeg, or Whisper.
- `transcriber.spec` defines the PyInstaller bundle name and dependency collection.

## Data Flow

1. The user starts `transcriber.exe` or calls the CLI with one or more Bilibili links.
2. Input text is passed through `extract_urls`, which keeps only supported Bilibili domains and removes trailing punctuation commonly copied from share text.
3. Each URL is downloaded through `yt-dlp` with `noplaylist=True`.
4. The video title from `yt-dlp` is sanitized into a stable Windows-safe filename stem.
5. `ffmpeg` extracts mono 16 kHz WAV audio.
6. The selected backend transcribes the WAV:
   - `openai-whisper` loads a named Whisper model, defaulting to `small`.
   - `ffmpeg-whisper` uses a caller-provided whisper.cpp ggml model path.
7. The tool writes raw transcript text and a Markdown校对稿 with source URL, duration, clean text, and raw ASR output.

## URL Support

`extract_urls` should accept these domains:

- `bilibili.com`
- `www.bilibili.com`
- `m.bilibili.com`
- `b23.tv`
- `bili2233.cn`

The function should continue to deduplicate URLs while preserving first-seen order.

## Error Handling

The existing error handling remains:

- No recognized URLs returns exit code `1` with a clear message.
- Missing `ffmpeg` returns exit code `1`.
- Missing ffmpeg-whisper model path returns exit code `1`.
- Per-link processing errors are collected; after the batch finishes, failures are printed and the process returns exit code `2`.

Messages should refer to Bilibili/video links rather than Douyin links.

## Testing

Update unit tests to cover:

- Extracting `b23.tv` and `www.bilibili.com/video/BV...` links from mixed share text.
- Deduplicating repeated Bilibili links.
- Rejecting unsupported non-Bilibili URLs.
- Existing filename, transcript cleanup, Markdown rendering, and ffmpeg escaping behavior.

Manual verification after implementation:

- Run the unit test suite.
- Run a lightweight CLI check using the provided link `https://b23.tv/MJoM0cX`.
- If local ffmpeg and Whisper dependencies are available, run an end-to-end transcription or at least confirm `yt-dlp` can resolve/download the Bilibili video.
