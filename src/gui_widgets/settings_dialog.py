from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from src.config import AppSettings


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.output_dir_edit = QLineEdit(settings.output_dir)
        self.ffmpeg_edit = QLineEdit(settings.ffmpeg_path)
        self.cookies_file_edit = QLineEdit(settings.bilibili_cookies_file)
        self.backend_combo = QComboBox()
        self.backend_combo.addItem("faster-whisper", "faster-whisper")
        self.backend_combo.addItem("openai-whisper", "openai-whisper")
        self.backend_combo.addItem("ffmpeg-whisper", "ffmpeg-whisper")
        backend_index = self.backend_combo.findData(settings.transcription_backend)
        if backend_index >= 0:
            self.backend_combo.setCurrentIndex(backend_index)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        for model in ["large-v3-turbo", "large-v3", "medium", "small", "base"]:
            self.model_combo.addItem(model)
        self.model_combo.setCurrentText(settings.whisper_model)

        self.device_combo = QComboBox()
        self.device_combo.setEditable(True)
        for device in ["auto", "cpu", "cuda"]:
            self.device_combo.addItem(device)
        self.device_combo.setCurrentText(settings.whisper_device)

        self.compute_type_combo = QComboBox()
        self.compute_type_combo.setEditable(True)
        for compute_type in ["int8", "float16", "float32", "default"]:
            self.compute_type_combo.addItem(compute_type)
        self.compute_type_combo.setCurrentText(settings.whisper_compute_type)

        self.keep_wav_check = QCheckBox("保留 WAV")
        self.keep_wav_check.setChecked(settings.keep_wav)
        self.cookies_combo = QComboBox()
        self.cookies_combo.addItem("不使用", "")
        self.cookies_combo.addItem("Chrome", "chrome")
        self.cookies_combo.addItem("Edge", "edge")
        index = self.cookies_combo.findData(settings.bilibili_cookies_browser)
        if index >= 0:
            self.cookies_combo.setCurrentIndex(index)

        browse_output = QPushButton("选择")
        browse_output.clicked.connect(self.choose_output_dir)
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_dir_edit)
        output_layout.addWidget(browse_output)

        browse_ffmpeg = QPushButton("选择")
        browse_ffmpeg.clicked.connect(self.choose_ffmpeg)
        ffmpeg_layout = QHBoxLayout()
        ffmpeg_layout.addWidget(self.ffmpeg_edit)
        ffmpeg_layout.addWidget(browse_ffmpeg)

        browse_cookies_file = QPushButton("选择")
        browse_cookies_file.clicked.connect(self.choose_cookies_file)
        cookies_file_layout = QHBoxLayout()
        cookies_file_layout.addWidget(self.cookies_file_edit)
        cookies_file_layout.addWidget(browse_cookies_file)

        form = QFormLayout(self)
        form.addRow("输出目录", output_layout)
        form.addRow("ffmpeg", ffmpeg_layout)
        form.addRow("转写后端", self.backend_combo)
        form.addRow("Whisper 模型", self.model_combo)
        form.addRow("运行设备", self.device_combo)
        form.addRow("计算类型", self.compute_type_combo)
        form.addRow("B 站 Cookies", self.cookies_combo)
        form.addRow("B 站 cookies.txt", cookies_file_layout)
        form.addRow("", self.keep_wav_check)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def settings(self, window_width: int, window_height: int) -> AppSettings:
        return AppSettings(
            output_dir=self.output_dir_edit.text().strip(),
            ffmpeg_path=self.ffmpeg_edit.text().strip(),
            transcription_backend=str(self.backend_combo.currentData() or "faster-whisper"),
            whisper_model=self.model_combo.currentText().strip() or "large-v3-turbo",
            whisper_device=self.device_combo.currentText().strip() or "auto",
            whisper_compute_type=self.compute_type_combo.currentText().strip() or "int8",
            keep_wav=self.keep_wav_check.isChecked(),
            bilibili_cookies_browser=str(self.cookies_combo.currentData() or ""),
            bilibili_cookies_file=self.cookies_file_edit.text().strip(),
            window_width=window_width,
            window_height=window_height,
        )

    def choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_dir_edit.text())
        if directory:
            self.output_dir_edit.setText(directory)

    def choose_ffmpeg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 ffmpeg.exe", "", "ffmpeg.exe (ffmpeg.exe);;Executables (*.exe)")
        if path:
            self.ffmpeg_edit.setText(path)

    def choose_cookies_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 B 站 cookies.txt",
            self.cookies_file_edit.text(),
            "Cookies files (*.txt);;All files (*.*)",
        )
        if path:
            self.cookies_file_edit.setText(path)
