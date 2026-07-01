import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.gui_widgets.result_panel import ResultPanel
from src.job_events import JobResult


def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_result_panel_lists_open_locate_and_copy_path_actions(tmp_path: Path) -> None:
    app()
    markdown = tmp_path / "demo.md"
    raw = tmp_path / "demo.raw.txt"
    video = tmp_path / "demo.mp4"
    info = tmp_path / "demo.info.json"
    for path in (markdown, raw, video, info):
        path.write_text("content", encoding="utf-8")
    result = JobResult(
        markdown_path=markdown,
        raw_path=raw,
        video_path=video,
        wav_path=None,
        info_path=info,
        title="demo",
        duration="00:10",
    )
    panel = ResultPanel()

    panel.show_result(result)

    headers = [panel.files_table.horizontalHeaderItem(i).text() for i in range(panel.files_table.columnCount())]
    assert headers == ["类型", "路径", "打开", "定位", "复制路径"]
    assert panel.files_table.rowCount() == 4


def test_result_panel_exposes_bilibili_cookie_retry_actions() -> None:
    app()
    panel = ResultPanel()
    actions = []
    panel.failure_action_requested.connect(actions.append)

    panel.show_failure_actions("bilibili_requires_cookies", "B 站需要浏览器 Cookies")
    panel.retry_chrome_button.click()
    panel.retry_edge_button.click()

    assert panel.failure_action_label.text() == "B 站需要浏览器 Cookies"
    assert panel.retry_chrome_button.isEnabled()
    assert panel.retry_edge_button.isEnabled()
    assert actions == ["chrome", "edge"]


def test_result_panel_exposes_ffmpeg_picker_action() -> None:
    app()
    panel = ResultPanel()
    actions = []
    panel.failure_action_requested.connect(actions.append)

    panel.show_failure_actions("ffmpeg_missing", "未找到 ffmpeg")
    panel.choose_ffmpeg_button.click()

    assert panel.failure_action_label.text() == "未找到 ffmpeg"
    assert panel.choose_ffmpeg_button.isEnabled()
    assert actions == ["choose_ffmpeg"]


def test_result_panel_network_failure_does_not_enable_wrong_actions() -> None:
    app()
    panel = ResultPanel()

    panel.show_failure_actions("network_ssl_failed", "B 站网络连接失败")

    assert panel.failure_action_label.text() == "B 站网络连接失败"
    assert not panel.retry_chrome_button.isEnabled()
    assert not panel.retry_edge_button.isEnabled()
    assert not panel.choose_ffmpeg_button.isEnabled()
    assert not panel.close_browser_retry_button.isEnabled()


def test_result_panel_exposes_cookie_retry_actions_for_browser_cookie_failure() -> None:
    app()
    panel = ResultPanel()
    actions = []
    panel.failure_action_requested.connect(actions.append)

    panel.show_failure_actions("browser_cookies_failed", "浏览器 Cookies 读取失败")
    panel.retry_chrome_button.click()
    panel.retry_edge_button.click()

    assert panel.failure_action_label.text() == "浏览器 Cookies 读取失败"
    assert panel.retry_chrome_button.isEnabled()
    assert panel.retry_edge_button.isEnabled()
    assert not panel.choose_ffmpeg_button.isEnabled()
    assert not panel.close_browser_retry_button.isEnabled()
    assert actions == ["chrome", "edge"]


def test_result_panel_exposes_close_browser_retry_for_cookie_database_lock() -> None:
    app()
    panel = ResultPanel()
    actions = []
    panel.failure_action_requested.connect(actions.append)

    panel.show_failure_actions("browser_cookies_locked", "浏览器 Cookies 数据库被占用", browser="edge")
    panel.close_browser_retry_button.click()

    assert panel.failure_action_label.text() == "浏览器 Cookies 数据库被占用"
    assert panel.retry_chrome_button.isEnabled()
    assert panel.retry_edge_button.isEnabled()
    assert panel.close_browser_retry_button.isEnabled()
    assert panel.close_browser_retry_button.text() == "关闭 Edge 后重试"
    assert actions == ["close_browser_retry"]
