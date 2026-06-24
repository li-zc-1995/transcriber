# Transcriber

批量下载 B 站/抖音视频，并生成本地语音转写校对稿。

## 功能

- 支持 B 站链接：`b23.tv`、`bilibili.com/video/BV...`、`m.bilibili.com/video/BV...`、`bili2233.cn`。
- 支持抖音短链和分享链接：`v.douyin.com`、`douyin.com`、`iesdouyin.com`、`amemv.com`。
- 使用 `yt-dlp` 下载视频。
- 使用 `ffmpeg` 提取 16 kHz 单声道 WAV 音频。
- 默认使用 `openai-whisper small` 本地转写中文音频。
- 输出原始 ASR 文本和 Markdown 校对稿。

## 可视化界面规划

项目已按 BMAD Method 完成 GUI V1 规划，目标是把当前 CLI 升级为 PySide6 桌面工作台，包含抖音/Bilibili 双 Tab、任务队列、阶段进度、输出路径管理和一键打开文件管理器。规划文档入口见 [docs/index.md](docs/index.md)。

## 使用方式

### 运行源码

```powershell
pip install -r requirements.txt
python -m src.cli "https://b23.tv/MJoM0cX"
```

如果 B 站返回 `HTTP Error 412: Precondition Failed`，可以读取已登录浏览器的 cookies：

```powershell
python -m src.cli "https://b23.tv/MJoM0cX" --cookies-from-browser chrome
```

不传链接时会进入粘贴输入模式：

```powershell
python -m src.cli
```

粘贴一条或多条 B 站/抖音视频链接或分享文本，一行一条，最后输入空行开始处理。

### 运行打包后的 exe

```powershell
.\transcriber.exe "https://b23.tv/MJoM0cX"
```

默认输出到 exe 同目录下的 `outputs` 文件夹。默认转写后端是 `openai-whisper small`，会使用本机缓存的 `small.pt` 模型；第一次运行如果没有缓存，会自动下载。

## 支持的链接

### B 站

- `https://b23.tv/...`
- `https://www.bilibili.com/video/BV...`
- `https://m.bilibili.com/video/BV...`
- `https://bili2233.cn/...`

### 抖音

- `https://v.douyin.com/...`
- `https://www.douyin.com/video/...`
- `https://www.iesdouyin.com/...`
- `https://www.amemv.com/...`

## 依赖

- `ffmpeg.exe`：放在 exe 同目录，或者加入系统 PATH。需要支持常规音频提取；如果使用 `--backend ffmpeg-whisper`，还需要支持 `whisper` filter。
- `small.pt`：openai-whisper small 模型，默认缓存在 `C:\Users\<用户名>\.cache\whisper\small.pt`。

`large-v3-turbo` 大约 1.6GB，默认不使用。需要 whisper.cpp 后端时，可以通过 `--backend ffmpeg-whisper --model <ggml模型路径>` 指定模型。

## 打包

```powershell
pip install -r requirements.txt
pyinstaller transcriber.spec
```

打包产物会生成到 `dist/transcriber`。

## 输出文件

默认输出到程序同目录下的 `outputs` 文件夹。每个视频会生成：

- 下载的视频文件
- `.info.json` 元数据
- `.raw.txt` 原始 ASR 文本
- `.校对稿.md` Markdown 校对稿
- `.wav` 中间音频文件，仅在传入 `--keep-wav` 时保留

## 常见问题

B 站可能对播放元数据接口做风控。如果遇到 `HTTP Error 412: Precondition Failed`，优先尝试：

1. 确认浏览器中能正常播放该视频。
2. 使用 `--cookies-from-browser chrome` 读取 Chrome cookies。
3. 如果使用 Edge，可以改成 `--cookies-from-browser edge`。
4. 仍失败时，升级 `yt-dlp` 或更换网络环境。
