import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.config import AppSettings
from src.gui_widgets.main_window import MainWindow
from src.gui_widgets.platform_input import detect_platform
from src.gui_widgets.settings_dialog import SettingsDialog


def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_detect_platform_handles_supported_link_types() -> None:
    assert detect_platform("https://b23.tv/MJoM0cX") == "bilibili"
    assert detect_platform("https://www.bilibili.com/video/BV1xx411c7mD") == "bilibili"
    assert detect_platform("https://v.douyin.com/v6A7Jb4Nsmw/") == "douyin"


def test_main_window_exposes_platform_tabs_and_output_controls(tmp_path: Path) -> None:
    app()
    settings = AppSettings(output_dir=str(tmp_path), bilibili_cookies_browser="chrome")

    window = MainWindow(settings=settings)

    assert window.windowTitle() == "Transcriber"
    assert window.font().family() == "Microsoft YaHei UI"
    assert [window.platform_tabs.tabText(i) for i in range(window.platform_tabs.count())] == ["抖音", "Bilibili"]
    assert window.output_dir_edit.text() == str(tmp_path)
    assert window.bilibili_input.cookies_combo.currentText() == "Chrome"
    assert window.douyin_input.cookies_combo is None


def test_settings_dialog_preserves_transcription_runtime_options(tmp_path: Path) -> None:
    app()
    settings = AppSettings(
        output_dir=str(tmp_path),
        transcription_backend="openai-whisper",
        whisper_model="medium",
        whisper_device="cpu",
        whisper_compute_type="float32",
    )
    dialog = SettingsDialog(settings)

    saved = dialog.settings(1200, 760)

    assert saved.transcription_backend == "openai-whisper"
    assert saved.whisper_model == "medium"
    assert saved.whisper_device == "cpu"
    assert saved.whisper_compute_type == "float32"


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


def test_task_list_adds_unique_urls(tmp_path: Path) -> None:
    app()
    window = MainWindow(settings=AppSettings(output_dir=str(tmp_path)))

    window.add_tasks("bilibili", ["https://b23.tv/MJoM0cX", "https://b23.tv/MJoM0cX"], None)

    assert window.task_list.rowCount() == 1
    assert window.task_list.item(0, 0).text() == "Bilibili"
    assert window.task_list.item(0, 2).text() == "等待中"


def test_runtime_bilibili_request_uses_current_cookie_selection(tmp_path: Path) -> None:
    app()
    window = MainWindow(settings=AppSettings(output_dir=str(tmp_path)))
    window.add_tasks("bilibili", ["https://b23.tv/MJoM0cX"], None)
    window.bilibili_input.cookies_combo.setCurrentText("Chrome")
    request = next(iter(window._requests_by_job_id.values()))

    runtime_request = window._with_runtime_settings(request, "ffmpeg")

    assert runtime_request.cookies_from_browser == ("chrome", None, None, None)


def test_main_window_exposes_cancel_button(tmp_path: Path) -> None:
    app()
    window = MainWindow(settings=AppSettings(output_dir=str(tmp_path)))

    assert window.cancel_button.text() == "取消当前任务"
    assert not window.cancel_button.isEnabled()


def test_main_window_maps_412_failure_to_cookie_retry(tmp_path: Path) -> None:
    app()
    window = MainWindow(settings=AppSettings(output_dir=str(tmp_path)))
    calls = []
    window.retry_failed_job = lambda: calls.append("retry")  # type: ignore[method-assign]

    window.handle_job_failed("bilibili-001", "HTTP Error 412: Precondition Failed")
    window.result_panel.retry_chrome_button.click()

    assert window.result_panel.retry_chrome_button.isEnabled()
    assert window.bilibili_input.cookies_combo.currentData() == "chrome"
    assert calls == ["retry"]


def test_main_window_maps_ffmpeg_failure_to_picker_action(tmp_path: Path) -> None:
    app()
    window = MainWindow(settings=AppSettings(output_dir=str(tmp_path)))
    calls = []
    window.choose_ffmpeg_path = lambda: calls.append("choose")  # type: ignore[method-assign]

    window.handle_job_failed("bilibili-001", "找不到 ffmpeg.exe")
    window.result_panel.choose_ffmpeg_button.click()

    assert window.result_panel.choose_ffmpeg_button.isEnabled()
    assert calls == ["choose"]


def test_main_window_maps_cookie_read_failure_to_cookie_retry(tmp_path: Path) -> None:
    app()
    window = MainWindow(settings=AppSettings(output_dir=str(tmp_path)))
    calls = []
    window.retry_failed_job = lambda: calls.append("retry")  # type: ignore[method-assign]

    window.handle_job_failed("bilibili-001", "ERROR: Failed to decrypt with DPAPI")
    window.result_panel.retry_edge_button.click()

    assert window.result_panel.retry_edge_button.isEnabled()
    assert window.bilibili_input.cookies_combo.currentData() == "edge"
    assert calls == ["retry"]


def test_retry_failed_job_only_runs_failed_request(monkeypatch, tmp_path: Path) -> None:
    app()
    window = MainWindow(settings=AppSettings(output_dir=str(tmp_path)))
    window.add_tasks("bilibili", ["https://b23.tv/one"], None)
    window.add_tasks("douyin", ["https://v.douyin.com/two/"], None)
    captured = []
    monkeypatch.setattr("src.gui_widgets.main_window.find_ffmpeg", lambda _explicit=None: "ffmpeg")
    window._run_requests = lambda requests: captured.extend(requests)  # type: ignore[method-assign]

    window.handle_job_failed("bilibili-001", "HTTP Error 412: Precondition Failed")
    window.retry_failed_job()

    assert [request.job_id for request in captured] == ["bilibili-001"]
