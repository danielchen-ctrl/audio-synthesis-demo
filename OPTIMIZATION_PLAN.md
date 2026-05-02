# 🔧 audio-synthesis-demo 优化方案

> 基于 `PROJECT_EXPLANATION.md` 第 5 章优缺点分析  
> 生成日期：2026-04-20  
> 优先级：P0（阻塞性）→ P1（高价值）→ P2（锦上添花）

---

## P0：可维护性紧急项（建议 1-2 周内完成）

### 【P0-1】`embedded_server_main.py` 职责拆分

**问题**：单文件 2000+ 行，HTTP 服务 / TTS 流水线 / Bundle 管理 / Manifest 缓存 / 文本生成全混在一起。修任何一处都要在 2000 行里找上下文。

**方案**：

```
src/demo_app/
├── embedded_server_main.py    ← 只剩 Tornado Application 入口 + main()，目标 < 200 行
├── server/
│   ├── handlers.py            ← 所有 Tornado Handler 类（TextHandler, AudioHandler, ...）
│   ├── bundle_manager.py      ← _cache_is_fresh / _extract_bundle_modules / _extract_static_assets
│   └── manifest_cache.py      ← _manifest_cache / _register_manifest / _find_manifest（线程安全封装）
└── tts/
    ├── base.py                ← TTSEngine Protocol/ABC 定义（见 P1-1）
    └── edge_tts_engine.py     ← 现有 edge_tts 逻辑迁移过来
```

**执行步骤**：
1. 先提取 `manifest_cache.py`（最独立，零副作用，容易测试）
2. 再提取 `bundle_manager.py`（依赖文件系统，需 smoke test 验证）
3. 最后拆 `handlers.py`（影响最大，需全量回归）

**预估工时**：3-5 天  
**收益**：可维护性从 3/5 → 4.5/5，单模块行数控制在 300 行以内

---

## P1：高价值优化（建议 2-4 周内完成）

### 【P1-1】TTS 引擎抽象层

**问题**：`_synthesize_audio_from_lines()` 硬编码 edge_tts，换引擎 = 改核心函数，风险高。

**方案**：定义 `TTSEngine` Protocol：

```python
# src/demo_app/tts/base.py
from typing import Protocol
from pathlib import Path

class TTSEngine(Protocol):
    async def synthesize_line(
        self,
        text: str,
        voice: str,
        output_path: Path,
    ) -> None:
        """将单行文本合成为音频文件"""
        ...

    def list_voices(self, language: str) -> list[str]:
        """返回指定语言的可用音色列表"""
        ...
```

**实现路径**：
- `EdgeTTSEngine`：封装现有 edge_tts 逻辑（立即实现）
- `KokoroEngine`：对照 `TTS_UPGRADE_GUIDE.md` 接入本地 Kokoro（后续）
- `SiliconFlowEngine`：接入 SiliconFlow API（后续）

**切换配置**（`config/server_config.yaml` 新增）：
```yaml
tts:
  engine: edge_tts   # 可选: edge_tts / kokoro / siliconflow
  concurrency: 5
```

**预估工时**：2-3 天  
**收益**：TTS 升级从"改核心函数"变成"换一行配置"

---

### 【P1-2】demo/ 目录自动清理

**问题**：每次生成写入 `demo/{timestamp}/`，长时间运行磁盘无上限增长。

**方案 A（推荐）**：启动时清理，配置驱动：

```python
# config/server_config.yaml 新增
storage:
  demo_retention_days: 7      # 保留最近 7 天
  demo_max_count: 200         # 或最多保留 200 个 session

# bundle_manager.py（或新 storage_manager.py）
def cleanup_old_demos(demo_dir: Path, retention_days: int = 7, max_count: int = 200):
    """服务启动时调用，清理过期 demo 目录"""
    sessions = sorted(demo_dir.glob("[0-9]*"), key=lambda p: p.stat().st_mtime)
    cutoff = datetime.now() - timedelta(days=retention_days)
    for session in sessions:
        if session.stat().st_mtime < cutoff.timestamp():
            shutil.rmtree(session, ignore_errors=True)
    # 超出 max_count 的也清理（最老的先删）
    while len(list(demo_dir.glob("[0-9]*"))) > max_count:
        shutil.rmtree(sessions.pop(0), ignore_errors=True)
```

**方案 B**：在 `AudioHandler` 成功返回后异步触发清理（不阻塞响应）

**预估工时**：0.5 天  
**收益**：磁盘风险从"低"→"无"

---

### 【P1-3】训练语料冷启动问题

**问题**：`demo/training_long_dialogue/` 被 gitignore，新机器需跑 2-4 小时批量生成才能用 Few-shot。

**方案**：提供"最小种子语料包"入 git：

```
demo/training_long_dialogue/
└── .gitkeep_seed/                 ← 这个子目录入 git（修改 .gitignore 例外）
    ├── medical_zh_5000.txt        ← 每个行业/语言各 1 个示例（手工精选）
    ├── finance_en_5000.txt
    └── ...（14 个行业 × 2 语言核心样本 = 28 个文件，约 5MB）
```

同时在 `few_shot_selector.py` 的降级逻辑里：优先用 `training_long_dialogue/` 下的文件，无精确匹配时 fallback 到 `.gitkeep_seed/`。

**预估工时**：1 天（主要是手工精选语料）  
**收益**：新环境冷启动从"2-4 小时"→"开箱即用"

---

### 【P1-4】Latin 语言质量改进

**问题**：法/德/西/葡语用"英语生成 → Google Translate"，翻译有损耗 + 网络依赖。

**方案（二选一）**：

**方案 A（短期）**：将翻译引擎改为离线优先：
```python
# 优先用 argostranslate（本地，无网络）
# 降级用 deep_translator（在线，当前方案）
# 再降级：直接返回英文原文 + 提示用户
```

**方案 B（中期，配合 P1-1 的 TTS 抽象层）**：为法/德/西/葡语直接配置对应语言的 edge_tts 音色，LLM 改为直接生成目标语言（需 few-shot 支持），绕开翻译环节。

**预估工时**：方案 A 1-2 天，方案 B 3-5 天（依赖 few-shot 语料准备）  
**收益**：Latin 语言质量+稳定性显著提升

---

## P2：改善项（有空再做）

### 【P2-1】长对话去重升级

**问题**：多段拼接时仅完全相等去重，相似句子不过滤。

**方案**：引入相似度去重（不需要 ML，轻量实现）：

```python
from difflib import SequenceMatcher

def is_too_similar(line_a: str, line_b: str, threshold: float = 0.85) -> bool:
    return SequenceMatcher(None, line_a, line_b).ratio() > threshold

# 在 _generate_long_dialogue_lines() 的去重逻辑里替换原有的 set() 去重
```

**预估工时**：0.5 天  
**收益**：长对话自然度提升，减少重复感

---

### 【P2-2】ffmpeg 跨平台解耦

**问题**：`bin/ffmpeg.exe` 绑定 Windows，macOS/Linux 无法运行。

**方案**：

```python
# utils/ffmpeg_finder.py
import shutil, sys
from pathlib import Path

def find_ffmpeg() -> str:
    """按优先级查找 ffmpeg：项目内置 > PATH 系统 > 报错"""
    bundled = Path(__file__).parent.parent / "bin" / (
        "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    )
    if bundled.exists():
        return str(bundled)
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    raise RuntimeError("找不到 ffmpeg，请安装或将 ffmpeg 放入 bin/ 目录")
```

**预估工时**：0.5 天  
**收益**：macOS/Linux 开发者可直接运行（系统装了 ffmpeg 即可）

---

### 【P2-3】Bundle LLM 版本信息透明化

**问题**：LLM 版本被封装在 `.exe` 里，无从得知当前用的是什么版本。

**方案**：在 bundle 解压时读取版本信息文件并暴露到 API：

```python
# GET /api/system_info 新增字段
{
  "bundle_version": "1.2.3",       # 从 bundle 内 VERSION 文件读取
  "bundle_lm_info": "Llama-3-...", # 从 bundle 内 MODEL_INFO 文件读取（需 bundle 侧配合）
  "edge_tts_version": "6.1.9"      # importlib.metadata.version("edge-tts")
}
```

**预估工时**：1 天（需 bundle 侧配合写入版本文件）  
**收益**：排查问题时有版本依据

---

## 优先级汇总

| 编号 | 项目 | 优先级 | 预估工时 | 主要收益 |
|------|------|--------|---------|---------|
| P0-1 | `embedded_server_main.py` 拆分 | 🔴 P0 | 3-5 天 | 可维护性 3→4.5 |
| P1-1 | TTS 引擎抽象层 | 🟠 P1 | 2-3 天 | TTS 可插拔 |
| P1-2 | demo/ 自动清理 | 🟠 P1 | 0.5 天 | 消除磁盘风险 |
| P1-3 | 训练语料冷启动 | 🟠 P1 | 1 天 | 新环境开箱即用 |
| P1-4 | Latin 语言质量 | 🟠 P1 | 1-5 天 | 翻译质量+稳定性 |
| P2-1 | 去重升级 | 🟡 P2 | 0.5 天 | 对话自然度 |
| P2-2 | ffmpeg 跨平台 | 🟡 P2 | 0.5 天 | macOS/Linux 支持 |
| P2-3 | Bundle 版本透明化 | 🟡 P2 | 1 天 | 排查便利性 |

**建议执行顺序**：P0-1 → P1-2（最快见效）→ P1-1 → P1-3 → P1-4 → P2 系列
