---
stepsCompleted: [1, 2, 3]
artifact_type: "epics-and-stories"
project: "transcriber-gui"
status: "complete"
---

# Transcriber GUI Epics and Stories

## Epic 1: 服务层重构

目标：把当前 CLI 中的视频处理流程抽成 GUI/CLI 共用的任务服务。

### Story 1.1 定义任务数据结构

作为开发者，我希望有清晰的 `JobRequest`、`JobEvent`、`JobResult` 数据结构，以便 CLI 和 GUI 用同一套任务协议通信。

验收标准：

- 存在 `src/job_events.py`。
- 定义任务请求、任务事件、任务结果。
- 事件包含状态、消息、进度、详情。
- 不依赖 PySide6。

### Story 1.2 抽取 TranscriberJob

作为开发者，我希望把 `process_url` 的核心流程抽到 `TranscriberJob`，以便 GUI 可以后台调用并接收状态事件。

验收标准：

- 存在 `src/transcriber_job.py`。
- `TranscriberJob.run()` 能完成下载、音频提取、转写和写文件。
- 支持 `on_event` callback。
- CLI 仍能处理 B 站和抖音链接。

### Story 1.3 保持 CLI 兼容

作为现有用户，我希望原命令行用法继续工作，以免 GUI 开发破坏已有流程。

验收标准：

- `python -m src.cli <url>` 可运行。
- `--cookies-from-browser chrome` 继续可用。
- `--out`、`--backend`、`--model`、`--ffmpeg`、`--keep-wav` 继续可用。
- 原有本地测试通过。

## Epic 2: GUI 骨架和设置

目标：建立 PySide6 桌面应用骨架。

### Story 2.1 创建 PySide6 入口

作为用户，我希望能打开桌面窗口，而不是使用命令行。

验收标准：

- 存在 `src/gui.py`。
- 运行 `python -m src.gui` 打开主窗口。
- 主窗口标题为 `Transcriber`。
- 窗口包含平台输入区、任务队列区、结果区。

### Story 2.2 实现抖音和 Bilibili Tab

作为用户，我希望按平台粘贴链接，减少配置混乱。

验收标准：

- 主界面有 `抖音` 和 `Bilibili` tab。
- 每个 tab 有多行输入框。
- Bilibili tab 有 cookies 选择。
- 抖音 tab 不显示 cookies 选择。

### Story 2.3 输出目录设置

作为用户，我希望选择输出目录，并快速打开它。

验收标准：

- 有输出目录显示。
- 可选择新目录。
- 可打开当前目录。
- 输出目录持久化。

### Story 2.4 设置持久化

作为用户，我希望软件记住常用配置。

验收标准：

- 存在 `settings.json`。
- 保存输出目录、ffmpeg 路径、Whisper 模型、cookies 默认选择。
- 配置损坏时恢复默认值。

## Epic 3: 任务队列和进度

目标：可视化展示每个视频的处理过程。

### Story 3.1 解析链接生成任务

作为用户，我希望先看到识别到的任务，再开始处理。

验收标准：

- 点击 `解析链接` 后生成任务列表。
- 重复链接只生成一个任务。
- 无效链接显示但不进入队列。

### Story 3.2 后台执行任务

作为用户，我希望任务执行时界面不卡死。

验收标准：

- 使用 QThread 或 QRunnable 执行任务。
- 任务运行时窗口仍可操作。
- 单任务串行执行。

### Story 3.3 展示阶段状态

作为用户，我希望知道当前任务处于哪个阶段。

验收标准：

- 任务显示等待、解析、下载、合并、提取音频、转写、写文件、完成、失败状态。
- 下载阶段显示百分比。
- 转写阶段显示耗时。

### Story 3.4 任务取消

作为用户，我希望可以取消未开始或下载中的任务。

验收标准：

- 等待中任务可立即取消。
- 下载中任务可请求取消。
- 转写中显示“等待当前阶段结束后取消”。

## Epic 4: 结果文件和文案工作区

目标：让用户完成后能直接使用结果。

### Story 4.1 显示结果文件

作为用户，我希望看到每个任务生成了哪些文件。

验收标准：

- 完成任务显示 Markdown、raw、视频、info、wav 文件。
- 缺失文件显示不可用。

### Story 4.2 打开和定位文件

作为用户，我希望一键打开校对稿或定位文件。

验收标准：

- `打开` 使用系统默认应用。
- `定位` 使用 Windows 文件管理器选中文件。
- `复制路径` 复制完整路径。

### Story 4.3 文案预览和复制

作为用户，我希望在软件里直接预览和复制文案。

验收标准：

- 结果区可显示清洗版文案。
- 可切换原始 ASR。
- 可复制全文。

## Epic 5: 失败恢复

目标：把常见失败转成可操作 UI。

### Story 5.1 B 站 412 重试

作为 B 站用户，我希望遇到 412 时可以一键用浏览器 cookies 重试。

验收标准：

- 识别 412 错误。
- 显示“B 站需要浏览器 Cookies”。
- 提供 Chrome/Edge 重试按钮。
- 不打印 cookies 内容。

### Story 5.2 ffmpeg 缺失处理

作为用户，我希望知道 ffmpeg 缺失并能选择路径。

验收标准：

- 启动或处理前检测 ffmpeg。
- 缺失时提供选择 ffmpeg.exe。
- 选择后可重新检测。

### Story 5.3 Whisper 模型提示

作为用户，我希望首次加载模型时知道软件在做什么。

验收标准：

- 显示模型名。
- 显示“首次运行可能下载模型”。
- 模型加载失败时显示可读错误。

### Story 5.4 日志详情

作为用户，我希望失败时可以复制错误详情。

验收标准：

- 任务有日志 tab。
- 可复制错误详情。
- 默认状态区不显示大段 traceback。

## Epic 6: 打包和文档

目标：把 GUI 交付为可运行版本。

### Story 6.1 更新依赖

作为开发者，我希望依赖文件包含 GUI 所需依赖。

验收标准：

- `requirements.txt` 包含 PySide6。
- README 说明 GUI 和 CLI 两种运行方式。

### Story 6.2 更新 PyInstaller

作为用户，我希望能双击 exe 启动 GUI。

验收标准：

- PyInstaller spec 以 GUI 入口打包。
- exe 启动后打开主窗口。
- 打包不包含测试目录和历史输出。

### Story 6.3 更新 README

作为用户，我希望知道如何使用 GUI。

验收标准：

- README 有 GUI 使用说明。
- README 有 B 站 cookies 说明。
- README 有输出文件说明。

## 推荐实施顺序

1. Story 1.1
2. Story 1.2
3. Story 1.3
4. Story 2.1
5. Story 2.2
6. Story 2.3
7. Story 3.1
8. Story 3.2
9. Story 3.3
10. Story 4.1
11. Story 4.2
12. Story 5.1
13. Story 5.2
14. Story 6.1
15. Story 6.2
16. Story 6.3
