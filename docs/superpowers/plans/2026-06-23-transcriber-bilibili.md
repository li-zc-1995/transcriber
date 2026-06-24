# Transcriber Bilibili Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the existing `douyin_transcriber` CLI into a generic `transcriber` tool that accepts Bilibili links and Bilibili share text.

**Architecture:** Keep the current small CLI architecture. `src/core.py` remains the pure helper module, `src/cli.py` remains the workflow orchestrator, `tests/test_core.py` covers local behavior without network access, and the PyInstaller spec defines the executable bundle name.

**Tech Stack:** Python 3.12, pytest, yt-dlp, ffmpeg, openai-whisper, PyInstaller.

---

## File Structure

- Modify: `C:/Users/lenovo/Documents/fat/douyin_transcriber/src/core.py`
  - Responsibility: URL extraction, safe filename stems, ffmpeg escaping, transcript cleanup, and Markdown rendering.
- Modify: `C:/Users/lenovo/Documents/fat/douyin_transcriber/src/cli.py`
  - Responsibility: CLI input, argument parsing, ffmpeg discovery, download/transcribe orchestration, and user-facing messages.
- Modify: `C:/Users/lenovo/Documents/fat/douyin_transcriber/tests/test_core.py`
  - Responsibility: fast unit coverage for helper behavior.
- Modify: `C:/Users/lenovo/Documents/fat/douyin_transcriber/README.md`
  - Responsibility: user-facing usage instructions for `transcriber.exe` and Bilibili links.
- Create: `C:/Users/lenovo/Documents/fat/douyin_transcriber/transcriber.spec`
  - Responsibility: PyInstaller bundle config with executable name `transcriber`.
- Delete: `C:/Users/lenovo/Documents/fat/douyin_transcriber/douyin_transcriber.spec`
  - Responsibility: remove stale PyInstaller entrypoint name after replacement.

Generated directories `C:/Users/lenovo/Documents/fat/douyin_transcriber/build/` and `C:/Users/lenovo/Documents/fat/douyin_transcriber/dist/` are not modified by this plan.

---

### Task 1: Update URL Extraction Tests

**Files:**
- Modify: `C:/Users/lenovo/Documents/fat/douyin_transcriber/tests/test_core.py`

- [ ] **Step 1: Replace the Douyin URL extraction test with Bilibili cases**

Replace the existing `test_extract_urls_from_mixed_batch_text` function with:

```python
def test_extract_urls_from_mixed_batch_text():
    text = """
    第一条 https://b23.tv/MJoM0cX
    第二条 https://www.bilibili.com/video/BV1xx411c7mD/?spm_id_from=333.337.search-card.all.click
    移动端 https://m.bilibili.com/video/BV1yy411c7mD
    重复链接 https://b23.tv/MJoM0cX
    其他平台 https://v.douyin.com/v6A7Jb4Nsmw/
    """

    assert extract_urls(text) == [
        "https://b23.tv/MJoM0cX",
        "https://www.bilibili.com/video/BV1xx411c7mD/?spm_id_from=333.337.search-card.all.click",
        "https://m.bilibili.com/video/BV1yy411c7mD",
    ]
```

- [ ] **Step 2: Add a trailing punctuation test for Bilibili share text**

Add this test after `test_extract_urls_from_mixed_batch_text`:

```python
def test_extract_urls_trims_bilibili_share_punctuation():
    text = "看这个视频：https://b23.tv/MJoM0cX，备用网址：https://bili2233.cn/abc123。"

    assert extract_urls(text) == [
        "https://b23.tv/MJoM0cX",
        "https://bili2233.cn/abc123",
    ]
```

- [ ] **Step 3: Update the safe filename fallback assertion**

Change the second assertion in `test_safe_stem_removes_windows_unsafe_characters` from:

```python
assert safe_stem("   ") == "douyin_video"
```

to:

```python
assert safe_stem("   ") == "video"
```

- [ ] **Step 4: Run the focused test file and verify it fails before implementation**

Run:

```powershell
python -m pytest tests/test_core.py -q
```

Expected: at least one failure showing Bilibili URLs are not yet accepted or the fallback still returns `douyin_video`.

---

### Task 2: Implement Bilibili URL Extraction

**Files:**
- Modify: `C:/Users/lenovo/Documents/fat/douyin_transcriber/src/core.py`
- Test: `C:/Users/lenovo/Documents/fat/douyin_transcriber/tests/test_core.py`

- [ ] **Step 1: Add supported domain configuration**

In `src/core.py`, add this constant after the regex constants:

```python
SUPPORTED_URL_DOMAINS = (
    "bilibili.com",
    "b23.tv",
    "bili2233.cn",
)
```

- [ ] **Step 2: Update `extract_urls` for Bilibili**

Replace the current `extract_urls` function with:

```python
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
```

- [ ] **Step 3: Update `safe_stem` fallback**

Change the function signature from:

```python
def safe_stem(value: str, fallback: str = "douyin_video") -> str:
```

to:

```python
def safe_stem(value: str, fallback: str = "video") -> str:
```

- [ ] **Step 4: Run the focused tests**

Run:

```powershell
python -m pytest tests/test_core.py -q
```

Expected: all tests in `tests/test_core.py` pass.

- [ ] **Step 5: Commit helper and test changes**

Run:

```powershell
git add -- douyin_transcriber/src/core.py douyin_transcriber/tests/test_core.py
git commit -m "feat: support bilibili url extraction"
```

Expected: commit succeeds and includes only `src/core.py` and `tests/test_core.py`.

---

### Task 3: Update CLI Messages and Tool Naming

**Files:**
- Modify: `C:/Users/lenovo/Documents/fat/douyin_transcriber/src/cli.py`

- [ ] **Step 1: Update interactive input prompt**

In `read_urls_interactively`, replace:

```python
print("请粘贴抖音链接或分享文本，一行一条；输入空行后开始处理：")
```

with:

```python
print("请粘贴 B 站视频链接或分享文本，一行一条；输入空行后开始处理：")
```

- [ ] **Step 2: Update argparse description and link help text**

In `build_parser`, replace:

```python
parser = argparse.ArgumentParser(description="批量下载抖音视频并生成转写校对稿。")
parser.add_argument("links", nargs="*", help="抖音链接；不传则进入粘贴输入模式。")
```

with:

```python
parser = argparse.ArgumentParser(description="批量下载 B 站视频并生成转写校对稿。")
parser.add_argument("links", nargs="*", help="B 站视频链接；不传则进入粘贴输入模式。")
```

- [ ] **Step 3: Update no-link error message**

In `main`, replace:

```python
print("没有识别到抖音链接。")
```

with:

```python
print("没有识别到 B 站视频链接。")
```

- [ ] **Step 4: Keep workflow logic unchanged**

Do not change `download_video`, `extract_audio`, `transcribe_audio_with_openai_whisper`, or `process_url` in this task. The existing `yt-dlp` pipeline already handles Bilibili links once the URL extractor accepts them.

- [ ] **Step 5: Run CLI no-link smoke check**

Run:

```powershell
python src/cli.py "https://v.douyin.com/v6A7Jb4Nsmw/"
```

Expected: command exits with code `1` and prints `没有识别到 B 站视频链接。`

- [ ] **Step 6: Run unit tests**

Run:

```powershell
python -m pytest tests/test_core.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit CLI message changes**

Run:

```powershell
git add -- douyin_transcriber/src/cli.py
git commit -m "chore: update cli text for bilibili transcriber"
```

Expected: commit succeeds and includes only `src/cli.py`.

---

### Task 4: Update README

**Files:**
- Modify: `C:/Users/lenovo/Documents/fat/douyin_transcriber/README.md`

- [ ] **Step 1: Replace README content**

Replace the README with:

```markdown
# Transcriber

批量下载 B 站视频，并生成本地语音转写校对稿。

## 使用方式

双击 `transcriber.exe`，粘贴一条或多条 B 站视频链接/分享文本，一行一条，最后输入空行开始处理。

也可以命令行调用：

```powershell
.\transcriber.exe "https://b23.tv/MJoM0cX"
```

默认输出到 exe 同目录下的 `outputs` 文件夹。默认转写后端是 `openai-whisper small`，会使用本机缓存的 `small.pt` 模型；第一次运行如果没有缓存，会自动下载。

## 支持的链接

- `https://b23.tv/...`
- `https://www.bilibili.com/video/BV...`
- `https://m.bilibili.com/video/BV...`
- `https://bili2233.cn/...`

## 依赖

- `ffmpeg.exe`：放在 exe 同目录，或者加入系统 PATH。需要支持常规音频提取；如果使用 `--backend ffmpeg-whisper`，还需要支持 `whisper` filter。
- `small.pt`：openai-whisper small 模型，默认缓存在 `C:\Users\<用户名>\.cache\whisper\small.pt`。

`large-v3-turbo` 大约 1.6GB，默认不使用。需要 whisper.cpp 后端时，可以通过 `--backend ffmpeg-whisper --model <ggml模型路径>` 指定模型。
```

- [ ] **Step 2: Search README for stale Douyin references**

Run:

```powershell
rg "Douyin|douyin|抖音|douyin_transcriber" README.md
```

Expected: no matches.

- [ ] **Step 3: Commit README changes**

Run:

```powershell
git add -- douyin_transcriber/README.md
git commit -m "docs: update readme for transcriber"
```

Expected: commit succeeds and includes only `README.md`.

---

### Task 5: Rename PyInstaller Spec

**Files:**
- Create: `C:/Users/lenovo/Documents/fat/douyin_transcriber/transcriber.spec`
- Delete: `C:/Users/lenovo/Documents/fat/douyin_transcriber/douyin_transcriber.spec`

- [ ] **Step 1: Copy the existing spec to `transcriber.spec`**

Create `transcriber.spec` with the same content as `douyin_transcriber.spec`, then change the `EXE` and `COLLECT` names from `douyin_transcriber` to `transcriber`:

```python
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='transcriber',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='transcriber',
)
```

- [ ] **Step 2: Delete the stale spec**

Remove:

```powershell
Remove-Item -LiteralPath .\douyin_transcriber.spec
```

- [ ] **Step 3: Search source docs for stale user-facing names**

Run:

```powershell
rg "douyin_transcriber|Douyin Transcriber|抖音" README.md src tests *.spec
```

Expected: no matches in README, source, tests, or spec files.

- [ ] **Step 4: Commit spec rename**

Run:

```powershell
git add -- douyin_transcriber/transcriber.spec douyin_transcriber/douyin_transcriber.spec
git commit -m "build: rename pyinstaller spec to transcriber"
```

Expected: commit succeeds and records `transcriber.spec` as added and `douyin_transcriber.spec` as deleted.

---

### Task 6: Verify Bilibili Link Handling

**Files:**
- No source changes expected.

- [ ] **Step 1: Run the full local unit test suite**

Run:

```powershell
python -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Verify `yt-dlp` can resolve the provided short link without downloading**

Run from `C:/Users/lenovo/Documents/fat/douyin_transcriber`:

```powershell
python -c "from yt_dlp import YoutubeDL; info=YoutubeDL({'quiet': True, 'skip_download': True, 'noplaylist': True}).extract_info('https://b23.tv/MJoM0cX', download=False); print(info.get('title')); print(info.get('webpage_url') or info.get('original_url'))"
```

Expected: prints a Bilibili video title and a Bilibili webpage URL.

- [ ] **Step 3: Run a CLI recognition smoke check with the provided link**

Run:

```powershell
python src/cli.py "https://b23.tv/MJoM0cX" --out .\verification_outputs --keep-wav
```

Expected if dependencies are present: video, `.wav`, `.raw.txt`, `.info.json`, and `.校对稿.md` files are created in `verification_outputs`.

Expected if dependencies are missing: the failure is dependency-related, not `没有识别到 B 站视频链接。`

- [ ] **Step 4: Review final git status**

Run:

```powershell
git status --short
```

Expected: only intended source/doc/spec changes are committed. Generated verification outputs may remain untracked and should not be committed unless explicitly requested.
