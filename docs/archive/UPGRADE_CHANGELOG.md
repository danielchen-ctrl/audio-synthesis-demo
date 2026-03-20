# 升级变更日志（P0 + P1-E/F）

## P0 实现

### A) 输出对齐产物（segments.json / transcript.vtt）
- **新增**：`audio_alignment.py`：`build_segments`、`write_segments_json`、`write_vtt`
- **修改**：`/api/generate_audio` 完成后，在输出目录写入：
  - `segments.json`：speaker, start_sec, end_sec, text, voice, line_index
  - `transcript.vtt`：WEBVTT 格式
- **响应**：新增 `segments_json_path`、`transcript_vtt_path`
- **位置**：与 mp3/wav 同目录（如 `demo/20250304_120000/`）

### B) SSML 停顿策略
- **新增**：`ssml_builder.py`：`to_ssml(text, lang, pause_profile)`
- **默认**：逗号/分号 80–150ms，句末 250–450ms
- **开关**：`autogate_config.json` → `tts.enable_ssml`（默认 true）

### C) quality_upgrade 校验门
- **集成**：`quality_upgrade/dialogue_quality_validator.py`
- **自动**：从 cast 身份推导 role_mapping（QA/PM/Backend/Ops/Risk/Client）
- **配置**：`quality_upgrade.enabled`、`max_retries`、`strict`
- **调试**：`DEBUG_QUALITY=1` 时写入 `validator_report.md`、`validator_report.json`（与文本同目录）

### D) 核心内容归一化
- **新增**：`core_content_normalizer.py`：`normalize_core_content(core) -> list[str]`
- **规则**：按换行/标点/编号拆成 5–12 条 bullet facts
- **注入**：生成前将 facts 追加到 core 上下文

## P1 实现

### E) V2 默认用于 meeting/review/decision
- **路由**：`classify_scene_type` 在 `it_review` / `promotion_meeting` 或含「评审/决策/决定」时自动启用 V2
- **配置**：`generation.prefer_v2_for_scenes`
- **调试**：`debug_info` 含 `from_v2`、`scene_type`

### F) template_bank 5 步模板（fallback 模式）
- **新增**：`template_retriever.py`：`load_template_bank`、`sample_template_lines`
- **fallback**：非 V2 时优先尝试 5 步模板，若存在则用模板骨架 + core 注入
- **缺失**：无模板时回退到原有结构化生成

## 新增 / 修改文件

| 类型 | 路径 |
|------|------|
| 新增 | `audio_alignment.py` |
| 新增 | `ssml_builder.py` |
| 新增 | `core_content_normalizer.py` |
| 新增 | `template_retriever.py` |
| 修改 | `server.py` |
| 修改 | `.autogate/autogate_config.json` |

## 输出产物位置

```
demo/
  {timestamp}/
    {basename}.txt          # 文本
    {basename}.mp3          # 音频
    segments.json           # 新增：时间戳对齐
    transcript.vtt         # 新增：WEBVTT 字幕
    manifest.json
    validator_report.md     # 仅 DEBUG_QUALITY=1
    validator_report.json   # 仅 DEBUG_QUALITY=1
```

## 验证

1. 生成文本：`POST /api/generate_text`，检查 `debug.param_debug.from_v2`、`scene_type`
2. 生成音频：`POST /api/generate_audio`，确认输出目录有 `segments.json`、`transcript.vtt`
3. SSML：`tts.enable_ssml: false` 可关闭
4. quality_upgrade：`quality_upgrade.enabled: true` 启用
