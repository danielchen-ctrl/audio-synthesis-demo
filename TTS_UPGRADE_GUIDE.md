# TTS 引擎升级指南

> 适用环境：Windows + 无独立显卡（Intel 集显）  
> 当前引擎：edge-tts（Microsoft）  
> 文档目标：说明可用的升级方案、接入步骤和代码改动位置

---

## 一、现状与问题

当前工具使用 **edge-tts** 合成音频，存在以下限制：

| 问题 | 原因 |
|------|------|
| 声音单调、播报腔 | edge-tts 不支持情感/韵律控制 |
| 多说话人区分度低 | 所有预设声音音色差异小 |
| SSML 情感标签无效 | Microsoft 已在 edge-tts 中禁用自定义 SSML（Issue #426） |
| 仅支持 rate/pitch 参数 | 调节空间极为有限，本质无法模拟情感 |

---

## 二、可用方案对比

### 你的电脑配置
- **CPU**：Intel（含 UHD 集显）
- **独立显卡**：无
- **结论**：无法运行需要 NVIDIA GPU 的模型（CosyVoice3 本地版、Fish Speech 等）

### 方案汇总

| | 方案 A：Kokoro-82M | 方案 B：SiliconFlow CosyVoice2 |
|---|---|---|
| **费用** | 完全免费 | 免费（注册送 ¥14，按用量极少消耗） |
| **运行位置** | 本地 CPU | 云端 API |
| **中文质量** | 良好（社区中文模型） | 极高（CosyVoice2 级别） |
| **情感控制** | 靠声音选择，无指令控制 | ✅ 自然语言指令（"用激动的语气"） |
| **多语言** | 英文最强，中文可用，日韩法德有限 | ✅ 中英日韩法德西葡全支持 |
| **Windows 安装** | pip 直接装，需装 espeak-ng | 只需 API Key，无需本地安装 |
| **License** | Apache-2.0，可商用 | 按调用付费，无 License 限制 |
| **隐私** | 完全本地，数据不出境 | 文本发送至 SiliconFlow 服务器 |

### 费用说明（方案 B）

CosyVoice2 价格：¥105 / 百万 UTF-8 字节，1 个汉字 ≈ 3 字节。

```
一次生成 3000 字对话的费用：
  3000 字 × 3 字节 = 9000 字节
  9000 / 1,000,000 × ¥105 = ¥0.00095

注册赠送 ¥14 可生成：
  ¥14 ÷ ¥0.00095 ≈ 14,700 次
```

日常 demo 使用，**¥14 免费额度大概率永远用不完**。

---

## 三、方案 A：Kokoro-82M（完全免费，本地运行）

### 3.1 安装步骤

**第一步：安装 espeak-ng（必须）**

1. 访问：https://github.com/espeak-ng/espeak-ng/releases
2. 下载最新的 `espeak-ng-*.msi` 文件
3. 双击安装，记录安装路径（默认 `C:\Program Files\eSpeak NG`）
4. 将安装路径下的 `bin/` 目录添加到系统 PATH 环境变量

**第二步：安装 Python 依赖**

```bash
pip install kokoro>=0.9.4 soundfile
pip install "misaki[zh]==0.9.4"   # 中文支持，锁定版本避免兼容问题
pip install kokoro-onnx            # ONNX 加速版，CPU 下更快
```

**第三步：验证安装**

```python
from kokoro import KPipeline
import soundfile as sf
import numpy as np

pipeline = KPipeline(lang_code='z', repo_id='hexgrad/Kokoro-82M-v1.1-zh')
generator = pipeline("你好，这是测试。", voice='zf_001', speed=1.0)
chunks = [chunk.audio for chunk in generator]
sf.write('test.wav', np.concatenate(chunks), 24000)
print("安装成功，已生成 test.wav")
```

### 3.2 可用的中文声音列表

中文模型（`hexgrad/Kokoro-82M-v1.1-zh`）内置 103 个声音：

```python
# 常用声音（zf = 中文女声，zm = 中文男声）
KOKORO_ZH_VOICES = [
    'zf_001',  # 标准女声
    'zf_002',  # 温柔女声
    'zm_001',  # 标准男声
    'zm_002',  # 低沉男声
    # ... 共103个，加载后查看 pipeline.get_voices() 获取完整列表
]
```

### 3.3 集成到现有代码

**改动位置：`src/demo_app/embedded_server_main.py`**

**改动1：在文件顶部新增导入和配置（约第 30 行后）**

```python
# ── Kokoro TTS 配置 ────────────────────────────────────────────────────────────
_USE_KOKORO = True   # 设为 False 回退到 edge-tts

_kokoro_pipeline_zh: Any | None = None
_kokoro_pipeline_en: Any | None = None
_kokoro_lock = threading.Lock()

def _get_kokoro_pipeline(language: str):
    """懒加载 Kokoro pipeline，首次调用时初始化（约需 5-10 秒）。"""
    global _kokoro_pipeline_zh, _kokoro_pipeline_en
    if language in ("Chinese", "Cantonese"):
        if _kokoro_pipeline_zh is None:
            with _kokoro_lock:
                if _kokoro_pipeline_zh is None:
                    from kokoro import KPipeline
                    _kokoro_pipeline_zh = KPipeline(
                        lang_code='z',
                        repo_id='hexgrad/Kokoro-82M-v1.1-zh',
                    )
        return _kokoro_pipeline_zh
    else:
        if _kokoro_pipeline_en is None:
            with _kokoro_lock:
                if _kokoro_pipeline_en is None:
                    from kokoro import KPipeline
                    _kokoro_pipeline_en = KPipeline(lang_code='a')  # 'a' = 美式英语
        return _kokoro_pipeline_en
```

**改动2：替换声音映射表（约第 79 行）**

```python
# 将原来的 edge-tts 声音表替换为 Kokoro 声音
VOICE_CATALOG = {
    "Chinese":    ["zf_001", "zm_001", "zf_002", "zm_002"],
    "English":    ["af_heart", "am_adam", "af_bella", "am_michael"],
    "Japanese":   ["jf_alpha", "jm_kumo"],          # Kokoro 英文模型含日语
    "Korean":     ["af_heart", "am_adam"],           # 降级用英文模型
    "French":     ["ff_siwis"],                      # Kokoro 含法语声音
    "German":     ["af_heart", "am_adam"],           # 降级用英文模型
    "Spanish":    ["ef_dora"],                       # Kokoro 含西班牙语
    "Portuguese": ["af_heart", "am_adam"],
    "Cantonese":  ["zf_001", "zm_001"],              # 粤语用中文模型近似
}
```

**改动3：替换 TTS 合成函数（`_synthesize_audio_from_lines` 内）**

```python
# 找到这段代码（约第 1430 行）：
#   async def _tts_one(voice: str, text: str, path: Path) -> None:
#       async with sem:
#           await edge_tts.Communicate(text, voice).save(str(path))
#
# 替换为：

def _kokoro_synthesize(voice: str, text: str, path: Path, language: str) -> None:
    """同步调用 Kokoro 合成一段音频并保存为 WAV。"""
    import soundfile as sf
    import numpy as np
    pipeline = _get_kokoro_pipeline(language)
    chunks = [chunk.audio for chunk in pipeline(text, voice=voice, speed=1.0)]
    if not chunks:
        raise RuntimeError(f"Kokoro 未返回音频: {text[:30]}")
    audio = np.concatenate(chunks)
    sf.write(str(path.with_suffix('.wav')), audio, 24000)

async def _tts_one(voice: str, text: str, path: Path, language: str = "Chinese") -> None:
    async with sem:
        if _USE_KOKORO:
            # Kokoro 是同步库，用 executor 避免阻塞事件循环
            loop = asyncio.get_event_loop()
            wav_path = path.with_suffix('.wav')
            await loop.run_in_executor(
                None, _kokoro_synthesize, voice, text, wav_path, language
            )
            # 更新 segment_file 引用为 .wav（后续 ffmpeg 合并用）
            path = wav_path  # noqa: F841
        else:
            await edge_tts.Communicate(text, voice).save(str(path))
```

### 3.4 已知限制

- 中文模型（v1.1-zh）是社区微调版，质量良好但偶有发音偏差
- ONNX 版的语速参数（speed）在中文模型下有 bug，只支持 3 个固定值
- 日韩法德等语言降级使用英文模型，效果有限
- 首次启动需下载模型（约 350MB），之后本地缓存

---

## 四、方案 B：SiliconFlow CosyVoice2（推荐，注册免费）

### 4.1 注册与获取 API Key

1. 访问：https://siliconflow.cn
2. 注册账号（手机号或邮箱）
3. 进入控制台 → API Keys → 创建新 Key
4. 新用户自动获得 **¥14 免费余额**

### 4.2 安装依赖

```bash
pip install aiohttp   # 异步 HTTP 客户端（可能已安装）
```

### 4.3 集成到现有代码

**改动1：新增配置（文件顶部或 `config/app.yaml`）**

```python
# src/demo_app/embedded_server_main.py 顶部附近新增
_SILICONFLOW_API_KEY = os.environ.get("SILICONFLOW_API_KEY", "")
_USE_SILICONFLOW = bool(_SILICONFLOW_API_KEY)   # 有 Key 就启用
```

在项目根目录新建 `.env` 文件（已在 `.gitignore` 中，不会提交）：
```
SILICONFLOW_API_KEY=sk-你的实际Key
```

**改动2：替换声音映射表**

```python
VOICE_CATALOG = {
    # 格式：CosyVoice2 内置 8 个声音，中英双语通用
    "Chinese":    ["anna",    "bella",   "claire",   "diana",
                   "alex",    "benjamin","charles",  "david"],
    "English":    ["alex",    "david",   "anna",     "diana",
                   "benjamin","charles", "bella",    "claire"],
    "Japanese":   ["anna",    "bella",   "alex",     "david"],
    "Korean":     ["anna",    "bella",   "alex",     "david"],
    "French":     ["claire",  "diana",   "anna",     "bella"],
    "German":     ["alex",    "david",   "anna",     "diana"],
    "Spanish":    ["anna",    "bella",   "alex",     "david"],
    "Portuguese": ["anna",    "bella",   "alex",     "charles"],
    "Cantonese":  ["anna",    "bella",   "claire",   "diana"],
}
```

**改动3：替换 TTS 合成函数**

```python
# 找到（约第 1430 行）：
#   async def _tts_one(voice: str, text: str, path: Path) -> None:
#       async with sem:
#           await edge_tts.Communicate(text, voice).save(str(path))
#
# 替换为：

async def _tts_one(
    voice: str,
    text: str,
    path: Path,
    emotion: str = "",
) -> None:
    async with sem:
        if _USE_SILICONFLOW:
            import aiohttp
            full_input = f"{emotion} <|endofprompt|>{text}" if emotion else text
            payload = {
                "model": "FunAudioLLM/CosyVoice2-0.5B",
                "input": full_input,
                "voice": f"FunAudioLLM/CosyVoice2-0.5B:{voice}",
                "response_format": "mp3",
                "speed": 1.0,
            }
            headers = {
                "Authorization": f"Bearer {_SILICONFLOW_API_KEY}",
                "Content-Type": "application/json",
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.siliconflow.cn/v1/audio/speech",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    resp.raise_for_status()
                    path.write_bytes(await resp.read())
        else:
            # 回退到 edge-tts
            await edge_tts.Communicate(text, voice).save(str(path))
```

**改动4（可选）：LLM 生成脚本时注入情感标注**

在 `_generate_text_payload` 函数中，修改发给 LLM 的 prompt，要求输出时在每行前加情感标签：

```python
# 在构建 LLM prompt 时加入指令（约第 853 行附近）
EMOTION_INSTRUCTION = """
请在每行对话前用方括号标注说话情感，例如：
Speaker 1: [激动] 这个季度的数据超出预期！
Speaker 2: [冷静] 我们还需要分析背后的原因。
Speaker 3: [担忧] 竞争对手那边好像也有动作。

可用的情感标签：[激动] [冷静] [温柔] [严肃] [担忧] [开心] [低沉] [平静]
"""

# 提取情感标签的辅助函数（在调用 TTS 前解析）
import re

def _extract_emotion_tag(text: str) -> tuple[str, str]:
    """从 '[激动] 文本内容' 中提取情感和纯文本。"""
    m = re.match(r'^\[(.+?)\]\s*', text)
    if m:
        emotion_map = {
            "激动": "用激动兴奋的语气说话",
            "冷静": "用冷静理性的语气说话",
            "温柔": "用温柔轻柔的语气说话",
            "严肃": "用严肃正式的语气说话",
            "担忧": "用略带担忧的语气说话",
            "开心": "用开心愉快的语气说话",
            "低沉": "用低沉缓慢的语气说话",
            "平静": "用平静自然的语气说话",
        }
        tag = m.group(1)
        instruction = emotion_map.get(tag, "")
        clean_text = text[m.end():]
        return instruction, clean_text
    return "", text
```

---

## 五、效果对比

### 音质对比（主观评估）

```
edge-tts（当前）  ★★★☆☆  播报腔，机械感强
Kokoro-82M        ★★★★☆  自然度明显提升，节奏更接近真人
CosyVoice2        ★★★★★  接近真人，情感丰富，方言支持
```

### 一次 3000 字中文对话生成耗时（估算）

```
edge-tts     约 5–8 秒    （并发异步，网络延迟为主）
Kokoro-82M   约 30–60 秒  （本地 CPU，约 RTF 1.1x，串行生成各段）
CosyVoice2   约 8–15 秒   （云端 API，网络延迟 + 推理时间）
```

> Kokoro 在 CPU 下生成速度明显慢于 edge-tts，适合对速度要求不高的场景。

---

## 六、实施建议

### 推荐路径

```
现在（无 GPU，希望免费）
    → 优先尝试方案 B（SiliconFlow）
        → 注册账号，¥14 免费额度
        → 只改 3 处代码，30 分钟接入
        → 如果用完再考虑充值（可能几个月都用不完）

    → 如果坚持完全本地
        → 选方案 A（Kokoro-82M）
        → 接受速度变慢（约 30-60 秒/次）
        → 安装 espeak-ng + pip 依赖
```

### 快速切换（两种方案共存）

两个方案均通过**环境变量**控制，可以随时切换：

```bash
# 启用 SiliconFlow（在 .env 中设置）
SILICONFLOW_API_KEY=sk-xxxx

# 启用 Kokoro（不设置 SILICONFLOW_API_KEY，且 _USE_KOKORO=True）
# 回退到 edge-tts（_USE_KOKORO=False，无 SILICONFLOW_API_KEY）
```

---

## 七、文件改动清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `src/demo_app/embedded_server_main.py` | 修改 | 声音表、TTS 调用函数、配置变量 |
| `.env`（新建） | 新增 | 存放 API Key，已在 .gitignore |
| `config/requirements.txt` | 修改 | 新增 `aiohttp`（方案B）或 `kokoro`（方案A）|

`.env` 文件已在 `.gitignore` 中（`*.env.*` 和 `.env`），**不会被提交到 GitHub**。

---

*文档生成日期：2026-04-20*  
*适用版本：audio-synthesis-demo main 分支*
