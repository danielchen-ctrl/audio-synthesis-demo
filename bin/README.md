# FFmpeg 目录说明

## 用途
将 `ffmpeg.exe` 放在此目录下，demo 会自动使用内置的 ffmpeg 进行 MP3 转码。

## 使用方法

1. **下载 ffmpeg**
   - 访问 https://ffmpeg.org/download.html
   - 下载 Windows 版本
   - 解压后找到 `ffmpeg.exe`

2. **放置文件**
   - 将 `ffmpeg.exe` 复制到 `demo_app/bin/` 目录下
   - 确保文件名为 `ffmpeg.exe`（小写）

3. **验证**
   - 运行 demo，生成音频时会自动使用内置的 ffmpeg
   - 如果找不到内置 ffmpeg，会尝试使用系统 PATH 中的 ffmpeg

## 优先级
1. 项目内置的 ffmpeg (`demo_app/bin/ffmpeg.exe`)
2. 系统 PATH 中的 ffmpeg

## 注意
- 打包后的 exe 会自动包含此目录下的 ffmpeg.exe
- 如果不需要 MP3 格式，可以不放置 ffmpeg.exe，系统会生成 WAV 文件
