# Local Faster Whisper Design

## Goal

Improve local transcription quality and speed without uploading audio, video, cookies, or transcript content to any remote service.

The new default transcription path should use `faster-whisper` with the `large-v3-turbo` model. Users can manually choose the model and runtime options in settings instead of relying on automatic quality presets.

## Current State

The project currently uses `openai-whisper` with the `small` model by default. The GUI and CLI both call the shared `TranscriberJob` service layer, which downloads video with `yt-dlp`, extracts 16 kHz mono WAV with `ffmpeg`, transcribes it, and writes `.raw.txt` plus `.校对稿.md`.

The recent real Bilibili end-to-end test completed successfully, but the `small` model produced weak Chinese recognition quality and took about 49 minutes to transcribe a 19-minute video on the current CPU-only PyTorch environment.

Detected local hardware includes an Intel i5-9400 CPU, 16 GB RAM, and a GTX 1050 Ti 4 GB. The current Python environment has CPU-only PyTorch and does not have `faster-whisper` installed.

## Non-Goals

- Do not add cloud transcription or any upload-based service.
- Do not rewrite the `yt-dlp` download flow, Bilibili cookie handling, ffmpeg extraction, task queue, or output file workflow.
- Do not make CUDA/GPU acceleration required for the first implementation.
- Do not remove the existing `openai-whisper` backend; keep it as a compatibility fallback.

## Recommended Approach

Add a new `faster-whisper` backend and make it the default for both GUI and CLI:

- Backend: `faster-whisper`
- Model: `large-v3-turbo`
- Device: `auto`
- Compute type: `int8`

`large-v3-turbo` is the preferred default because it usually gives much better Chinese recognition than `small` while being faster and lighter than full `large-v3`. `int8` keeps local CPU/RAM requirements lower and avoids making GPU setup a prerequisite.

## Configuration Model

Extend settings with explicit transcription options:

- `transcription_backend`: default `faster-whisper`
- `whisper_model`: default `large-v3-turbo`
- `whisper_device`: default `auto`
- `whisper_compute_type`: default `int8`

Model selection is manual:

- The GUI settings dialog should expose an editable model field or combo box.
- Suggested values can include `large-v3-turbo`, `large-v3`, `medium`, `small`, and `base`, but the user can type another supported model name or local model path.
- The app should not silently switch models based on video length or machine profile.

Backend selection is also explicit:

- `faster-whisper` should be the default.
- `openai-whisper` remains available for compatibility.
- `ffmpeg-whisper` remains available for users who provide a compatible ggml model path.

## Service Layer Design

Keep `TranscriberJob` as the only orchestration layer used by GUI and CLI.

Add a dedicated transcription function:

```python
transcribe_audio_with_faster_whisper(
    wav_path: Path,
    model_name_or_path: str,
    transcript_path: Path,
    device: str = "auto",
    compute_type: str = "int8",
) -> str
```

The function should:

- Load `faster_whisper.WhisperModel`.
- Transcribe with `language="zh"` and `task="transcribe"`.
- Write timestamped raw transcript lines in the existing `[start-end] text` format.
- Return the joined clean text source used by `clean_transcript_text`.

`JobRequest` should carry the new runtime options so CLI and GUI stay aligned. Existing tests around `JobRequest.job_id` should remain stable.

## GUI Behavior

Settings should expose transcription controls near the existing Whisper model field:

- Backend
- Model
- Device
- Compute type

Defaults should show `faster-whisper`, `large-v3-turbo`, `auto`, and `int8`.

For this iteration, no new visual workflow is required in the main task screen. The task list and logs should continue to show the current stage, with the transcribing message including backend and model, for example:

```text
转写中：faster-whisper large-v3-turbo int8
```

## CLI Behavior

Update CLI defaults and arguments:

- `--backend` default becomes `faster-whisper`.
- `--model` default becomes `large-v3-turbo`.
- Add `--device`, default `auto`.
- Add `--compute-type`, default `int8`.

Existing commands should continue to work. Users can still pass `--backend openai-whisper --model small` to reproduce the old behavior.

## Dependencies

Implementation should add `faster-whisper` to `requirements.txt`.

README should document:

- The new default local backend and model.
- First-run model download behavior.
- How to manually choose another model.
- How to fall back to the previous `openai-whisper small` behavior.

## Output Metadata

The generated Markdown should continue to include the generation note, expanded with backend, model, device, and compute type. This makes speed and quality comparisons easier when users test different models.

Example:

```text
生成方式：yt-dlp 下载视频，ffmpeg 提取音频，faster-whisper large-v3-turbo 模型转写，device=auto，compute_type=int8。
```

## Error Handling

Classify missing or failed `faster-whisper` dependencies as `whisper_model_failed` unless a more specific error is obvious.

User-facing messages should distinguish:

- `faster-whisper` is not installed.
- Model download/load failed.
- Device or compute type is unsupported.

The GUI can initially show the existing Whisper failure action area without adding a model picker recovery button.

## Testing Strategy

Add tests before implementation:

- Config round trip includes backend, model, device, and compute type.
- GUI settings dialog preserves the new fields.
- Main window creates `JobRequest` with default `faster-whisper`, `large-v3-turbo`, `auto`, and `int8`.
- CLI parser defaults to the new backend and model options.
- `TranscriberJob` dispatches to `transcribe_audio_with_faster_whisper` when backend is `faster-whisper`.
- Faster-whisper transcription writes raw timestamped lines and returns clean text source using a fake model.
- Existing openai-whisper and ffmpeg-whisper tests continue to pass.

Manual verification after implementation:

1. `python -m pytest tests -q`
2. `python -m compileall src tests -q`
3. `python -m src.cli --help`
4. Run one short local or Bilibili sample with `faster-whisper large-v3-turbo`.
5. Compare speed and transcript quality against the prior `openai-whisper small` result.

## Rollout Notes

`faster-whisper` and its runtime dependencies can be large. The first model run may download model files. README should document this clearly and explain that `large-v3-turbo` is the new default local model.

Packaging may require PyInstaller hidden-import/data handling for `faster-whisper`, `ctranslate2`, and related dependencies. Packaging verification can be a follow-up if source-mode GUI/CLI behavior is stable first.
