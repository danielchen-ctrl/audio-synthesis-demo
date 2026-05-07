# 真人 TTS API 接入方案

> 版本：v4.1 终版 · 2026-05-07  
> 状态：**已通过审核，可进入 Phase 1 开发**

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [现状分析](#2-现状分析)
3. [核心设计原则](#3-核心设计原则)
4. [数据模型](#4-数据模型)
5. [Provider 抽象层](#5-provider-抽象层)
6. [段落合并规则](#6-段落合并规则)
7. [API 能力分级](#7-api-能力分级)
8. [异步 API Job 轮询模型](#8-异步-api-job-轮询模型)
9. [失败分类与降级体系](#9-失败分类与降级体系)
10. [数据库迁移](#10-数据库迁移)
11. [兼容策略](#11-兼容策略)
12. [配置与鉴权](#12-配置与鉴权)
13. [前端音色选择器](#13-前端音色选择器)
14. [任务状态与 UI 展示](#14-任务状态与-ui-展示)
15. [改动文件清单](#15-改动文件清单)
16. [上线分阶段计划](#16-上线分阶段计划)
17. [验收标准](#17-验收标准)
18. [开工前置条件](#18-开工前置条件)

---

## 1. 背景与目标

### 1.1 当前问题

Microsoft edge_tts Neural 合成音频存在以下问题：

- **拼接感明显**：每行文本独立合成，句间停顿机械，情绪连续性中断
- **韵律不连贯**：同一角色前后句音调、语速不一致
- **音色偏假**：Neural 音色与真人语音差距明显，影响语料质量

### 1.2 目标

接入真人 TTS API，实现以下效果提升：

| 维度 | 当前（edge_tts） | 目标（真人 API） |
|------|-----------------|----------------|
| 合成粒度 | 每行独立 | 按角色段落合并，可整段对话一次请求 |
| 音色质量 | Neural 合成 | 真人录制音色 |
| 情绪连续性 | 无 | 支持 style/emotion 参数（API 能力许可时）|
| 句间停顿 | 机械固定 | SSML 或停顿参数控制 |
| 可观测性 | 仅成功/失败 | 逐段 provider 追踪、降级原因、耗时 |

### 1.3 不在本方案范围内

- edge_tts 完全废弃（保留作 fallback）
- bundle TTS 完全废弃（保留作最后保底）
- 批量训练链路接入（Phase 3，需单独成本评审后跟进）

---

## 2. 现状分析

### 2.1 当前合成链路

```
对话文本行列表
  └─ _synthesize_audio_from_lines()          # embedded_server_main.py
       ├─ 遍历每行：edge_tts.Communicate(text, voice).save()
       │    ├─ Phase 0：并发合成，失败的行记录
       │    ├─ Phase 0b：失败行串行重试
       │    └─ Phase 0c：仍失败 → raise → 进入 except
       ├─ 成功路径：ffmpeg concat 拼接 MP3
       └─ except 路径：bundle_server._generate_wave_for_lines()
                        （返回 warning: "edge_tts_fallback:..."）
```

### 2.2 现有 voice 相关字段

**后端 `VOICE_CATALOG`**（`embedded_server_main.py`）：自动分配，key 为语言名，value 为 Neural voice 字符串列表。

**前端 `VOICE_LIBRARY`**（`static/app.js`）：用户手动选择，同结构。

**任务表 `voice_map`**（`tasks` 表）：`{"1": "zh-CN-XiaoxiaoNeural", "2": "zh-CN-YunxiNeural"}` 格式，拆列存储。

### 2.3 当前 tasks 表实际字段

```
task_id, status, generation_mode, topic, language,
people_count, word_count, error_msg, file_id,
voice_map (TEXT/JSON), output_format, keywords,
template, custom_prompt, input_text, include_scripts
```

**没有 `params_json`**——参数是拆列存储的。本方案选择扩列路线（路线 A），不顺手加 `params_json`，降低首版接入风险。

---

## 3. 核心设计原则

| 原则 | 具体体现 |
|------|---------|
| Provider 与 voice_id 分离 | 不用 `voice.startswith("real_")` 路由，provider 独立字段 |
| 合成粒度按 API 能力适配 | 优先段落级/整段，最差退化到单句，不硬编码 |
| 显式降级，不静默成功 | 用户选择真人 API 时，降级必须在 UI 明确标注 |
| 兼容旧数据，不破坏历史任务 | `voice_map` 只读不写，新任务写 `voice_assignments` |
| 可观测性优先 | 逐段记录 provider、耗时、降级原因、时间轴来源 |
| 鉴权走环境变量 | API URL 和 Key 不进任何配置文件 |

---

## 4. 数据模型

### 4.1 VoiceSpec — 统一音色参数对象

```python
@dataclass
class VoiceSpec:
    provider: str          # "edge_tts" | "real_human" | "bundle"
    voice_id: str          # provider 内部 ID
    language: str          # "Chinese" / "English" / ...
    gender: str = "female"
    style: str | None = None      # "calm" / "professional" / None
    emotion: str | None = None    # "neutral" / "warm" / None
    speed: float = 1.0
    sample_rate: int = 24000

    VALID_PROVIDERS = {"edge_tts", "real_human", "bundle"}

    @classmethod
    def from_dict(
        cls,
        data: dict,
        language: str = "Chinese",
        fallback_provider: str = "edge_tts",
    ) -> "VoiceSpec":
        """带校验和默认值补齐的构造方法，防止前端少传字段导致异常"""
        provider = data.get("provider") or fallback_provider
        if provider not in cls.VALID_PROVIDERS:
            logger.warning("[VoiceSpec] 未知 provider=%s，回退 %s", provider, fallback_provider)
            provider = fallback_provider
        return cls(
            provider=provider,
            voice_id=data.get("voice_id") or "",
            language=data.get("language") or language,
            gender=data.get("gender") or "female",
            style=data.get("style"),
            emotion=data.get("emotion"),
            speed=float(data.get("speed") or 1.0),
            sample_rate=int(data.get("sample_rate") or 24000),
        )
```

### 4.2 SynthesisRequest — 合成请求单元（段落级）

```python
@dataclass
class SynthesisRequest:
    speaker: str               # "Speaker 1"
    segments: list[str]        # 该角色连续多句，合并为段落
    voice_spec: VoiceSpec
    line_indices: list[int]    # 对应原始行号，用于时间轴回填
```

### 4.3 SynthesisResult — 合成结果

```python
@dataclass
class SynthesisResult:
    request: SynthesisRequest
    audio_path: Path | None
    provider_used: str          # 实际执行的 provider（可能降级）
    degraded: bool
    degraded_reason: str | None # 见失败分类表
    latency_ms: int
    api_response_code: int | None
    request_chars: int          # 本次请求字符数
    audio_duration_ms: int      # 实际音频时长（ms）
    timeline_source: str        # "api_word_timestamp" | "estimated" | "original"
    # 异步 API 专用（同步模式为 None）
    job_id: str | None = None
    submit_latency_ms: int | None = None
    poll_count: int | None = None
    download_latency_ms: int | None = None
```

### 4.4 tts_meta — 写入 audio_files 表的 JSON 字段

```json
{
  "requested_provider": "real_human",
  "actual_provider": "mixed",
  "degraded_level": "partial",
  "degraded_to": "edge_tts",
  "degraded_reason": "timeout:2seg,rate_limit:1seg",
  "segment_results": [
    {
      "line_indices": [0, 1, 2],
      "speaker": "Speaker 1",
      "provider_used": "real_human",
      "latency_ms": 1240,
      "degraded": false,
      "error": null,
      "request_chars": 98,
      "audio_duration_ms": 6200,
      "timeline_source": "api_word_timestamp",
      "job_id": null,
      "submit_latency_ms": null,
      "poll_count": null,
      "download_latency_ms": null
    },
    {
      "line_indices": [3, 4],
      "speaker": "Speaker 2",
      "provider_used": "edge_tts",
      "latency_ms": 320,
      "degraded": true,
      "error": "timeout",
      "request_chars": 126,
      "audio_duration_ms": 8420,
      "timeline_source": "estimated",
      "job_id": null,
      "submit_latency_ms": null,
      "poll_count": null,
      "download_latency_ms": null
    }
  ]
}
```

`tts_meta` 字段语义：

| 字段 | 类型 | 取值说明 |
|------|------|---------|
| `requested_provider` | str | 用户/配置期望的 provider |
| `actual_provider` | str | `real_human` \| `edge_tts` \| `bundle` \| `mixed` |
| `degraded_level` | str | `none` \| `partial` \| `full` |
| `degraded_to` | str | `edge_tts` \| `bundle` \| `mixed` \| `null` |
| `degraded_reason` | str | 人读摘要，如 `timeout:2seg` |
| `segment_results` | list | 每个 SynthesisRequest 的逐段明细 |

---

## 5. Provider 抽象层

### 5.1 TTSProvider 接口

**新建 `src/demo_app/tts_provider.py`**：

```python
class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(
        self, request: SynthesisRequest, output_path: Path
    ) -> SynthesisResult: ...

    @abstractmethod
    def supports_multi_segment(self) -> bool:
        """是否支持段落级/对话级合成"""
        ...

    @abstractmethod
    def available_voices(self, language: str) -> list[VoiceSpec]: ...
```

三个实现类：

| 类名 | 位置 | 说明 |
|------|------|------|
| `EdgeTTSProvider` | `tts_provider.py` | 现有 edge_tts 逻辑迁入 |
| `RealHumanProvider` | `real_human_tts.py` | 新真人 API（新建） |
| `BundleProvider` | `tts_provider.py` | 现有 bundle fallback 迁入 |

### 5.2 ProviderCapabilities — 结构化能力声明

**不用 `tier == "A"` 字符串路由**，改用字段逐项判断：

```python
@dataclass
class ProviderCapabilities:
    tier: str                        # "A" | "B" | "C"（辅助标签，不做路由依据）
    supports_ssml: bool              # 支持 SSML <break> / <voice>
    supports_multi_speaker: bool     # 单次请求含多 speaker tag
    supports_word_timestamps: bool   # 返回字级时间戳
    supports_pause_control: bool     # 支持停顿参数 or SSML break
    max_chars_per_request: int       # 单次最大字符数，超出时自动切段
    output_formats: list[str]        # ["mp3", "wav", "pcm"]
    async_mode: bool                 # True = 异步 job_id 轮询模式
```

### 5.3 TTSRouter — 合成路由器

```python
class TTSRouter:
    def __init__(self, config, capabilities: ProviderCapabilities): ...

    async def synthesize_all(
        self,
        requests: list[SynthesisRequest],
        tmp_dir: Path,
    ) -> list[SynthesisResult]:
        """
        对每个 SynthesisRequest 按 provider 路由，
        失败时按 fallback_strategy 降级，记录 SynthesisResult
        """
        ...

    def _select_provider(self, spec: VoiceSpec) -> TTSProvider:
        """
        1. spec.provider == "real_human" → RealHumanProvider
        2. spec.provider == "edge_tts"   → EdgeTTSProvider
        3. spec.provider == "bundle"     → BundleProvider
        """
        ...

    def _fallback_chain(self, spec: VoiceSpec) -> list[TTSProvider]:
        """
        按 fallback_strategy 返回降级链：
        edge_then_bundle → [EdgeTTSProvider, BundleProvider]
        edge_only        → [EdgeTTSProvider]
        none             → []
        """
        ...
```

**路由执行策略**（基于 `ProviderCapabilities`，不依赖 tier 字符串）：

```python
if caps.supports_multi_speaker:
    # A 档：整段对话一次请求，含 speaker tag
elif caps.supports_ssml:
    # B 档上：按角色合并段落，SSML break 控制停顿
elif caps.max_chars_per_request >= 200:
    # B 档下：按角色合并段落，纯文本，停顿参数控制
else:
    # C 档：单句单请求（与现有 edge_tts 等价）
```

---

## 6. 段落合并规则

### 6.1 合并逻辑

```
输入：[(speaker, text), ...]

步骤 1  连续相同 speaker → 合并为一个 SynthesisRequest
步骤 2  单个 Request 超过 MAX_CHARS(500 字) → 在句号/换行处切段
步骤 3  按 ProviderCapabilities 决定是否合并多 speaker
```

### 6.2 时间轴回填策略

合并后音频完成，**按字符数比例切分时间戳**：

```
合并请求：["你好。", "我今天来是想问一下。", "关于这个问题……"]
合成音频：总时长 T 毫秒

line_i.start_time = T × (字符前缀和_i / 总字符数)
line_i.end_time   = T × (字符前缀和_{i+1} / 总字符数)
```

- **优先**：若 API 返回字级时间戳，使用 API 返回值，`timeline_source = "api_word_timestamp"`
- **兜底**：字符比例估算，`timeline_source = "estimated"`
- 字幕和详情页按**原始行粒度**回填，不暴露合并边界给用户

### 6.3 句间停顿策略

| API 能力 | 停顿处理方式 |
|----------|-------------|
| `supports_ssml = true` | 句号后插 `<break time="400ms"/>`，段落间插 `<break time="800ms"/>` |
| `supports_pause_control = true` | 按语言设不同默认值（中文 350ms / 英文 300ms / 日文 300ms） |
| 仅纯文本 | 句号后追加全角空格模拟停顿（效果有限，在 `tts_meta` 中注明） |

---

## 7. API 能力分级

系统根据 `ProviderCapabilities` 字段自动适配，**无需改代码**切换档位。

### A 档：整段多 speaker / SSML

```yaml
capabilities:
  tier: "A"
  supports_ssml: true
  supports_multi_speaker: true
  supports_word_timestamps: true
  supports_pause_control: true
  max_chars_per_request: 5000
  output_formats: ["mp3", "wav"]
  async_mode: false
```

| 项目 | 行为 |
|------|------|
| 合成粒度 | 整段对话一次请求（含多 speaker tag） |
| 停顿 | SSML `<break>` |
| 时间轴 | API 字级时间戳（最准） |
| 预期效果 | 最佳，情绪连续，角色切换自然 |

### B 档：段落级单 speaker

```yaml
capabilities:
  tier: "B"
  supports_ssml: false
  supports_multi_speaker: false
  supports_word_timestamps: false
  supports_pause_control: true
  max_chars_per_request: 500
  output_formats: ["mp3"]
  async_mode: false
```

| 项目 | 行为 |
|------|------|
| 合成粒度 | 按角色合并段落，每段一请求，并发执行 |
| 停顿 | 停顿参数 or 句号后追加标记 |
| 时间轴 | 字符比例估算 |
| 预期效果 | 良好，单角色内部连贯，角色切换处仍有轻微拼接感 |

### C 档：单句单请求

```yaml
capabilities:
  tier: "C"
  supports_ssml: false
  supports_multi_speaker: false
  supports_word_timestamps: false
  supports_pause_control: false
  max_chars_per_request: 100
  output_formats: ["mp3"]
  async_mode: false
```

| 项目 | 行为 |
|------|------|
| 合成粒度 | 每行一请求（与现有 edge_tts 等价） |
| 停顿 | 无，依赖 ffmpeg concat 间隔 |
| 时间轴 | 原始行粒度 |
| 预期效果 | 仅音色提升，拼接感不变；**上线前须向业务方说明** |

> **C 档接入后效果提升有限，应在上线评审时明确告知业务方，避免预期落差。**

---

## 8. 异步 API Job 轮询模型

适用于 `capabilities.async_mode = true` 的 API（提交任务后返回 job_id，需轮询获取结果）：

```python
class RealHumanProvider(TTSProvider):

    async def submit_job(self, request: SynthesisRequest) -> str:
        """提交合成任务，返回 job_id"""
        ...

    async def poll_job(
        self,
        job_id: str,
        timeout_sec: int = 60,
        interval_sec: float = 2.0,
    ) -> dict:
        """
        轮询直到完成或超时。
        返回 {"status": "completed", "result_url": "...", "poll_count": N}
        超时 → raise TimeoutError
        失败 → raise RuntimeError
        """
        elapsed = 0.0
        poll_count = 0
        while elapsed < timeout_sec:
            resp = await self._get_job_status(job_id)
            poll_count += 1
            if resp["status"] == "completed":
                return {**resp, "poll_count": poll_count}
            if resp["status"] == "failed":
                raise RuntimeError(f"job {job_id} failed: {resp.get('error')}")
            await asyncio.sleep(interval_sec)
            elapsed += interval_sec
        raise TimeoutError(f"job {job_id} 超时 {timeout_sec}s，已 poll {poll_count} 次")

    async def download_audio(self, result_url: str, output_path: Path) -> None:
        """下载音频流到本地临时路径"""
        ...

    async def synthesize(
        self, request: SynthesisRequest, output_path: Path
    ) -> SynthesisResult:
        t0 = time.monotonic()
        if self.capabilities.async_mode:
            job_id = await self.submit_job(request)
            submit_ms = int((time.monotonic() - t0) * 1000)
            t1 = time.monotonic()
            poll_result = await self.poll_job(job_id)
            t2 = time.monotonic()
            await self.download_audio(poll_result["result_url"], output_path)
            download_ms = int((time.monotonic() - t2) * 1000)
            # 写入 SynthesisResult 的各阶段耗时字段
        else:
            # 同步直接返回音频流
            ...
```

`tts_meta.segment_results` 中的异步字段：

```json
{
  "job_id": "tts_job_abc123",
  "submit_latency_ms": 120,
  "poll_count": 6,
  "download_latency_ms": 430
}
```

---

## 9. 失败分类与降级体系

### 9.1 六类失败

| 错误类型 | 触发条件 | 降级策略 | 记录内容 |
|----------|----------|----------|----------|
| `timeout` | 超过 `timeout_sec` | 降级 edge_tts | 超时时长 |
| `rate_limit` | HTTP 429 | 等待 `retry_after` 再试，最多 2 次；仍失败降级 | retry 次数 |
| `auth_failure` | HTTP 401/403 | 立即降级，不重试；打 WARN 日志 | 响应体摘要 |
| `param_error` | HTTP 400 | 降级，记录请求参数快照 | 请求参数 + 响应体 |
| `empty_audio` | 响应 200 但文件为空/损坏 | 降级，记录文件字节数 | bytes 大小 |
| `provider_error` | HTTP 5xx | 最多重试 1 次，仍失败降级 | 状态码 + 响应体摘要 |

### 9.2 三层降级链

```
real_human
  └─ 失败 → edge_tts（fallback_strategy 包含 edge）
               └─ 失败 → bundle（fallback_strategy 包含 bundle）
                            └─ 失败 → task 置为 failed
```

`fallback_strategy` 取值：

| 值 | 行为 |
|----|------|
| `edge_then_bundle` | 两级降级（默认） |
| `edge_only` | 最多降级到 edge，bundle 不启用 |
| `none` | 不降级，real_human 失败直接 task failed |

### 9.3 显式 provider 行为规范

| 配置情况 | 系统行为 |
|----------|---------|
| `provider=auto` + API 未配置 | 自动回退 edge_tts；前端真人音色置灰 + Tooltip；日志 WARN 一次；正常启动 |
| `provider=real_human` + API 未配置 | 启动时日志 ERROR；真人音色置灰；选了 real_human 的任务**直接 failed**，提示"真人 API 未配置" |
| 单任务显式选 real_human + API 失败 | 按 `fallback_strategy` 降级；**不允许静默绿色成功**；`tts_meta` 必须记录降级 |

> **核心原则：用户显式选择 real_human 时，静默降级是禁止行为。**

---

## 10. 数据库迁移

### 10.1 新增列

**tasks 表**：

| 列名 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tts_provider` | TEXT | `'edge_tts'` | 用户/配置期望的 provider |
| `tts_fallback_strategy` | TEXT | `'edge_then_bundle'` | 降级策略 |
| `voice_assignments` | TEXT | `'{}'` | 新格式音色参数（JSON） |

**audio_files 表**：

| 列名 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `tts_meta` | TEXT | `NULL` | 完整降级详情（JSON，见 §4.4） |

### 10.2 幂等迁移实现

```python
# src/webapp/db.py

CRITICAL_TTS_COLUMNS = [
    # 关键列：缺失会导致任务创建/消费时直接报错
    ("tasks",       "tts_provider",         "TEXT DEFAULT 'edge_tts'"),
    ("tasks",       "voice_assignments",     "TEXT DEFAULT '{}'"),
    ("audio_files", "tts_meta",              "TEXT DEFAULT NULL"),
]

NON_CRITICAL_TTS_COLUMNS = [
    # 非关键列：缺失只影响统计/排查，不阻断主流程
    ("tasks", "tts_fallback_strategy", "TEXT DEFAULT 'edge_then_bundle'"),
]

def _add_column_if_missing(conn, table: str, col: str, col_def: str):
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if col not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
        logger.info("[db-migrate] %s.%s 新增成功", table, col)
    else:
        logger.debug("[db-migrate] %s.%s 已存在，跳过", table, col)

def _run_tts_migration(conn) -> bool:
    """返回 True = 关键列全部就绪，False = 有关键列失败"""
    critical_ok = True
    for table, col, defn in CRITICAL_TTS_COLUMNS:
        try:
            _add_column_if_missing(conn, table, col, defn)
        except Exception as e:
            logger.error("[db-migrate][CRITICAL] %s.%s 失败: %s", table, col, e)
            critical_ok = False
    for table, col, defn in NON_CRITICAL_TTS_COLUMNS:
        try:
            _add_column_if_missing(conn, table, col, defn)
        except Exception as e:
            logger.warning("[db-migrate][WARN] %s.%s 失败（非关键）: %s", table, col, e)
    conn.commit()
    return critical_ok
```

### 10.3 启动时阻断策略

```python
# server_platform.py 启动序列

migration_ok = _run_tts_migration(conn)
if not migration_ok:
    if effective_provider == "real_human":
        raise RuntimeError("[TTS] 关键列迁移失败，real_human 模式无法启动")
    else:
        logger.error("[TTS] 关键列迁移失败，真人 TTS 功能已禁用，回退 edge_tts")
        effective_provider = "edge_tts"
```

| 场景 | 行为 |
|------|------|
| 关键列失败 + `provider=real_human` | 启动失败，明确报错 |
| 关键列失败 + `provider=auto/edge` | 启动成功，真人 TTS 禁用，日志 ERROR |
| 非关键列失败 | 启动成功，日志 WARN，功能完整 |
| 重复启动（列已存在） | 日志 debug，无副作用 |

---

## 11. 兼容策略

### 11.1 voice_map → voice_assignments 双轨兼容

**`voice_map` 只读不写**——新任务只写 `voice_assignments`，历史任务仍能正常回放。

**新建 `src/demo_app/voice_resolver.py`**（所有入口统一调用）：

```python
def resolve_voice_spec(
    speaker_id: str,
    language: str,
    voice_assignments: dict | None = None,   # 新格式（优先）
    voice_map: dict | None = None,           # 旧格式（兼容）
    effective_provider: str = "edge_tts",
) -> VoiceSpec:
    # 1. 优先读新格式 voice_assignments
    if voice_assignments and speaker_id in voice_assignments:
        return VoiceSpec.from_dict(
            voice_assignments[speaker_id],
            language=language,
            fallback_provider=effective_provider,
        )
    # 2. 降级读旧格式 voice_map（只读，不写）
    if voice_map and speaker_id in voice_map:
        return VoiceSpec(
            provider="edge_tts",
            voice_id=voice_map[speaker_id],
            language=language,
        )
    # 3. 按语言自动分配默认音色
    return default_voice_spec(language, speaker_id, effective_provider)
```

调用方一览：

| 调用位置 | 传入来源 |
|----------|---------|
| `task_runner.py` | `task["voice_assignments"]` + `task["voice_map"]` |
| `embedded_server_main.py`（legacy modal） | payload 里的 `voice_assignments` / `voice_map` |
| 批量训练链路（Phase 3，后续） | 同上 |

### 11.2 legacy modal 兼容

**Phase 1 先只改 platform tasks**，legacy modal（生成语料弹窗）保持现有 edge_tts 逻辑不变，等 Phase 1 稳定后 Phase 2 跟进。

历史通过 legacy modal 生成的文件：`tts_meta` 为 NULL，`tts_provider` 为默认值 `'edge_tts'`，UI 正常显示，不受影响。

### 11.3 没有配置真人 API 时

```
启动检测：
  REAL_HUMAN_TTS_API_URL 未设置
    → provider=auto：强制回退 edge_tts，前端真人音色置灰（Tooltip："真人 API 未配置"）
    → provider=real_human：启动阻断或功能禁用（见 §10.3）
    → 日志 WARN/ERROR，不静默
```

---

## 12. 配置与鉴权

### 12.1 config/runtime.yaml（仅非敏感项）

```yaml
tts:
  provider: "auto"                   # edge_tts | real_human | auto
  segment_merge_max_chars: 500       # 段落合并字数上限
  real_human:
    timeout_sec: 30
    max_retries: 2
    fallback_to_edge: true
    fallback_to_bundle: true
    capabilities:
      tier: "B"                      # 辅助标签，路由不依赖此值
      supports_ssml: false
      supports_multi_speaker: false
      supports_word_timestamps: false
      supports_pause_control: true
      max_chars_per_request: 500
      output_formats: ["mp3"]
      async_mode: false
    # api_url 和 api_key 不在此处，走环境变量
```

### 12.2 环境变量（唯一鉴权来源）

```bash
REAL_HUMAN_TTS_API_URL=https://api.example.com/v1/tts
REAL_HUMAN_TTS_API_KEY=sk-xxxxxxxxxxxxxxxx
```

### 12.3 启动校验逻辑

```python
# server_platform.py

api_url = os.environ.get("REAL_HUMAN_TTS_API_URL", "").strip()
api_key = os.environ.get("REAL_HUMAN_TTS_API_KEY", "").strip()
configured_provider = runtime_cfg.get("tts", {}).get("provider", "edge_tts")

if configured_provider in ("real_human", "auto") and not api_url:
    if configured_provider == "real_human":
        raise RuntimeError("[TTS] provider=real_human 但 REAL_HUMAN_TTS_API_URL 未设置")
    else:
        logger.warning("[TTS] provider=auto 但 API 未配置，强制回退 edge_tts")
        effective_provider = "edge_tts"
else:
    effective_provider = configured_provider
```

---

## 13. 前端音色选择器

### 13.1 VOICE_LIBRARY 分组（app.js）

```javascript
Chinese: [
  // 真人音色（API 配置后启用）
  { value: "real_zh_f1", label: "🎙 真人·女声 A", group: "real", provider: "real_human" },
  { value: "real_zh_m1", label: "🎙 真人·男声 A", group: "real", provider: "real_human" },
  // Neural 音色（保留）
  { value: "zh-CN-XiaoxiaoNeural", label: "晓晓（女·青年·亲切）", group: "neural", provider: "edge_tts" },
  { value: "zh-CN-YunxiNeural",    label: "云希（男·青年·活泼）", group: "neural", provider: "edge_tts" },
  ...
]
```

### 13.2 选择器 UI

```
音色选择（Speaker 1）
├── 🎙 真人音色
│   ├── 真人·女声 A（自然）
│   └── 真人·男声 A（沉稳）
│   [style 下拉，若 API 支持]
└── 🤖 Neural 音色
    ├── 晓晓（女·青年·亲切）
    └── 云扬（男·中年·新闻）
```

- 真人 API 未配置时，真人音色分组置灰 + Tooltip 提示
- 选中真人音色后，若 `capabilities.supports_pause_control` 为 true，显示 style/emotion 附加选项

### 13.3 任务 payload 扩展

```javascript
// POST /api/platform/tasks 的新字段
{
  "tts_provider": "real_human",          // 或 "auto" / "edge_tts"
  "tts_fallback_strategy": "edge_then_bundle",
  "voice_assignments": {
    "1": { "provider": "real_human", "voice_id": "real_zh_f1", "style": "calm" },
    "2": { "provider": "real_human", "voice_id": "real_zh_m1" }
  }
}
```

---

## 14. 任务状态与 UI 展示

### 14.1 任务状态规则

`status` 枚举**不新增值**，UI 完全依赖 `tts_meta` 展示警告：

| 场景 | `status` | `tts_meta.degraded_level` | `tts_meta.degraded_to` |
|------|----------|--------------------------|------------------------|
| 全程真人 API 成功 | `completed` | `none` | `null` |
| 部分段降级至 edge | `completed` | `partial` | `edge_tts` |
| 部分段降级至 bundle | `completed` | `partial` | `bundle` |
| 全程降级至 edge | `completed` | `full` | `edge_tts` |
| 全程降级至 bundle | `completed` | `full` | `bundle` |
| `fallback_strategy=none` 且失败 | `failed` | — | — |
| 三层全部失败 | `failed` | — | — |

### 14.2 任务卡片五级展示

```
tts_meta.degraded_level=none
  → ✅ 已完成（真人 API）                          绿色

tts_meta.degraded_level=partial, degraded_to=edge_tts
  → ⚠️ 已完成（部分降级·Neural）                   橙色

tts_meta.degraded_level=partial, degraded_to=bundle
  → ⚠️ 已完成（部分降级·合成音色）                  橙深色

tts_meta.degraded_level=full, degraded_to=edge_tts
  → ⚠️ 已完成（全程 Neural，真人 API 失败）          橙色

tts_meta.degraded_level=full, degraded_to=bundle
  → 🔴 已完成（全程合成音色，质量较低）               红色（独立于橙色系）

status=failed
  → ❌ 失败
```

> **bundle 降级单独用红色**，与 edge 降级的橙色区分，因为对用户听感影响明显更大。

---

## 15. 改动文件清单

### 15.1 不依赖 API 文档，可立即开工

| 文件 | 改动性质 | 主要内容 |
|------|----------|---------|
| `src/demo_app/tts_provider.py` | **新建** | TTSProvider 抽象、ProviderCapabilities、TTSRouter、EdgeTTSProvider 迁入、BundleProvider 迁入 |
| `src/demo_app/voice_resolver.py` | **新建** | VoiceSpec.from_dict、resolve_voice_spec、default_voice_spec，兼容新旧格式 |
| `src/webapp/db.py` | 修改 | _add_column_if_missing、_run_tts_migration、关键列失败阻断 |
| `src/webapp/task_runner.py` | 修改 | 传 tts_provider / voice_assignments；合成后写 tts_meta；调用 voice_resolver |
| `src/webapp/handlers.py` | 修改 | _import 路径写 tts_meta；移除 voice 解析逻辑（移入 voice_resolver） |
| `static/app.js` | 修改 | VOICE_LIBRARY 分组（real/neural）；voice_assignments payload；真人音色置灰逻辑 |
| `static/index.html` | 修改 | 五级降级状态展示；真人 API 未配置时 Tooltip |

### 15.2 依赖 API 文档，等文档到位后开工

| 文件 | 改动性质 | 主要内容 |
|------|----------|---------|
| `src/demo_app/real_human_tts.py` | **新建** | RealHumanProvider 实现；同步/异步双模式；六类失败处理；job 轮询（async_mode=true 时） |
| `config/runtime.yaml` | 修改 | tts.real_human.capabilities 按实际 API 填写 |

### 15.3 不需要改动的文件

`training/`、`few_shot_selector.py`、`multilingual_naturalness.py`、`rule_loader.py`、音频拼接/脚本生成逻辑。

---

## 16. 上线分阶段计划

```
Phase 1  platform tasks 支持真人 API
          改动：db.py + tts_provider.py + voice_resolver.py + task_runner.py
                real_human_tts.py + runtime.yaml（需 API 文档）
                前端 VOICE_LIBRARY 分组 + 任务卡片五级展示
          验收：单条任务试听 + 降级路径覆盖测试 + DB 迁移重复启动测试

Phase 2  legacy modal 接入真人 API
          改动：embedded_server_main.py 合成调用替换为 TTSRouter
                legacy modal payload 支持 voice_assignments
          前提：Phase 1 稳定运行 ≥ 1 周

Phase 3  批量训练链路接入
          前提：Phase 1/2 稳定 + 单独完成成本/吞吐评审
          注意：训练链路体量大，API 成本需单独核算，不与 demo 同批上线
```

---

## 17. 验收标准

### 17.1 听感对比（同一段 200 字中文对话，3 人）

| 组别 | 合成方式 | 验收重点 |
|------|----------|---------|
| 对照组 | edge_tts（现有） | 基线，记录拼接感明显程度 |
| C 档 | 真人 API 单句模式 | 音色提升 vs 拼接感是否改善 |
| B 档 | 真人 API 段落合并 | 单角色连续句内部是否自然 |
| A 档（若支持） | 真人 API 整段多 speaker | 角色切换处、情绪连续性 |

逐项检查：

- [ ] 句间停顿是否机械（B/A 档应明显优于 C 档）
- [ ] 同一角色前后句韵律是否一致
- [ ] 角色切换处是否有明显拼接感
- [ ] 字幕与音频是否对齐（±500ms 以内）
- [ ] `tts_meta.timeline_source` 是否正确反映时间轴来源

### 17.2 可观测性验收

- [ ] `tts_meta` 降级记录准确反映实际执行路径
- [ ] 真人 API 失败时任务卡片正确显示五级状态，不允许静默绿色
- [ ] bundle 降级显示红色，与 edge 降级橙色可区分
- [ ] `tts_meta.segment_results` 逐段记录 provider、耗时、降级原因

### 17.3 工程稳定性验收

- [ ] 重复启动服务器 3 次，DB 迁移脚本不报错，日志显示"已存在，跳过"
- [ ] 关键列迁移失败时，服务按规则阻断或禁用真人 TTS
- [ ] `provider=real_human` + API 未配置时，任务直接 failed 并有明确提示
- [ ] `provider=auto` + API 未配置时，自动回退 edge_tts，前端真人音色置灰

### 17.4 性能与成本验收

| 指标 | 验收条件 |
|------|---------|
| 端到端耗时 | 200 字 / 3 人，首帧可播放 ≤ 15s |
| 单段平均 latency | B 档段落级 ≤ 5s / 段（来自 `tts_meta.segment_results.latency_ms`） |
| 每 1000 字预估成本 | 记录并与 edge_tts（免费）对比，用于 Phase 3 评审 |
| Worker 阻塞时间 | API 失败时 worker 释放 ≤ `timeout_sec + 2s`，确认 timeout 机制有效 |

---

## 18. 开工前置条件

### 18.1 可立即开工（无需等待）

db.py 迁移函数、voice_resolver.py 公共模块、tts_provider.py 抽象层（EdgeTTSProvider / BundleProvider 迁入）、前端 VOICE_LIBRARY 分组 UI、任务卡片五级降级展示。

### 18.2 需要 API 文档后开工

请提供以下信息：

1. **接口地址与鉴权**：API endpoint、请求方式（Header / Body）、鉴权格式
2. **ProviderCapabilities 逐项确认**：
   - 是否支持 SSML / `<break>` 标签？
   - 是否支持单次多 speaker tag？
   - 是否返回字级时间戳？
   - 是否支持停顿时长参数？
   - 单次最大字符数限制？
   - 支持哪些输出格式（mp3 / wav / pcm）？
   - 同步返回音频流，还是异步返回 job_id？
3. **音色 ID 列表**：至少中文和英文，用于填充 `REAL_HUMAN_VOICE_CATALOG`
4. **限流规则**：QPS 上限、是否返回 `retry_after`
