<!--
  PROJECT_EXPLANATION.md
  自动生成 by generate-demo-docs skill v1.0.0
  生成日期：2026-04-20
  分析目录：D:\Github\audio-synthesis-demo
-->

# audio-synthesis-demo — 项目说明文档

> **文档类型**：项目说明文档（非 README）
> **适合读者**：研发工程师 / 产品经理 / 测试人员 / AI 分析工具
> **生成方式**：由 Claude Code `/generate-docs` 命令自动生成
> **最后更新**：2026-04-20

---

## 1. 项目总览 / Executive Summary

**项目名称**：audio-synthesis-demo（Scene Dialogue Demo）
**一句话定义**：这是一个多语言行业对话音频合成 demo 工具，输入行业场景描述后，由内置 LLM 自动生成多角色对话文本，再通过 Microsoft Edge TTS 合成为有声音频文件，整体以本地 Web 界面交互。

### 核心能力

- **多语言对话生成**：支持中、英、日、韩、法、德、西班牙、葡萄牙、意大利、俄、阿拉伯、印尼、粤语，共 13 种语言
- **行业场景覆盖**：内置 28+ 个行业预置情景（医疗、金融、法律、保险、建筑、AI 科技等），可直接选择或自定义
- **多角色 TTS 音频合成**：每个说话人分配不同音色，并发生成后 ffmpeg 拼接为完整音频（mp3/wav/m4a）
- **长对话分段生成**：超过 5000 字的对话自动切分为多轮 LLM 调用并去重合并，可生成万字级对话
- **few-shot 风格注入**：从本地训练语料库自动选取同行业、同语言示例注入到生成请求，引导 LLM 对齐行业风格
- **文本质量后处理**：生成后自动执行关键词注入、对话质量修复、稳定性约束三道后处理
- **PyInstaller 打包运行**：支持打包为 `.exe` 单文件分发，运行时自动从包内解压模块并热加载
- **嵌入式 Web 服务器**：基于 Tornado 的本地 HTTP 服务，前端 UI 通过 pywebview 嵌入桌面窗口

### 适合谁阅读

| 角色 | 建议阅读章节 | 关注重点 |
|------|------------|---------|
| 研发工程师 | 全文 | 架构设计、模块调用关系、核心算法、TTS 流程 |
| 产品经理 | 章节 1-3 | 功能能力清单、支持语言/行业范围、demo 使用场景 |
| 测试人员 | 章节 2、4、5 | 功能清单、输入输出格式、局限性和风险点 |
| AI 分析工具 | 章节 6-7 | 调用链、数据流、复杂函数解读、隐式约定 |

### 快速理解摘要

这个项目是一个面向 B 端行业对话场景的**音频合成 demo 工具**。用户在浏览器界面中选择行业（如医疗、金融、法律）和使用场景，填写对话参数，点击生成后，后端调用内置 LLM 引擎生成多角色对话文本，再为每个说话人分配一个 TTS 音色，并发合成音频片段，最后用 ffmpeg 拼接成一个完整的有声音频文件下载。整个运行链路完全本地化，不需要外部 AI 服务，可打包为 Windows `.exe` 独立分发。这个工具主要用于向客户/产品/测试人员演示「AI 生成行业对话音频」的能力边界和效果。

---

## 2. 功能清单 / Feature Breakdown

### 核心功能

#### 功能 1：LLM 对话文本生成

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/demo_app/embedded_server_main.py` → `_generate_text_payload()` |
| 功能作用 | 调用内置 bundle LLM 生成 Speaker N: 格式的多角色对话文本 |
| 输入 | JSON：`scenario`（场景描述）、`core_content`（核心内容）、`people_count`（角色数）、`word_count`（目标字数）、`language`（目标语言）、`profile`（角色背景）、`generation_context`（行业+场景类型+讨论轴等结构化参数） |
| 输出 | JSON：`dialogue_text`（完整对话文本）、`lines`（按行解析后的结构化列表）、`dialogue_id`（唯一 ID）、文本文件写入 `demo/{timestamp}/` |
| 适用场景 | 用户在 UI 填写场景后点击"生成文本"按钮 |
| 依赖模块 | `multilingual_naturalness.py`、`few_shot_selector.py`、bundle LLM（从 .exe 解压） |

支持 100~50000 字的字数目标，超过 5000 字自动切换多段拼接模式。

#### 功能 2：TTS 音频合成

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/demo_app/embedded_server_main.py` → `_synthesize_audio_from_lines()` |
| 功能作用 | 为每条对话行分配 TTS 音色，并发合成各段音频，ffmpeg 拼接为完整音频 |
| 输入 | `dialogue_id`（用于查找已生成的对话文本）、`voice_map`（说话人 → 音色映射）、`audio_output_format`（mp3/wav/m4a） |
| 输出 | 音频文件写入 `demo/{timestamp}/{basename}.mp3`（或 .wav/.m4a），manifest.json 同步更新 |
| 适用场景 | 用户在 UI 点击"生成音频"按钮 |
| 依赖模块 | `edge_tts`（Microsoft TTS）、`ffmpeg.exe`（bin/ 目录内置）、`pydub`（探测音频时长） |

并发度：asyncio Semaphore(5)，每段对话行独立合成。音频拼接使用 ffmpeg concat demuxer（磁盘模式），不在内存中累加，避免大文件内存峰值。

#### 功能 3：多语言翻译回退（Latin 语言）

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/demo_app/embedded_server_main.py` → `_translate_dialogue_lines()` |
| 功能作用 | 当 LLM 为法/德/西/葡语请求生成了中文内容（CJK 污染），先用英语生成再翻译为目标语言 |
| 输入 | `lines`（英语对话行列表）、`target_language`（法/德/西/葡语） |
| 输出 | 翻译后的对话行列表（说话人标签保留） |
| 适用场景 | 隐式调用，非 Latin 语言污染时自动触发 |
| 依赖模块 | `deep-translator` → Google Translate API |

#### 功能 4：对话文本质量后处理（三道关卡）

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/demo_app/multilingual_naturalness.py` |
| 功能作用 | 对 LLM 生成的对话文本进行质量修复、关键词注入、稳定性约束 |
| 输入 | `lines`（对话行列表）、`language`、`title`、`keywords`、`generation_context` |
| 输出 | 质量提升后的对话行列表 + 元数据（修复次数、注入关键词数） |
| 适用场景 | 文本生成流水线中自动调用，对用户透明 |
| 依赖模块 | `rule_loader.py`（从 config/ 加载规则 YAML） |

三道后处理：① `repair_dialogue_quality`（修复占位符角色名、删除模板标记等）→ ② `merge_keywords_into_lines`（关键词注入）→ ③ `stabilize_dialogue_constraints`（字数/角色数稳定）

#### 功能 5：Few-shot 风格注入

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/demo_app/few_shot_selector.py` |
| 功能作用 | 从本地训练语料库（`demo/training_long_dialogue/`）中检索同行业同语言对话片段，注入生成 prompt |
| 输入 | `domain`（行业，如"人工智能/科技"）、`language`（如"Chinese"/"Japanese"） |
| 输出 | 一段训练语料中的对话摘录（最多 500 字），无匹配时返回空字符串 |
| 适用场景 | 生成文本前自动调用 |
| 依赖模块 | 本地 `.txt` 训练文件（`demo/training_long_dialogue/`，共 140 个文件，已 gitignore） |

内置语言质量过滤：English 文件排除 CJK 污染，Korean 验证 Hangul 比例，Japanese 验证假名比例，防止错误语言材料污染 prompt。

#### 功能 6：预置场景管理

| 字段 | 说明 |
|------|------|
| 对应脚本 | `src/demo_app/embedded_server_main.py` → `_load_preset_topics()` |
| 功能作用 | 从 `demo/对话情景参数/预置对话情景参数.txt` 解析结构化预置场景，提供给前端下拉选择 |
| 输入 | 本地 txt 文件（特定结构化格式） |
| 输出 | 预置场景列表（含 id、display_title、scenario、core_content、people_count、word_count 等） |
| 适用场景 | 前端加载时初始化下拉列表 |
| 依赖模块 | `config/online_audio_ui.json`（覆盖展示标题）、正则解析（PRESET_BLOCK_RE） |

### 辅助功能

#### 功能 7：对话历史管理（LRU 缓存）

| 字段 | 说明 |
|------|------|
| 对应脚本 | `embedded_server_main.py` → `_ensure_manifest_cache` / `_register_manifest` / `_find_manifest` |
| 功能作用 | 维护最近 500 条对话的 manifest 索引，支持快速 O(1) 查找 |
| 输入 | `dialogue_id`（8 位随机字符串） |
| 输出 | `(manifest_path, manifest_dict)` |
| 依赖模块 | `collections.OrderedDict`（LRU 实现），线程安全（`threading.Lock`） |

#### 功能 8：PyInstaller Bundle 解压与热加载

| 字段 | 说明 |
|------|------|
| 对应脚本 | `embedded_server_main.py` → `_extract_bundle_modules()` / `_extract_static_assets()` |
| 功能作用 | 从打包后的 `.exe` / `.pkg` 中提取 Python 模块和前端静态资源到磁盘缓存，首次解压后复用 |
| 输入 | `build/demo_app/SceneDialogueDemo.exe`（模块包）、`build/DialogDemo/DialogDemo.pkg`（资源包） |
| 输出 | 解压到 `runtime/cache/embedded_bundle/` |
| 依赖模块 | `PyInstaller.archive.readers.CArchiveReader` |

### 工具功能

#### 功能 9：批量训练语料生成

| 字段 | 说明 |
|------|------|
| 对应脚本 | `tools/generation/batch_long_dialogue_training.py` |
| 功能作用 | 批量调用服务器接口，为 14 个行业 × 10 种语言生成 5000 字对话训练文件 |
| 输入 | 运行中的本地服务器（localhost:8899） |
| 输出 | `demo/training_long_dialogue/*.txt`（140 个文件，格式：`{industry}_{lang}_spk{N}_wc5000.txt`） |

#### 功能 10：CI 质量门禁

| 字段 | 说明 |
|------|------|
| 对应脚本 | `scripts/enforce_pre_release_ci_gate.py`、`scripts/enforce_multilingual_quality_gate.py` |
| 功能作用 | 读取测试报告 JSON，验证所有子检查项通过（时效性 + 状态 + 每语言结果），不通过则 CI 失败 |
| 输入 | `reports/pre_release_gate/latest.json`（或指定路径） |
| 输出 | JSON 状态输出到 stdout，返回码 0 = 通过，非 0 = 失败 |

---

## 3. 文件与脚本地图 / Project File Map

```
audio-synthesis-demo/
├── server.py                          ← [主入口] 项目根入口，将 src/ 加入 sys.path 后调用 main()
├── start_demo.bat                     ← [主入口] Windows 一键启动脚本（调用 server.py）
├── src/
│   └── demo_app/
│       ├── embedded_server_main.py    ← [核心逻辑] 全部核心逻辑：HTTP 服务、文本生成、音频合成
│       ├── few_shot_selector.py       ← [核心逻辑] 训练语料检索，为 LLM 提供 few-shot 示例
│       ├── multilingual_naturalness.py← [核心逻辑] 文本质量后处理：修复、关键词注入、稳定约束
│       └── rule_loader.py             ← [工具脚本] 用 lru_cache 加载 config/ 下三个规则 YAML
├── config/
│   ├── app.yaml                       ← [配置文件] 服务器端口(8899)、窗口尺寸、host
│   ├── runtime.yaml                   ← [配置文件] 运行时特性开关（text/audio backend 策略）
│   ├── requirements.txt               ← [配置文件] Python 依赖（tornado/edge-tts/pydub/PyYAML等）
│   ├── paths.yaml                     ← [配置文件] 所有目录路径定义
│   ├── online_audio_ui.json           ← [配置文件] 前端 UI 配置（预置标题覆盖、模板目录等）
│   ├── text_naturalness_rules.yaml    ← [配置文件] 各语言自然度规则（关键词、语气词等）
│   ├── text_postprocess_rules.yaml    ← [配置文件] 文本后处理规则（语言术语替换等）
│   └── text_quality_rules.yaml        ← [配置文件] 文本质量规则（角色约束等）
├── scripts/
│   ├── start_server.py                ← [主入口] 等效入口，scripts/ 目录下的启动脚本
│   ├── enforce_pre_release_ci_gate.py ← [辅助脚本] CI 质量门禁（读报告 JSON，验证各子检查）
│   ├── enforce_multilingual_quality_gate.py← [辅助脚本] 多语言质量门禁
│   ├── auto_pull.py                   ← [辅助脚本] 自动拉取 GitHub 最新代码
│   ├── run_pre_release_ci_gate.py     ← [辅助脚本] 生成 pre-release 报告
│   ├── run_multilingual_quality_checks.py  ← [辅助脚本] 执行多语言质量检查
│   ├── validate_rule_configs.py       ← [辅助脚本] 验证 config/ 下 YAML 规则文件格式
│   └── maintenance/
│       ├── cleanup_workspace.py       ← [工具脚本] 清理历史生成文件
│       ├── clean_logs.py              ← [工具脚本] 清理日志
│       └── project_guard.py           ← [工具脚本] 项目保护（防误操作）
├── tools/
│   ├── generation/
│   │   ├── batch_long_dialogue_training.py← [辅助脚本] 批量生成训练语料（140个文件矩阵）
│   │   ├── batch_generate_audio.py        ← [辅助脚本] 批量生成多行业对话音频
│   │   └── run_training_pipeline.py       ← [辅助脚本] 完整训练流水线入口
│   ├── analysis/
│   │   ├── analyze_jobs.py            ← [辅助脚本] 分析批量任务结果
│   │   └── verify_integrity.py        ← [辅助脚本] 验证生成结果完整性
│   └── validation/
│       └── validate_generated.py      ← [辅助脚本] 验证生成文件格式
├── training/
│   ├── build_template_bank.py         ← [辅助脚本] 从训练输出提取可复用对话模板
│   ├── dialogue_validators.py         ← [辅助脚本] 对话格式校验器
│   ├── role_cards.py                  ← [数据/样例] 行业角色卡片定义
│   ├── scenario_bank.py               ← [数据/样例] 行业场景库
│   └── run_training_generation_mvp.py ← [辅助脚本] MVP 阶段训练生成入口
├── tests/                             ← [测试] 共 20 个测试文件
│   ├── test_server_refactor.py        ← [测试] 服务器 HTTP 接口回归测试
│   ├── test_rule_loader.py            ← [测试] 规则加载单元测试
│   ├── test_multilingual_naturalness.py← [测试] 多语言自然度处理单元测试
│   └── ...（其他略）
├── bin/
│   └── ffmpeg.exe                     ← [数据/样例] 内置 ffmpeg，音频合成必需（526KB）
├── build/
│   ├── demo_app/SceneDialogueDemo.exe ← [数据/样例] PyInstaller 打包的主程序（含 LLM bundle）
│   ├── DialogDemo/DialogDemo.pkg      ← [数据/样例] 前端静态资源包
│   ├── build_win.ps1                  ← [辅助脚本] Windows 打包脚本
│   └── build_mac.sh                   ← [辅助脚本] macOS 打包脚本
├── .github/
│   └── workflows/
│       ├── ci.yml                     ← [配置文件] GitHub Actions CI：pytest + 质量门禁
│       ├── pre-release-gate.yml       ← [配置文件] Pre-release 门禁 workflow
│       └── project-reminder.yml       ← [配置文件] 项目提醒 workflow
├── skills/generate-demo-docs/         ← [文档] Claude Code 文档生成技能包
├── TTS_UPGRADE_GUIDE.md               ← [文档] TTS 升级方案说明（Kokoro-82M / SiliconFlow）
└── PROJECT_EXPLANATION.md             ← [文档] 本文档
```

**关键文件快速索引**：

| 文件 | 标签 | 一句话用途 |
|------|------|-----------|
| `server.py` | 主入口 | 项目根目录启动入口 |
| `src/demo_app/embedded_server_main.py` | 核心逻辑 | 全部业务逻辑的实现（2000+行） |
| `src/demo_app/few_shot_selector.py` | 核心逻辑 | 训练语料检索，影响生成质量 |
| `src/demo_app/multilingual_naturalness.py` | 核心逻辑 | 文本质量后处理的三道关卡 |
| `src/demo_app/rule_loader.py` | 工具脚本 | config/ 规则文件的缓存加载器 |
| `config/requirements.txt` | 配置文件 | Python 依赖声明 |
| `config/app.yaml` | 配置文件 | 服务端口和 GUI 配置 |
| `bin/ffmpeg.exe` | 数据/样例 | 音频合成的关键依赖，内置在项目中 |

---

## 4. 脚本能力说明 / What Each Script Can Do

### `server.py` ⭐ 主入口

**这个脚本是干什么的**

项目的根入口文件。它做的事情极其简单：将 `src/` 目录加入 Python 路径，然后把 `src/demo_app/embedded_server_main.py` 中的所有内容导入，最后调用 `main()` 函数启动整个应用。

本身没有任何业务逻辑，纯粹是一个路径桥接层，让开发者可以在项目根目录直接运行 `python server.py` 而不需要手动设置 `PYTHONPATH`。

**如何调用**

```bash
# 方式一：直接启动服务器（开发模式）
python server.py

# 方式二：通过 start_demo.bat（Windows）
start_demo.bat

# 方式三：通过 scripts/start_server.py
python scripts/start_server.py
```

**成功运行后会产生什么**

- 启动本地 HTTP 服务器，监听 `127.0.0.1:8899`（端口见 `config/app.yaml`）
- 打开 pywebview 桌面窗口，嵌入 Web UI（标题："Scene Dialogue Demo"）
- 控制台输出可访问的本地 URL 列表

---

### `src/demo_app/embedded_server_main.py` ⭐ 核心逻辑

**这个脚本是干什么的**

整个项目的大脑。这一个文件承担了所有核心工作：
- 启动 Tornado HTTP 服务器，暴露 `/api/*` 接口给前端调用
- 管理 PyInstaller bundle 的解压和热加载（首次运行时从 .exe 提取模块）
- 调用 bundle 内置的 LLM 引擎生成对话文本
- 调用 edge_tts 并发合成多段音频，再调用 ffmpeg 拼接
- 维护对话历史 LRU 缓存（最多 500 条）
- 处理预置场景加载、对话编辑保存、对话删除等所有 HTTP 请求

**它可以完成哪些事情**

- **生成对话文本**：接收结构化参数 → 调用 LLM → 后处理 → 保存 txt + manifest.json
- **合成音频**：读取已生成的对话文本 → TTS → ffmpeg 拼接 → 保存 mp3/wav/m4a
- **对话编辑**：接收用户编辑后的文本 → 重新解析行结构 → 更新 manifest
- **对话删除**：从 demo/ 目录删除整个时间戳子目录
- **历史查询**：通过 `dialogue_id` 快速查找已生成的对话
- **预置场景**：解析 txt 文件，提供结构化预置列表给前端

**如何调用（HTTP API）**

```bash
# 生成文本
POST http://127.0.0.1:8899/api/generate_text
Content-Type: application/json
{
  "scenario": "医生与慢病患者进行随访",
  "core_content": "讨论血压控制情况",
  "people_count": 2,
  "word_count": 1000,
  "audio_language": "Chinese",
  "profile": {"job_function": "医疗健康", "work_content": "慢病随访", "seniority": "资深", "use_case": "医疗健康｜医疗咨询"}
}

# 合成音频
POST http://127.0.0.1:8899/api/synthesize_audio
{
  "dialogue_id": "abc12345",
  "voice_map": {"1": "zh-CN-YunxiNeural", "2": "zh-CN-XiaoxiaoNeural"},
  "audio_output_format": "mp3"
}
```

**成功运行后会产生什么**

文本生成：`demo/{timestamp}/{basename}.txt` + `demo/{timestamp}/manifest.json`
音频合成：`demo/{timestamp}/{basename}.mp3`（或 .wav/.m4a）

**注意事项**

- 首次运行需要 `build/demo_app/SceneDialogueDemo.exe` 存在，否则无法加载 LLM 模块（bundle LLM）
- 音频合成需要 `bin/ffmpeg.exe` 存在
- 如果 bundle 未解压，脚本会自动解压到 `runtime/cache/embedded_bundle/`，首次约需 10-30 秒

---

### `src/demo_app/few_shot_selector.py` ⭐ 核心逻辑

**这个脚本是干什么的**

从本地训练语料库中检索与当前请求同行业、同语言的对话片段，注入到生成 prompt 中，引导 LLM 生成更贴合行业风格的对话。

**它可以完成哪些事情**

- 根据 domain（行业）× language 找到对应训练文件
- 随机从文件中采样一段不重复的对话摘录（最多 500 字）
- 对语言质量进行过滤（防止跨语言污染）
- 使用 LRU 内存缓存（32 文件上限）避免重复磁盘读取

**如何调用**

```python
from demo_app.few_shot_selector import get_few_shot_example

# 获取"人工智能/科技"行业的中文 few-shot 示例
excerpt = get_few_shot_example(domain="人工智能/科技", language="Chinese")
# 返回值：一段 Speaker N: 格式的对话文本，或 ""（无匹配时）
```

**注意事项**

- 训练文件位于 `demo/training_long_dialogue/`，被 gitignore，需要本地生成（用 `tools/generation/batch_long_dialogue_training.py`）
- 支持的 domain：14 个行业；支持的 language：9 种（中/英/日/韩/法/德/西/葡/粤）
- 无匹配文件时静默返回 `""`，不影响主流程

---

### `src/demo_app/multilingual_naturalness.py` ⭐ 核心逻辑

**这个脚本是干什么的**

对话文本的后处理工厂。LLM 生成的原始文本质量参差不齐，这个模块负责在合成音频前对文本进行三道加工：修复质量问题、注入关键词、稳定约束。

**它可以完成哪些事情**

- **`repair_dialogue_quality()`**：修复 LLM 生成的问题（占位符角色名如 "Professional" → 真实名字，删除 `<<Core:...>>` 模板标记，修复与场景不符的对话内容）
- **`merge_keywords_into_lines()`**（对应 `enforce_keywords_in_lines`）：将用户指定的关键词自然地插入对话中合适的位置
- **`stabilize_dialogue_constraints()`**：当实际字数或角色数与目标不符时，额外调整稳定
- **`polish_generated_lines()`**：语言自然度优化（根据 `text_naturalness_rules.yaml` 的语言规则）

**注意事项**

- 依赖 `rule_loader.py` 加载 YAML 规则，规则文件变更后需重启生效（`lru_cache` 缓存）
- 内置多语言角色名池（中文医生名、患者名、商务人士名），根据场景关键词自动选择合适名字替换占位符

---

### `src/demo_app/rule_loader.py` 工具脚本

**这个脚本是干什么的**

配置规则文件的加载器，用 `@lru_cache(maxsize=1)` 确保三个 YAML 规则文件只在进程生命周期内读取一次。

**关键函数**

- `load_text_postprocess_rules()` → `config/text_postprocess_rules.yaml`（语言术语替换规则）
- `load_text_quality_rules()` → `config/text_quality_rules.yaml`（角色约束规则）
- `load_text_naturalness_rules()` → `config/text_naturalness_rules.yaml`（各语言自然度规则）
- `clear_rule_cache()` → 清空三个缓存（供测试使用）

**注意事项**：运行时修改 YAML 文件不会自动生效，需调用 `clear_rule_cache()` 或重启服务器。

---

### `scripts/enforce_pre_release_ci_gate.py` 辅助脚本

**这个脚本是干什么的**

CI 流水线中的质量门禁执行器。从 `reports/pre_release_gate/latest.json` 读取测试报告，逐项验证是否全部通过，不通过则以非零退出码让 CI 失败。

**如何调用**

```bash
python scripts/enforce_pre_release_ci_gate.py
python scripts/enforce_pre_release_ci_gate.py --report reports/pre_release_gate/latest.json --max-age-hours 24
```

**验证项目**：报告时效性（默认 24 小时内）、`required_paths`、`yaml_parse`、`python_compile`、`repo_daily_check`、`multilingual_quality_check`、`embedded_demo_smoke`。

**注意事项**：若 report 文件不存在，输出 `status: skipped` 并返回 0（不让 CI 失败），适用于纯配置变更的 PR。

---

### `tools/generation/batch_long_dialogue_training.py` 辅助脚本

**这个脚本是干什么的**

批量生成训练语料的自动化脚本。向运行中的本地服务器发出 HTTP 请求，生成 14 行业 × 10 语言 × 1 字数档（5000字）= 140 个训练文件，保存为 `.txt` 格式供 `few_shot_selector.py` 使用。

**如何调用**

```bash
# 先启动服务器
python server.py

# 新终端运行批量生成
python tools/generation/batch_long_dialogue_training.py
```

**注意事项**：生成 140 个文件需要较长时间（每文件约 30-60 秒 LLM 推理），总计约 2-4 小时。生成结果保存在 `demo/training_long_dialogue/`（gitignore，本地保留）。

---

## 5. 优缺点分析 / Strengths and Limitations

### 整体项目评估

#### 优点

- **端到端闭环**：从场景描述到可下载音频，完整流程本地化，无需外部 AI 服务
- **行业覆盖广**：内置 28 个行业预置场景，支持 13 种语言的 TTS，覆盖面好
- **质量有保障**：三道后处理（修复→关键词注入→稳定约束）显著提升 LLM 输出质量
- **内存优化**：LRU 缓存（manifest 500 条上限、训练文件 32 条上限）、ffmpeg 磁盘拼接避免音频内存积累
- **可独立分发**：支持 PyInstaller 打包为 `.exe`，零依赖安装
- **CI 体系完善**：pre-release 门禁、多语言质量检查、自动化测试覆盖关键路径

#### 局限性

- **TTS 质量一般**：当前使用 edge_tts（Microsoft Neural TTS），没有真实情绪控制，声音表达层次不够丰富（详见 `TTS_UPGRADE_GUIDE.md`）
- **LLM 在 bundle 内**：核心 LLM 引擎被打包在 `build/demo_app/SceneDialogueDemo.exe` 内，无法从源码直接理解其能力和限制，形成黑盒依赖
- **训练语料不入 git**：`demo/training_long_dialogue/` 被 gitignore，新环境需重新批量生成，冷启动成本高
- **Latin 语言质量**：法/德/西/葡语采用"英语生成→Google Translate 翻译"的 fallback，翻译质量有损耗，且依赖网络
- **长对话去重粗糙**：多段拼接时仅按文本完全相等去重，相似句子不会被过滤

#### 潜在风险

- **ffmpeg.exe 绑定**（风险等级：中）：音频合成硬依赖 `bin/ffmpeg.exe`，跨 OS 运行（macOS/Linux）需替换二进制
- **网络依赖**（风险等级：低-中）：Latin 语言回退翻译依赖 Google Translate 网络访问，在无网络或 Google 不可达的环境中降级为英语
- **demo/ 目录积累**（风险等级：低）：每次生成都写入 `demo/{timestamp}/`，长时间运行后磁盘占用会累积，没有自动清理机制
- **bundle LLM 版本锁定**（风险等级：中）：LLM 能力受限于 `.exe` 内的固定版本，无法在不重新打包的情况下升级

#### 可维护性

⭐⭐⭐☆☆（3/5）

`embedded_server_main.py` 承担了过多职责（HTTP 服务 + TTS + 文本处理 + Bundle 管理），单文件超过 2000 行，修改一个功能容易牵连其他。其他模块（`few_shot_selector.py`、`rule_loader.py`、`multilingual_naturalness.py`）拆分合理，可维护性较好。

#### 可扩展性

⭐⭐⭐⭐☆（4/5）

语言和行业的扩展只需修改 `VOICE_CATALOG`、`_DOMAIN_TO_ID`、`_LANG_TO_SHORT` 等映射字典，不需要改核心逻辑。TTS 引擎替换（见 `TTS_UPGRADE_GUIDE.md`）主要集中在 `_synthesize_audio_from_lines()` 一个函数，影响范围可控。

#### 最值得重构的地方

1. **`embedded_server_main.py`（职责分离）**：将 HTTP Handler 类、TTS 逻辑、Bundle 管理、Manifest 缓存各自拆分为独立模块，降低单文件复杂度
2. **`_synthesize_audio_from_lines()`（TTS 引擎抽象）**：用 Protocol/ABC 定义 TTS 接口，让 edge_tts、Kokoro、SiliconFlow 可插拔替换
3. **demo/ 目录清理**：增加定时清理或按配置保留最近 N 天的机制

---

## 6. 内部调用与实现逻辑 / Internal Flow and Call Graph

### 主流程步骤（文本生成 + 音频合成）

```
Step 1: 用户触发
  └─ 访问 http://127.0.0.1:8899/，在 Web UI 填写场景参数

Step 2: 服务器启动（main() 函数）
  └─ 检查 bundle 缓存是否新鲜（_cache_is_fresh()）
  └─ 不新鲜 → _extract_bundle_modules() + _extract_static_assets()
  └─ importlib 动态加载 bundle 模块（app.pyc / server.pyc 等）
  └─ 初始化 Tornado Application + 绑定端口 8899
  └─ 启动 pywebview 桌面窗口

Step 3: 文本生成请求（POST /api/generate_text）
  └─ 参数净化：_safe_profile() + _safe_generation_context()
  └─ 语言规范化：_canonical_language()
  └─ 非中文语言：_sanitize_profile_for_language()（中→英翻译字段）
  └─ Few-shot 注入：get_few_shot_example(domain, language)
  └─ LLM 调用：_generate_long_dialogue_lines()
       ├─ [≤5000字] 单次调用 bundle_server._generate_dialogue_lines()
       └─ [>5000字] 循环分段调用，去重累积至字数达标
  └─ Latin 语言 CJK 检测 → 触发翻译回退（可选）
  └─ 三道后处理：
       1. repair_dialogue_quality() [multilingual_naturalness.py]
       2. merge_keywords_into_lines() [multilingual_naturalness.py]
       3. stabilize_dialogue_constraints() [multilingual_naturalness.py]
  └─ 写文件：demo/{timestamp}/{basename}.txt + manifest.json
  └─ 注册缓存：_register_manifest()
  └─ 返回 JSON 响应（含 dialogue_id + dialogue_text + lines）

Step 4: 音频合成请求（POST /api/synthesize_audio）
  └─ 查缓存：_find_manifest(dialogue_id)
  └─ 读对话文本，解析为行列表
  └─ _synthesize_audio_from_lines()
       ├─ 为每行分配 TTS 音色（_voice_for_speaker()）
       ├─ asyncio.gather（Semaphore=5）并发合成各行音频片段
       │    └─ 每行：edge_tts.Communicate.save() → 临时 .mp3 文件
       ├─ 探测每段时长（pydub.AudioSegment，读后立即释放）
       ├─ 写 ffmpeg concat list 文件（.concat_list.txt）
       └─ subprocess.run(ffmpeg -f concat ...) 拼接为最终文件
  └─ 更新 manifest.json（audio_path + 时长信息）
  └─ 返回 JSON 响应（含 audio_download_url）
```

### 调用链（简化版）

```
main()
  └─ _cache_is_fresh()
  └─ _extract_bundle_modules()  [CArchiveReader → runtime/cache/]
  └─ _extract_static_assets()   [CArchiveReader → runtime/cache/]
  └─ importlib.util.spec_from_file_location() × N  [加载 bundle 模块]
  └─ tornado.web.Application([...handlers])
  └─ BundleServer（来自 bundle 模块）

TextHandler.post() → _generate_text_payload()
  └─ get_few_shot_example()          [few_shot_selector.py]
       └─ _read_training_file()      [LRU 文件缓存]
  └─ _generate_long_dialogue_lines()
       └─ bundle_server._generate_dialogue_lines()  [bundle LLM，黑盒]
  └─ repair_dialogue_quality()       [multilingual_naturalness.py]
       └─ load_text_quality_rules()  [rule_loader.py → YAML]
  └─ merge_keywords_into_lines()     [multilingual_naturalness.py]
       └─ load_text_naturalness_rules()  [rule_loader.py → YAML]
  └─ stabilize_dialogue_constraints() [multilingual_naturalness.py]
  └─ _register_manifest()            [OrderedDict LRU]

AudioHandler.post() → _synthesize_audio_from_lines()
  └─ _voice_for_speaker()            [VOICE_CATALOG 查表]
  └─ asyncio.gather(Semaphore(5))
       └─ edge_tts.Communicate.save() × N  [HTTP → Microsoft TTS]
  └─ pydub.AudioSegment.from_file() [探测时长，即读即弃]
  └─ subprocess.run([ffmpeg, -f, concat, ...])  [子进程]
  └─ _manifest_cache 更新
```

### 数据流

```
用户输入（JSON）
  ↓ 参数净化 + 语言规范化
结构化参数（profile + scenario + core_content + 语言）
  ↓ Few-shot 注入
enriched core_content（含行业示例文本）
  ↓ bundle LLM 推理
raw_lines：list[tuple[str, str]]（speaker, text 对）
  ↓ 三道后处理
quality_lines：list[tuple[str, str]]（质量提升）
  ↓ 渲染为文本
dialogue_text：str（Speaker N: 格式）
  ↓ 写文件到 demo/{timestamp}/
  ↓ TTS 合成（每行 → 临时音频片段）
segments：list[Path]（临时 .mp3 文件）
  ↓ ffmpeg concat
final_audio：Path（最终 .mp3/.wav/.m4a）
```

### 外部资源调用

| 资源类型 | 资源名称 | 调用位置 | 说明 |
|---------|---------|---------|------|
| HTTP | Microsoft TTS（edge_tts） | `_synthesize_audio_from_lines()` | 每行对话独立调用，并发 5 |
| HTTP | Google Translate（deep_translator） | `_translate_dialogue_lines()` | 仅 Latin 语言 CJK 回退时调用 |
| 子进程 | `bin/ffmpeg.exe` | `_synthesize_audio_from_lines()` | 音频拼接，timeout=300s |
| 文件系统 | `demo/{timestamp}/` | 文本生成、音频合成 | 读写对话文本和音频文件 |
| 文件系统 | `runtime/cache/embedded_bundle/` | 服务启动时 | 读写 bundle 解压缓存 |
| 文件系统 | `demo/training_long_dialogue/` | `few_shot_selector.py` | 只读训练语料 |

---

## 7. 复杂脚本深度解读 / Deep Technical Notes for AI and Maintainers

### `src/demo_app/embedded_server_main.py` — 深度解读

#### 模块概述

整个应用的单体核心，2000+ 行，承担了 Web 服务器、LLM 调用编排、TTS 合成流水线、Bundle 提取、Manifest 缓存管理五大职责。这种设计来自早期快速原型阶段，适合 demo 场景但对长期维护有挑战。

#### 全局状态清单

| 变量 | 类型 | 用途 | 特别说明 |
|------|------|------|---------|
| `_BUNDLE_SERVER` | `Any \| None` | bundle 内 BundleServer 实例 | 只初始化一次，跨请求共享 |
| `_manifest_cache` | `OrderedDict[str, tuple]` | LRU 对话索引缓存 | 上限 500 条，线程安全（Lock） |
| `_manifest_cache_loaded` | `bool` | 首次加载标志 | 双重检查锁定（DCL）模式 |
| `_manifest_cache_lock` | `threading.Lock` | 缓存并发保护 | 读写都要加锁 |
| `_ONLINE_AUDIO_CONFIG_CACHE` | `dict \| None` | UI 配置缓存 | 进程内不刷新 |
| `_PRESET_TOPICS_CACHE` | `list \| None` | 预置场景缓存 | 进程内不刷新 |

⚠️ **边界条件**：`_manifest_cache` 在多线程环境下，读操作也需要加锁（因为 `move_to_end` 会修改 OrderedDict 内部结构）。当前实现已正确处理。

#### 关键函数说明

##### `_synthesize_audio_from_lines(bundle_server, lines, voice_map, save_dir, basename, output_format)`

- **职责**：TTS 合成主函数，从对话行列表出发，最终产出一个完整的音频文件
- **参数**：
  - `lines`：`list[tuple[str, str]]`，`(speaker_label, text)` 对，如 `("Speaker 1", "你好")`
  - `voice_map`：`dict[str, str]`，说话人编号 → edge_tts 音色名，如 `{"1": "zh-CN-YunxiNeural"}`
  - `save_dir`：`Path`，保存目录（如 `demo/20260420_123456/`）
  - `basename`：`str`，文件名前缀
  - `output_format`：`str`，`"mp3"` / `"wav"` / `"m4a"`
- **副作用**：
  - 在 `save_dir/` 下创建大量临时音频片段文件（命名 `seg_{i:04d}.mp3`）
  - 创建 `.concat_list.txt` 临时文件
  - 上述临时文件在 ffmpeg 拼接完成后被清理（try/finally）
  - 最终音频文件写入 `save_dir/{basename}.{format}`
- **调用关系**：被 `AudioHandler.post()` 调用；内部调用 `edge_tts.Communicate`、`pydub.AudioSegment`（仅探测时长）、`subprocess.run(ffmpeg)`

##### `_generate_long_dialogue_lines(bundle_server, profile, scenario, core_content, people_count, total_target, language)`

- **职责**：LLM 调用调度器。≤5000字单次调用，>5000字多段循环拼接并去重
- **去重逻辑**：`seen_texts: set[str]` 记录已出现的每行文本，完全相同才去重（相似不去重）
- **无限循环保护**：连续 3 次调用均无新增行时退出（LLM 陷入重复），避免死循环
- **返回值**：`(lines, rewrite_info)` 元组，`rewrite_info` 是 bundle LLM 返回的元数据字典

##### `_ensure_manifest_cache()` + `_register_manifest()` + `_find_manifest()`

这三个函数共同实现 LRU 对话缓存：

- **`_ensure_manifest_cache()`**：惰性初始化。首次调用时扫描 `demo/` 目录，加载最近 500 个 manifest.json，按修改时间倒序，用双重检查锁定（DCL）保证线程安全
- **`_register_manifest()`**：新对话生成后注册，调用 `move_to_end(dialogue_id)` 标记为最新，超出 500 条时从头部 `popitem` 弹出最旧条目
- **`_find_manifest()`**：O(1) 查找，命中时 `move_to_end` 保持 LRU 顺序，文件被删除时自动从缓存中驱逐

##### `_extract_bundle_modules(archive_path, dest_dir, selected_modules)` 和 `_extract_static_assets(pkg_path, dest_dir)`

- **职责**：从 PyInstaller 生成的 `.exe` / `.pkg` 归档中提取 Python 模块（`.pyc`）和前端静态文件
- **实现细节**：使用 `CArchiveReader`（PyInstaller 内部 API）遍历归档内容。Python 模块项类型为 `PYZ_ITEM_MODULE` 或 `PYZ_ITEM_PKG`，提取后写为 `.pyc` 文件（带时间戳 magic header，用 `_code_to_timestamp_pyc` 生成）
- **⚠️ 资源释放**：`CArchiveReader` 实例必须 `close()`，否则会持有文件句柄。当前实现用 `try/finally` + `hasattr(reader, 'close')` 保护，防止不同 PyInstaller 版本的兼容性问题

#### 核心算法 / TTS 合成流程

```
1. 解析对话行：将 "Speaker N: text" 格式解析为 (speaker, text) 元组列表
2. 分配音色：每个 speaker_id 通过 VOICE_CATALOG 查表得到 edge_tts 音色名
3. 并发合成（asyncio + Semaphore(5)）：
   - 为每行创建 Communicate(text, voice=...) 对象
   - await comm.save(temp_path) → 写临时 .mp3 文件
   - 所有行同时最多 5 个并发（避免对 Microsoft TTS 造成过大压力）
4. 探测时长（pydub）：
   - AudioSegment.from_file(seg_path) → 读取时长
   - del _probe（立即释放，避免大量音频驻内存）
5. 写 ffmpeg concat 列表：
   file 'seg_0001.mp3'
   file 'seg_0002.mp3'
   ...
6. 调用 ffmpeg：
   ffmpeg -y -f concat -safe 0 -i .concat_list.txt {codec_args} output.mp3
   - timeout=300s（5 分钟保护）
   - capture_output=True（日志不打印到控制台）
7. 清理临时文件（try/finally）
```

#### 容易看不懂的代码段

##### 代码段 1：`_code_to_timestamp_pyc` 的使用

**位置**：`_extract_bundle_modules()` 内，写 `.pyc` 文件时

**意图**：Python 的 `.pyc` 文件有一个 magic header，包含 Python 版本标识和时间戳。`importlib._bootstrap_external._code_to_timestamp_pyc()` 是 CPython 内部函数，用于将已有的 code object 包装成带正确 magic header 的字节序列。这么做是因为 PyInstaller 归档里存的是裸 code object，直接写到磁盘需要加这个头才能被 `importlib` 正确加载。

**为什么用内部 API**：Python 标准库没有公开这个函数，这是 PyInstaller 生态常见的"必要的 hack"。

##### 代码段 2：`_translate_dialogue_lines()` 的说话人标签规范化

**位置**：翻译后处理，正则 `re.sub(r"^[A-Za-z\xc0-\xff\-\s\xa0]+?\s*(\d+)\s*[\xa0\s]*[:\uff1a]\s*", r"Speaker \1: ", ...)`

**意图**：Google Translate 会把 "Speaker 1:" 翻译成目标语言的等价词（如法语 "Haut-parleur 1 :"、德语 "Sprecher 1:"），这个正则负责把所有这些变体规范化回统一的 "Speaker N:" 格式，以便后续的行解析能正确识别。字符类 `\xc0-\xff` 覆盖拉丁扩展字符（法语的 é、à 等），`\xa0` 是不换行空格（Google Translate 有时会插入）。

##### 代码段 3：Bundle LRU 缓存的双重检查锁定（DCL）

```python
def _ensure_manifest_cache() -> None:
    global _manifest_cache_loaded
    if _manifest_cache_loaded:      # 第一次检查（无锁，快路径）
        return
    with _manifest_cache_lock:
        if _manifest_cache_loaded:  # 第二次检查（有锁，防并发重复初始化）
            return
        # ... 实际加载逻辑
        _manifest_cache_loaded = True
```

**意图**：第一次检查（无锁）是为了在已初始化后的快路径上避免加锁开销（锁有 CPU 代价）。第二次检查（有锁）是为了防止两个线程同时通过第一次检查后都去初始化。这是经典的双重检查锁定模式（DCL）。在 Python GIL 下这是安全的，但即使没有 GIL 也是正确的（锁保证了内存可见性）。

#### 隐式约定与假设

- **路径约定**：所有路径都以 `ROOT = Path(__file__).resolve().parents[2]` 为基准，即项目根目录。无论从哪里运行脚本，路径都能正确解析
- **Demo 目录格式**：每次生成对话创建 `demo/{timestamp}/` 子目录，`timestamp` 格式固定为 `%Y%m%d_%H%M%S`（如 `20260420_123456`）
- **Manifest 结构**：`manifest.json` 中的 `dialogue_id` 是系统唯一标识符（8位小写字母数字），`save_dir` 字段必须存在且指向 `demo/` 内（强制验证，越界会 HTTP 400）
- **线程安全**：`_manifest_cache` 的读写均在 `_manifest_cache_lock` 下进行，包括 `move_to_end()`（这很重要，OrderedDict 的 `move_to_end` 不是线程安全的）
- **临时文件命名**：TTS 段命名为 `seg_{i:04d}.mp3`，i 从 0 开始。concat list 命名为 `.concat_list.txt`（点开头，避免与音频文件混淆）
- **bundle LLM 接口约定**：`bundle_server._generate_dialogue_lines(profile, scenario, core_content, people_count, word_count, language)` 返回 `(lines, rewrite_info)` 元组。这个接口来自 bundle 模块，属于黑盒约定，不得擅自修改调用签名

#### 维护者建议

1. **修改 TTS 逻辑前**：必须理解 ffmpeg concat demuxer 格式（`-f concat -safe 0`），以及 `safe 0` 的含义（允许绝对路径）。修改后，用 20+ 行对话测试内存峰值和临时文件清理
2. **修改 manifest 缓存**：任何改动都要考虑线程安全。`OrderedDict` 的迭代和修改不能交叉
3. **修改 bundle 提取**：`CArchiveReader` 是 PyInstaller 内部 API，版本升级可能导致接口变化。目前用 `hasattr` 检查 `.close()`，保持这个防御性写法
4. **扩展新语言 TTS**：只需在 `VOICE_CATALOG` 中添加新语言的音色列表，在 `_canonical_language()` 的映射中添加别名，在 `few_shot_selector.py` 的 `_LANG_TO_SHORT` 中添加语言代码
5. **扩展新行业**：在 `few_shot_selector.py` 的 `_DOMAIN_TO_ID` 中添加映射，然后生成对应的训练语料文件

---

### `src/demo_app/few_shot_selector.py` — 深度解读

#### 关键算法：语言质量过滤

训练文件可能存在语言污染（如英语文件里混入了中文，日语文件没有假名）。当前过滤策略：

| 语言 | 检测方法 | 阈值 | 说明 |
|------|---------|------|------|
| English | `_cjk_ratio()` | ≤ 5% CJK | CJK 超过 5% 则视为中文污染文件，跳过 |
| Korean | `_hangul_ratio()` | ≥ 8% Hangul | 韩语文件必须有足够比例的韩文字符 |
| Japanese | kana 比例 | ≥ 5% kana | 日语文件必须有假名（平假名/片假名），纯汉字=中文污染 |
| French/German/Spanish等 | 不过滤 | N/A | 拉丁字母语言文件不做 CJK 检测 |

**隐式约定**：仅检查文件前 2000 字符的语言分布，假设文件整体语言一致。

#### `_extract_excerpt()` 的采样逻辑

- 跳过文件前 20%（避免总是取开头的客套对话）
- 从跳过后的位置随机选一个起点
- 对每行去除 "Speaker N:" 前缀后提取内容，内容相同的行跳过（去重）
- 累计字符数超过 500 时截止
- 过滤掉包含 `<<` 或 `>>` 的行（防止模板标记泄漏进 prompt）

---

### `src/demo_app/multilingual_naturalness.py` — 深度解读

#### 模块概述

这个模块的核心是"让 AI 生成的对话听起来更像真人说的话"。它不改变对话的主题内容，但会：修复明显的 AI 生成痕迹（占位符角色名、模板标记）、注入用户指定的关键词、验证字数和角色数是否符合要求。

#### 关键设计：`_ROLE_SPECIFIC_PACKS`

这是一个多元组列表，每个元素包含：
- `trigger_keywords`：触发条件（对话 scenario/core_content 包含这些词时激活）
- `facts`：这个场景中应该出现的事实性话题
- `risks`：这个场景中应该提到的风险点
- `outputs`：这个场景中应该产出的交付物

**意图**：当 LLM 生成的内容缺乏行业专业性时，后处理函数可以参考这些预设的专业词汇和话题进行增补。这是领域知识的显式编码，而不是依赖 LLM 自发生成。

#### 隐式约定

- **函数调用顺序**：必须先 `repair_dialogue_quality`，再 `merge_keywords_into_lines`，最后 `stabilize_dialogue_constraints`。顺序不能乱，因为前一道的输出是后一道的输入
- **`load_text_naturalness_rules()` 是进程级缓存**：规则文件修改后需要重启或调用 `clear_rule_cache()` 才生效

---

*文档由 generate-demo-docs skill v1.0.0 自动生成*
*生成时间：2026-04-20*
*分析文件数：23 个核心文件*
*主入口：`server.py`、`start_demo.bat`、`scripts/start_server.py`（三个等效入口）*
*如发现文档有误或信息过时，请重新运行 `/generate-docs` 更新*
