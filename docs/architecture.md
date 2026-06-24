---
stepsCompleted: [1, 2, 3, 4]
artifact_type: "architecture"
project: "transcriber-gui"
status: "complete"
---

# Transcriber GUI Architecture

## 1. 架构目标

GUI 架构必须满足：

- 复用现有 CLI 核心逻辑。
- 长任务不阻塞 UI。
- 下载、ffmpeg、Whisper 阶段能上报状态。
- CLI 保持可用。
- 未来可扩展内容加工能力。

## 2. 技术选择

推荐使用 PySide6。

理由：

- 当前项目是 Python，PySide6 可直接调用现有模块。
- Windows 桌面体验比浏览器壳更自然。
- 支持线程、信号、文件对话框、系统托盘、进度条等桌面能力。
- 可继续用 PyInstaller 打包。

## 3. 目标文件结构

```text
src/
├── __init__.py
├── core.py
├── cli.py
├── config.py
├── job_events.py
├── transcriber_job.py
├── worker.py
├── gui.py
└── gui_widgets/
    ├── __init__.py
    ├── main_window.py
    ├── platform_input.py
    ├── task_list.py
    ├── result_panel.py
    └── settings_dialog.py
```

## 4. 模块职责

### core.py

保留纯函数：

- URL 提取。
- 文件名清洗。
- ffmpeg filter 参数转义。
- 文案清洗。
- Markdown 渲染。

不得依赖 PySide6。

### transcriber_job.py

新增核心任务服务。

职责：

- 表示单个视频处理任务。
- 调用 yt-dlp 下载。
- 调用 ffmpeg 提取音频。
- 调用 Whisper 转写。
- 写入输出文件。
- 通过 callback 或事件对象汇报状态。

接口建议：

```python
class TranscriberJob:
    def __init__(self, request: JobRequest, on_event: Callable[[JobEvent], None]):
        ...

    def run(self) -> JobResult:
        ...

    def request_cancel(self) -> None:
        ...
```

### job_events.py

定义跨 CLI/GUI 共用的数据结构：

```python
@dataclass
class JobRequest:
    url: str
    platform: str
    index: int
    output_dir: Path
    backend: str
    model: str
    ffmpeg: str
    keep_wav: bool
    cookies_from_browser: tuple[str, str | None, str | None, str | None] | None

@dataclass
class JobEvent:
    job_id: str
    status: JobStatus
    message: str
    progress: float | None = None
    detail: str | None = None

@dataclass
class JobResult:
    markdown_path: Path
    raw_path: Path
    video_path: Path
    wav_path: Path | None
    info_path: Path
    title: str
    duration: str
```

### worker.py

负责后台执行。

PySide6 可使用：

- `QThread`
- `QObject` + `Signal`

第一版建议单 worker 串行执行任务，避免 Whisper 多并发占满资源。

### gui.py

GUI 入口：

```powershell
python -m src.gui
```

职责：

- 创建 QApplication。
- 加载设置。
- 打开 MainWindow。

### gui_widgets/main_window.py

职责：

- 组合平台输入区、任务列表、结果区。
- 处理全局设置和输出目录。

### gui_widgets/platform_input.py

职责：

- 抖音/Bilibili tab。
- 链接输入、解析、开始处理。
- B 站 cookies 设置。

### gui_widgets/task_list.py

职责：

- 展示任务卡。
- 更新任务状态和进度。
- 处理选中、取消、重试。

### gui_widgets/result_panel.py

职责：

- 展示清洗版文案、原始 ASR、日志、文件。
- 打开文件、定位文件、复制路径。

### config.py

职责：

- 读写本地 `settings.json`。
- 提供默认配置。
- 配置损坏时恢复默认值。

## 5. 状态机

```text
queued
  -> parsing
  -> downloading
  -> merging
  -> extracting_audio
  -> transcribing
  -> writing_files
  -> done

任意非 done 状态 -> failed
queued/downloading -> cancelled
transcribing -> cancellation_requested -> cancelled 或 done
```

## 6. 事件模型

任务服务通过事件上报：

- 状态变化。
- 下载进度。
- 日志消息。
- 输出文件生成。
- 错误详情。

GUI 只订阅事件并更新 UI，不直接解析 yt-dlp 输出。

## 7. yt-dlp 进度接入

使用 `progress_hooks`：

```python
options["progress_hooks"] = [self._on_download_progress]
```

下载事件映射：

- `downloading` -> `JobEvent(status=downloading, progress=...)`
- `finished` -> `JobEvent(status=merging, message="下载完成，准备合并")`

## 8. ffmpeg 接入

V1 使用 subprocess 执行 ffmpeg。

状态：

- 执行前发送 `extracting_audio`。
- 成功后进入 `transcribing`。
- 失败时捕获 stderr 并发送 failed。

## 9. Whisper 接入

V1 使用 openai-whisper Python API。

状态：

- 加载模型：`transcribing`，message=`加载 Whisper 模型`
- 转写中：`transcribing`，message=`转写中`
- 完成后写 raw 文本。

后续可扩展 finer progress。

## 10. 文件打开与定位

Windows：

```python
os.startfile(path)
subprocess.run(["explorer", "/select,", str(path)])
```

注意 `explorer /select,` 参数应构造为单个参数：

```python
subprocess.run(["explorer", f"/select,{path}"])
```

## 11. 错误分类

新增错误分类函数：

```python
def classify_error(exc: Exception) -> UserFacingError:
    ...
```

分类：

- `bilibili_requires_cookies`
- `ffmpeg_missing`
- `ffmpeg_failed`
- `whisper_model_failed`
- `download_failed`
- `output_path_failed`
- `unknown`

GUI 根据分类展示操作按钮。

## 12. 打包策略

PyInstaller spec 需要新增：

- PySide6 依赖收集。
- GUI 入口。
- 保留 CLI 入口可选。

建议：

- V1 打包 GUI exe：`transcriber.exe`
- CLI 可保留源码运行，不一定单独打包。

## 13. 兼容性约束

- Windows 优先。
- Python 3.12。
- 输出文件路径必须使用 `Path`。
- GUI 代码不得打印 cookies 内容。
- 任务日志不得包含完整 cookies。

## 14. 技术风险

### 风险 1：PyInstaller 包体大

原因：PySide6、torch、whisper 都很大。

缓解：

- V1 接受体积。
- 后续评估 faster-whisper 或外部模型路径。

### 风险 2：Whisper 阻塞或占用 CPU

缓解：

- 单任务串行。
- 后台线程执行。
- 明确显示耗时。

### 风险 3：B 站 cookies 读取失败

缓解：

- 提供 Chrome/Edge 两个选项。
- 给出关闭浏览器或手动 cookies 的后续扩展入口。

### 风险 4：CLI 和 GUI 逻辑分叉

缓解：

- 先拆 `TranscriberJob` 服务。
- CLI 调用同一服务。
