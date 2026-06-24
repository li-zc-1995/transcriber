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
