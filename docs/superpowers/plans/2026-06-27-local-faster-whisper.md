# Local Faster Whisper Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the local default transcription backend `faster-whisper` with the manually controlled `large-v3-turbo` model, improving Chinese recognition quality and speed while keeping all processing offline.

**Architecture:** Keep `TranscriberJob` as the shared GUI/CLI orchestration service. Add `faster-whisper` as a new backend behind the existing `JobRequest` contract, extend persistent settings and CLI arguments with backend/model/device/compute type, and leave `openai-whisper` plus `ffmpeg-whisper` available as fallback paths.

**Tech Stack:** Python, PySide6, pytest, yt-dlp, ffmpeg, openai-whisper, faster-whisper, CTranslate2.

---

Spec: `docs/superpowers/specs/2026-06-27-local-faster-whisper-design.md`

Use @superpowers:test-driven-development for each implementation task and @superpowers:verification-before-completion before claiming completion.

## File Structure

- Modify: `requirements.txt`
  - Add the `faster-whisper` dependency.
- Modify: `src/job_events.py`
  - Extend `JobRequest` with `device` and `compute_type` runtime options.
- Modify: `src/config.py`
  - Add persistent transcription backend/device/compute settings and change default model to `large-v3-turbo`.
- Modify: `src/transcriber_job.py`
  - Add `transcribe_audio_with_faster_whisper`.
  - Dispatch `request.backend == "faster-whisper"` to the new function.
  - Include backend/model/device/compute type in progress and generation notes.
- Modify: `src/cli.py`
  - Make `faster-whisper` the default backend.
  - Make `large-v3-turbo` the default model.
  - Add `--device` and `--compute-type`.
- Modify: `src/gui_widgets/settings_dialog.py`
  - Expose backend, model, device, and compute type controls.
- Modify: `src/gui_widgets/main_window.py`
  - Create and refresh `JobRequest` objects using the persisted transcription settings.
- Modify: `README.md`
  - Document the new default local backend/model, first-run model download, manual model selection, and old-backend fallback.
- Test: `tests/test_config.py`
- Test: `tests/test_job_events.py`
- Test: `tests/test_transcriber_job.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_gui.py`

---

## Chunk 1: Data Model, Settings, and Dependency

### Task 1: Add Persistent Transcription Settings

**Files:**
- Modify: `src/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing config round-trip test**

Update `tests/test_config.py::test_settings_round_trip_json` so the constructed `AppSettings` includes:

```python
settings = AppSettings(
    output_dir=str(tmp_path / "out"),
    ffmpeg_path="C:/tools/ffmpeg.exe",
    transcription_backend="faster-whisper",
    whisper_model="large-v3-turbo",
    whisper_device="auto",
    whisper_compute_type="int8",
    keep_wav=True,
    bilibili_cookies_browser="chrome",
    window_width=1440,
    window_height=900,
)
```

Add a new test:

```python
def test_default_settings_use_faster_whisper_large_v3_turbo() -> None:
    settings = AppSettings()

    assert settings.transcription_backend == "faster-whisper"
    assert settings.whisper_model == "large-v3-turbo"
    assert settings.whisper_device == "auto"
    assert settings.whisper_compute_type == "int8"
```

- [ ] **Step 2: Run the config tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_config.py -q
```

Expected: FAIL because `AppSettings` does not yet define the new fields and still defaults `whisper_model` to `small`.

- [ ] **Step 3: Implement minimal settings changes**

Update `src/config.py`:

```python
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
```

No migration function is needed because `_coerce_settings` already ignores unknown keys and dataclass defaults fill missing keys.

- [ ] **Step 4: Run config tests and verify they pass**

Run:

```powershell
python -m pytest tests/test_config.py -q
```

Expected: PASS.

### Task 2: Add Runtime Request Options

**Files:**
- Modify: `src/job_events.py`
- Test: `tests/test_job_events.py`
- Test: `tests/test_transcriber_job.py`

- [ ] **Step 1: Write the failing request-options test**

Add to `tests/test_job_events.py`:

```python
def test_job_request_defaults_to_auto_device_and_int8_compute(tmp_path: Path) -> None:
    request = JobRequest(
        url="https://b23.tv/MJoM0cX",
        platform="bilibili",
        index=1,
        output_dir=tmp_path,
        backend="faster-whisper",
        model="large-v3-turbo",
        ffmpeg="ffmpeg",
        keep_wav=False,
    )

    assert request.device == "auto"
    assert request.compute_type == "int8"
```

- [ ] **Step 2: Run the request test and verify it fails**

Run:

```powershell
python -m pytest tests/test_job_events.py -q
```

Expected: FAIL because `JobRequest` does not yet expose `device` or `compute_type`.

- [ ] **Step 3: Implement minimal `JobRequest` fields**

Update `src/job_events.py`:

```python
@dataclass(frozen=True)
class JobRequest:
    url: str
    platform: str
    index: int
    output_dir: Path
    backend: str
    model: str
    ffmpeg: str
    keep_wav: bool
    cookies_from_browser: tuple[str, str | None, str | None, str | None] | None = None
    device: str = "auto"
    compute_type: str = "int8"
```

Use keyword arguments for all new construction sites later in the plan. Existing tests that use keyword arguments should keep working.

- [ ] **Step 4: Run request tests and verify they pass**

Run:

```powershell
python -m pytest tests/test_job_events.py tests/test_transcriber_job.py -q
```

Expected: PASS or only unrelated failures from later tests not yet updated.

### Task 3: Add the Faster Whisper Dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add dependency**

Append to `requirements.txt`:

```text
faster-whisper
```

- [ ] **Step 2: Verify dependency can install in the active Python**

Run:

```powershell
python -m pip install -r requirements.txt
```

Expected: install succeeds. If `ctranslate2` or `faster-whisper` has no compatible Python 3.13 wheel, stop and report the dependency compatibility issue before continuing implementation.

- [ ] **Step 3: Verify import**

Run:

```powershell
@'
from faster_whisper import WhisperModel
print(WhisperModel.__name__)
'@ | python -
```

Expected: prints `WhisperModel`.

- [ ] **Step 4: Commit chunk 1**

Run:

```powershell
git add -- requirements.txt src/config.py src/job_events.py tests/test_config.py tests/test_job_events.py
git commit -m "feat: add transcription runtime settings"
```

Expected: commit succeeds and includes only dependency, config, request model, and their tests.

---

## Chunk 2: Faster Whisper Backend

### Task 4: Implement Faster Whisper Transcription Function

**Files:**
- Modify: `src/transcriber_job.py`
- Test: `tests/test_transcriber_job.py`

- [ ] **Step 1: Write the failing unit test with a fake faster-whisper module**

Add to `tests/test_transcriber_job.py`:

```python
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
```

Also update the import at the top of the test file:

```python
from src.transcriber_job import (
    TranscriberJob,
    classify_error,
    download_video,
    transcribe_audio_with_faster_whisper,
    transcribe_audio_with_openai_whisper,
)
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```powershell
python -m pytest tests/test_transcriber_job.py::test_faster_whisper_transcription_writes_timestamped_raw_text -q
```

Expected: FAIL because `transcribe_audio_with_faster_whisper` is not defined.

- [ ] **Step 3: Implement the function**

Add to `src/transcriber_job.py` near the existing transcription functions:

```python
def transcribe_audio_with_faster_whisper(
    wav_path: Path,
    model_name_or_path: str,
    transcript_path: Path,
    device: str = "auto",
    compute_type: str = "int8",
) -> str:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name_or_path, device=device, compute_type=compute_type)
    segments, _info = model.transcribe(str(wav_path), language="zh", task="transcribe")

    lines: list[str] = []
    clean_parts: list[str] = []
    for segment in segments:
        text = str(getattr(segment, "text", "")).strip()
        if not text:
            continue
        start = float(getattr(segment, "start", 0.0))
        end = float(getattr(segment, "end", 0.0))
        lines.append(f"[{start:.2f}-{end:.2f}] {text}")
        clean_parts.append(text)
    transcript_path.write_text("\n".join(lines), encoding="utf-8")
    return "\n".join(clean_parts)
```

- [ ] **Step 4: Run the new test and verify it passes**

Run:

```powershell
python -m pytest tests/test_transcriber_job.py::test_faster_whisper_transcription_writes_timestamped_raw_text -q
```

Expected: PASS.

### Task 5: Dispatch TranscriberJob to Faster Whisper

**Files:**
- Modify: `src/transcriber_job.py`
- Test: `tests/test_transcriber_job.py`

- [ ] **Step 1: Write failing dispatch test**

Add to `tests/test_transcriber_job.py`:

```python
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
```

- [ ] **Step 2: Run the dispatch test and verify it fails**

Run:

```powershell
python -m pytest tests/test_transcriber_job.py::test_transcriber_job_uses_faster_whisper_backend -q
```

Expected: FAIL because `TranscriberJob` does not yet route to the new backend.

- [ ] **Step 3: Implement dispatch**

Update `src/transcriber_job.py` in `TranscriberJob.run()`:

```python
self._emit(JobStatus.TRANSCRIBING, self._transcribing_message(request))
if request.backend == "ffmpeg-whisper":
    ...
elif request.backend == "faster-whisper":
    clean_source = transcribe_audio_with_faster_whisper(
        wav_path,
        request.model,
        raw_path,
        device=request.device,
        compute_type=request.compute_type,
    )
    raw_text = raw_path.read_text(encoding="utf-8", errors="ignore")
    clean_text = clean_transcript_text(clean_source)
    generation_note = (
        "yt-dlp 下载视频，ffmpeg 提取音频，"
        f"faster-whisper {request.model} 模型转写，"
        f"device={request.device}，compute_type={request.compute_type}。"
    )
else:
    ...
```

Add a small helper if it keeps the message logic readable:

```python
def _transcribing_message(self, request: JobRequest) -> str:
    if request.backend == "faster-whisper":
        return f"转写中：faster-whisper {request.model} {request.compute_type}"
    return f"转写中：{request.model}"
```

- [ ] **Step 4: Run backend tests**

Run:

```powershell
python -m pytest tests/test_transcriber_job.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit chunk 2**

Run:

```powershell
git add -- src/transcriber_job.py tests/test_transcriber_job.py
git commit -m "feat: add faster whisper transcription backend"
```

Expected: commit succeeds and includes only backend implementation and tests.

---

## Chunk 3: CLI and GUI Wiring

### Task 6: Update CLI Defaults and Arguments

**Files:**
- Modify: `src/cli.py`
- Test: `tests/test_cli.py` or `tests/test_transcriber_job.py`

- [ ] **Step 1: Create CLI parser tests**

If no CLI test file exists, create `tests/test_cli.py`:

```python
from src.cli import build_parser, default_model_name


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
```

- [ ] **Step 2: Run CLI tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_cli.py -q
```

Expected: FAIL because the parser still defaults to `openai-whisper`/`small` and lacks device arguments.

- [ ] **Step 3: Implement CLI changes**

Update `src/cli.py`:

```python
def default_model_name() -> str:
    return "large-v3-turbo"
```

Add helper if desired:

```python
def default_backend() -> str:
    return "faster-whisper"
```

Update parser:

```python
parser.add_argument(
    "--backend",
    choices=["faster-whisper", "openai-whisper", "ffmpeg-whisper"],
    default="faster-whisper",
    help="转写后端。默认 faster-whisper，使用 large-v3-turbo。",
)
parser.add_argument("--device", default="auto", help="faster-whisper 设备，例如 auto、cpu、cuda。")
parser.add_argument("--compute-type", default="int8", help="faster-whisper 计算类型，例如 int8、float16。")
```

Thread the values through `process_url()` and `JobRequest(...)`:

```python
device: str,
compute_type: str,
...
device=device,
compute_type=compute_type,
```

- [ ] **Step 4: Run CLI tests**

Run:

```powershell
python -m pytest tests/test_cli.py -q
```

Expected: PASS.

### Task 7: Update GUI Settings Dialog

**Files:**
- Modify: `src/gui_widgets/settings_dialog.py`
- Modify: `src/gui_widgets/main_window.py`
- Test: `tests/test_gui.py`

- [ ] **Step 1: Write failing GUI settings tests**

Add to `tests/test_gui.py`:

```python
from src.gui_widgets.settings_dialog import SettingsDialog


def test_settings_dialog_preserves_transcription_runtime_options(tmp_path: Path) -> None:
    app()
    settings = AppSettings(
        output_dir=str(tmp_path),
        transcription_backend="faster-whisper",
        whisper_model="large-v3-turbo",
        whisper_device="auto",
        whisper_compute_type="int8",
    )
    dialog = SettingsDialog(settings)

    saved = dialog.settings(1200, 760)

    assert saved.transcription_backend == "faster-whisper"
    assert saved.whisper_model == "large-v3-turbo"
    assert saved.whisper_device == "auto"
    assert saved.whisper_compute_type == "int8"
```

Update or add:

```python
def test_main_window_creates_requests_with_transcription_settings(tmp_path: Path) -> None:
    app()
    window = MainWindow(
        settings=AppSettings(
            output_dir=str(tmp_path),
            transcription_backend="faster-whisper",
            whisper_model="large-v3-turbo",
            whisper_device="auto",
            whisper_compute_type="int8",
        )
    )

    window.add_tasks("bilibili", ["https://b23.tv/MJoM0cX"], None)
    request = next(iter(window._requests_by_job_id.values()))

    assert request.backend == "faster-whisper"
    assert request.model == "large-v3-turbo"
    assert request.device == "auto"
    assert request.compute_type == "int8"
```

- [ ] **Step 2: Run GUI tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_gui.py -q
```

Expected: FAIL because settings dialog and request creation do not expose or propagate the new fields.

- [ ] **Step 3: Implement settings dialog controls**

Update `src/gui_widgets/settings_dialog.py`:

- Add `self.backend_combo = QComboBox()` with data values:
  - `faster-whisper`
  - `openai-whisper`
  - `ffmpeg-whisper`
- Replace the plain model edit with an editable `QComboBox` or keep `QLineEdit` and add common model hints. Prefer editable combo:

```python
self.model_combo = QComboBox()
self.model_combo.setEditable(True)
for model in ["large-v3-turbo", "large-v3", "medium", "small", "base"]:
    self.model_combo.addItem(model)
self.model_combo.setCurrentText(settings.whisper_model)
```

- Add `self.device_combo` with editable values `auto`, `cpu`, `cuda`.
- Add `self.compute_type_combo` with editable values `int8`, `float16`, `float32`, `default`.
- Return all values in `settings()`.

- [ ] **Step 4: Implement main window propagation**

Update every `AppSettings(...)` construction in `src/gui_widgets/main_window.py` to preserve:

```python
transcription_backend=self.settings.transcription_backend,
whisper_device=self.settings.whisper_device,
whisper_compute_type=self.settings.whisper_compute_type,
```

Update `add_tasks()` and `_with_runtime_settings()`:

```python
backend=self.settings.transcription_backend,
model=self.settings.whisper_model,
device=self.settings.whisper_device,
compute_type=self.settings.whisper_compute_type,
```

- [ ] **Step 5: Run GUI tests**

Run:

```powershell
python -m pytest tests/test_gui.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit chunk 3**

Run:

```powershell
git add -- src/cli.py src/gui_widgets/settings_dialog.py src/gui_widgets/main_window.py tests/test_cli.py tests/test_gui.py
git commit -m "feat: wire faster whisper through cli and gui"
```

Expected: commit succeeds and includes CLI/GUI wiring plus tests.

---

## Chunk 4: Documentation and Verification

### Task 8: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update user-facing docs**

Document:

- Default backend is now `faster-whisper`.
- Default model is `large-v3-turbo`.
- First run may download model files.
- GUI settings let users manually choose backend/model/device/compute type.
- CLI fallback to old behavior:

```powershell
python -m src.cli "<url>" --backend openai-whisper --model small
```

- [ ] **Step 2: Check README mentions the new defaults**

Run:

```powershell
Select-String -LiteralPath README.md -Pattern 'faster-whisper','large-v3-turbo','openai-whisper --model small'
```

Expected: all three patterns are present.

### Task 9: Full Automated Verification

**Files:**
- All modified source and test files.

- [ ] **Step 1: Run tests**

Run:

```powershell
python -m pytest tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Compile source and tests**

Run:

```powershell
python -m compileall src tests -q
```

Expected: exit code 0.

- [ ] **Step 3: Check CLI help**

Run:

```powershell
python -m src.cli --help
```

Expected: help includes `faster-whisper`, `--device`, and `--compute-type`.

### Task 10: Source-Mode Smoke Test

**Files:**
- No tracked output files.
- Use ignored `verification_outputs/` only for generated artifacts.

- [ ] **Step 1: Run a short real or controlled sample**

Prefer a short Bilibili or local sample to avoid a long model-download/transcription cycle. Use an output directory under `verification_outputs/`.

Example:

```powershell
python -m src.cli "<short-url>" --out verification_outputs\faster_whisper_smoke --keep-wav
```

Expected:

- Model loads or downloads.
- Task reaches `done`.
- Markdown and raw transcript are created.
- Generation note mentions `faster-whisper large-v3-turbo`.

- [ ] **Step 2: Compare against prior baseline**

For a comparable sample, record:

- Video duration.
- Transcription wall time.
- Obvious Chinese recognition quality differences.

Do not commit generated media, transcripts, model cache, or verification outputs.

### Task 11: Final Commit and Optional Push

**Files:**
- Modify: `README.md`
- Include any final source/test changes from prior chunks if not already committed.

- [ ] **Step 1: Check worktree**

Run:

```powershell
git status --short --branch
```

Expected: only intended tracked files are modified; no `outputs`, media, build, dist, or cache files are staged.

- [ ] **Step 2: Commit docs and any remaining changes**

Run:

```powershell
git add -- README.md
git commit -m "docs: document faster whisper defaults"
```

Expected: commit succeeds if README changed.

- [ ] **Step 3: Push when verification passes**

Run:

```powershell
git push origin codex/gui-v1
```

Expected: push succeeds.

## Final Acceptance Checklist

- [ ] GUI and CLI default to `faster-whisper`.
- [ ] Default model is `large-v3-turbo`.
- [ ] Model selection is manually controlled in settings.
- [ ] Device and compute type are manually configurable.
- [ ] `openai-whisper small` remains available as an explicit fallback.
- [ ] `TranscriberJob` remains the shared service layer for GUI and CLI.
- [ ] `python -m pytest tests -q` passes.
- [ ] `python -m compileall src tests -q` passes.
- [ ] `python -m src.cli --help` shows the new options.
- [ ] No generated outputs, videos, audio, build artifacts, dist artifacts, or caches are committed.
