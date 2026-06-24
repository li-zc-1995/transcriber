---
stepsCompleted: [1]
inputDocuments: []
session_topic: 'Transcriber GUI design for Bilibili and Douyin workflows'
session_goals: 'Plan a more usable visual interface with platform tabs, link input, progress visibility, output path management, and file explorer shortcuts'
selected_approach: 'ai-recommended'
techniques_used: ['Persona Journey', 'Solution Matrix', 'Failure Analysis']
ideas_generated: []
context_file: ''
---

# Brainstorming Session Results

**Facilitator:** Codex
**Date:** 2026-06-24

## Session Overview

**Topic:** Transcriber 可视化界面设计。
**Goals:** 设计一个比当前 CLI 更好用的桌面界面，覆盖 B 站和抖音两个平台，提供链接输入、解析/下载/转写进度、输出路径展示，以及一键打开文件管理器。

### Context Guidance

当前工具是 Python CLI：使用 `yt-dlp` 下载视频，`ffmpeg` 提取音频，`openai-whisper` 转写，已支持 B 站 cookies 和抖音短链识别。GUI 应尽量复用现有核心流程，避免重写下载/转写逻辑。

### Session Setup

本次规划聚焦于产品体验、界面结构、状态反馈、错误处理和实现路径，不直接进入代码实现。

## Technique Selection

**Approach:** AI-Recommended Techniques

**Recommended Techniques:**

- **Persona Journey:** 先从真实用户流程出发，设计打开软件、粘贴链接、等待处理、找到文件、失败重试的完整体验。
- **Solution Matrix:** 比较 GUI 技术栈、任务执行模型、输出文件管理方式，选出适合当前 Python 工具的实现路线。
- **Failure Analysis:** 系统梳理 B 站 cookies、ffmpeg、Whisper、下载格式、长任务等待等失败场景，设计清晰可恢复的 GUI 状态。

**AI Rationale:** 当前工具的核心能力已经存在，GUI 设计的关键不是重新发明下载/转写逻辑，而是降低使用门槛、增强状态可见性、让失败可理解并可恢复。

## Technique Execution Results

### Persona Journey

**Interactive Focus:** 从用户打开软件、粘贴链接、解析任务、等待下载/转写、找到输出文件、失败重试到后续内容整理的完整路径出发设计 GUI。

**Key Ideas Generated:**

**[UX #1]：双 Tab 工作台**  
_Concept_：主界面提供 `抖音` 和 `Bilibili` 两个明确入口，每个平台有自己的输入区和专属配置。  
_Novelty_：用户按平台心智操作，B 站 cookies 等配置只在 Bilibili 页面出现，减少干扰。

**[UX #2]：先解析，后处理**  
_Concept_：点击开始后先识别链接并生成任务列表，让用户确认再进入下载/转写。  
_Novelty_：避免粘错链接后直接进入长时间任务。

**[UX #3]：分阶段任务卡**  
_Concept_：每个视频一张任务卡，展示解析中、下载中、提取音频、转写中、生成校对稿、完成、失败等状态。  
_Novelty_：批量任务中能清楚看到每个视频卡在哪一步。

**[UX #4]：结果即操作**  
_Concept_：完成后直接显示校对稿、raw 文本、视频、音频、metadata，并提供打开、定位、复制路径。  
_Novelty_：把“生成结果”和“使用结果”接起来，不需要用户自己找文件。

**[UX #5]：内容生产台方向**  
_Concept_：用户选择把 GUI 定位为“半自动内容生产台”，不止转写，还要预留清洗文案、标题提取、摘要生成等后续入口。  
_Novelty_：从一次性转写工具升级为可迭代的内容工作流平台。

### Solution Matrix

**Recommended Direction:** 使用 PySide6 做 Windows 桌面 GUI，保留 Python 后端能力，把现有 CLI 流程拆成可被 GUI 调用的任务服务。

**[Tech #1]：PySide6 桌面工作台**  
_Concept_：用 PySide6 构建原生桌面界面，支持 tab、任务列表、进度条、文件按钮、日志面板和设置页。  
_Novelty_：不把工具做成临时脚本 UI，而是做成可长期迭代的桌面工作台。

**[Tech #2]：任务服务层拆分**  
_Concept_：把 `download_video`、`extract_audio`、`transcribe_audio`、`render_markdown` 包装为 `TranscriptionJob` 服务，通过事件回调向 GUI 上报状态。  
_Novelty_：GUI 不直接塞满业务逻辑，未来 CLI 和 GUI 可以共用同一套转写核心。

**[Tech #3]：事件驱动进度模型**  
_Concept_：统一输出 `queued / parsing / downloading / extracting_audio / transcribing / writing_files / done / failed / cancelled` 状态。  
_Novelty_：把命令行黑盒进度转成用户能理解的阶段化进度。

**[Tech #4]：内容工作区预留**  
_Concept_：右侧结果区先做 Markdown/Raw 预览和复制，后续加摘要、标题、脚本生成。  
_Novelty_：第一版不做重编辑器，但从布局上为内容生产台留位置。

### Failure Analysis

**Interactive Focus:** 设计 GUI 在外部依赖失败、平台风控、长任务中断、路径异常和批量任务部分失败时的提示与恢复策略。

**[Failure #1]：B 站 412 恢复路径**  
_Concept_：当 B 站返回 `HTTP Error 412` 时，任务卡显示“需要浏览器 Cookies”，提供 `使用 Chrome Cookies 重试`、`使用 Edge Cookies 重试` 和 `查看详情`。  
_Novelty_：把底层 HTTP 风控错误翻译成明确动作，而不是让用户看 traceback。

**[Failure #2]：依赖自检面板**  
_Concept_：启动时检测 `ffmpeg`、Whisper 模型、Python 包和输出目录权限，状态栏显示 `正常 / 缺失 / 需要配置`。  
_Novelty_：把运行时失败提前到启动或设置阶段暴露。

**[Failure #3]：批量任务局部失败**  
_Concept_：一个任务失败不影响其他任务继续执行，失败任务保留错误状态和重试按钮。  
_Novelty_：避免批量转写时一个链接拖垮全部任务。

**[Failure #4]：长任务可取消与可恢复**  
_Concept_：下载阶段支持取消；转写阶段第一版先标记“等待当前阶段结束后取消”，避免强杀导致半成品状态混乱。  
_Novelty_：明确取消语义，减少用户误以为软件卡死。

**[Failure #5]：输出路径保护**  
_Concept_：输出目录不存在时自动创建；无权限时提示重新选择；完成后所有文件路径都记录在任务结果中。  
_Novelty_：把“文件找不到”问题前置解决。

**[Failure #6]：日志分层**  
_Concept_：默认展示人类可读状态；高级详情中保留 yt-dlp、ffmpeg、Whisper 原始日志，便于排查。  
_Novelty_：普通用户不被日志淹没，调试时又不丢信息。
