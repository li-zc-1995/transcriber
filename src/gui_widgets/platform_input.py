from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core import extract_urls


COOKIE_OPTIONS = {
    "": "不使用",
    "chrome": "Chrome",
    "edge": "Edge",
}


def detect_platform(url: str) -> str:
    lowered = url.lower()
    if any(domain in lowered for domain in ("bilibili.com", "b23.tv", "bili2233.cn")):
        return "bilibili"
    return "douyin"


class PlatformInputWidget(QWidget):
    parse_requested = Signal(str, list, object)
    start_requested = Signal(str, list, object)

    def __init__(self, platform: str, default_cookies_browser: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.platform = platform
        self.cookies_combo: QComboBox | None = None

        self.input_edit = QTextEdit()
        self.input_edit.setAcceptRichText(False)
        self.input_edit.setPlaceholderText(self._placeholder())
        self.input_edit.setMinimumHeight(160)

        self.parse_button = QPushButton("解析链接")
        self.start_button = QPushButton("开始处理")
        self.paste_button = QPushButton("从剪贴板粘贴")
        self.clear_button = QPushButton("清空")

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.paste_button)
        button_layout.addWidget(self.parse_button)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.clear_button)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(self._label()))
        layout.addWidget(self.input_edit)

        if platform == "bilibili":
            cookie_layout = QHBoxLayout()
            cookie_layout.addWidget(QLabel("Cookies"))
            self.cookies_combo = QComboBox()
            for value, label in COOKIE_OPTIONS.items():
                self.cookies_combo.addItem(label, value)
            default_index = self.cookies_combo.findData(default_cookies_browser)
            if default_index >= 0:
                self.cookies_combo.setCurrentIndex(default_index)
            cookie_layout.addWidget(self.cookies_combo)
            cookie_layout.addStretch(1)
            layout.addLayout(cookie_layout)

        layout.addLayout(button_layout)
        layout.addStretch(1)

        self.paste_button.clicked.connect(self.paste_from_clipboard)
        self.clear_button.clicked.connect(self.input_edit.clear)
        self.parse_button.clicked.connect(self.emit_parse_requested)
        self.start_button.clicked.connect(self.emit_start_requested)

    def urls(self) -> list[str]:
        urls = extract_urls(self.input_edit.toPlainText())
        return [url for url in urls if detect_platform(url) == self.platform]

    def cookies_browser(self) -> str | None:
        if self.cookies_combo is None:
            return None
        value = self.cookies_combo.currentData()
        return str(value) if value else None

    def paste_from_clipboard(self) -> None:
        self.input_edit.paste()

    def emit_parse_requested(self) -> None:
        self.parse_requested.emit(self.platform, self.urls(), self.cookies_browser())

    def emit_start_requested(self) -> None:
        self.start_requested.emit(self.platform, self.urls(), self.cookies_browser())

    def _label(self) -> str:
        return "粘贴抖音短链或分享文本" if self.platform == "douyin" else "粘贴 Bilibili BV 链接、b23 短链或分享文本"

    def _placeholder(self) -> str:
        if self.platform == "douyin":
            return "例如：https://v.douyin.com/...\n支持一行一条或整段分享文本"
        return "例如：https://b23.tv/MJoM0cX\n遇到 412 时可选择 Chrome 或 Edge Cookies"
