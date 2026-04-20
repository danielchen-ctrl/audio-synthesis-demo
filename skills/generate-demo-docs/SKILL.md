# Skill: generate-demo-docs

**版本**：1.0.0  
**作者**：daniel.chen@plaud.ai  
**创建日期**：2026-04-20  
**许可证**：MIT

---

## 技能定义

**名称**：`generate-demo-docs`  
**斜杠命令**：`/generate-docs`

### 触发场景

在以下情况下使用此技能：

- 用户说"**生成说明文档**"、"**帮我生成一份demo说明文档**"或"**说明文档**"
- 用户希望为 demo 项目、脚本集合、原型代码、功能验证项目生成系统说明文档
- 用户需要把项目结构、脚本功能、调用关系、复杂实现解释整理成文档
- 用户需要给 AI 准备高质量项目说明材料（用于后续让 AI 分析或改造代码）
- 用户刚写完一批脚本，没有任何文档，需要从零生成
- 用户要把项目交接给他人，需要一份完整说明

### 不适用场景

- 生成简单 README（用户只需要安装步骤 → 写普通 README 即可）
- 生成 API 文档（应使用专门的 API doc 工具）
- 生成 changelog 或 release notes

---

## 技能目标

> 自动为用户的各种 demo 脚本项目生成**非常详细、层次清晰、可给人看也可给 AI 读**的说明文档。

### 设计原则

| 原则 | 说明 |
|------|------|
| **先总后分** | 总览在最前，技术细节在最后 |
| **解释 > 复制** | 不堆代码，解释意图 |
| **人话优先** | 白话文解释，再讲技术实现 |
| **标注不确定** | 无法确认的内容写"推测用途" |
| **AI 可读** | 结构化表达，适合后续 AI 分析 |

---

## 输出文档结构（必须按此顺序）

```
PROJECT_EXPLANATION.md
├── 1. 项目总览 / Executive Summary          ← 首屏，1分钟内看懂
├── 2. 功能清单 / Feature Breakdown          ← 所有主要功能，按类别分组
├── 3. 文件与脚本地图 / Project File Map     ← 树状结构 + 每文件一句注释
├── 4. 脚本能力说明 / What Each Script Can Do ← 每个脚本的详细能力说明（带示例）
├── 5. 优缺点分析 / Strengths and Limitations ← 客观评估，包含技术债说明
├── 6. 内部调用与实现逻辑 / Internal Flow    ← 调用链 + 数据流
└── 7. 复杂脚本深度解读 / Deep Technical Notes ← AI 可读的技术细节
```

---

## 参考材料（`references/` 目录）

| 文件 | 用途 |
|------|------|
| `doc_template.md` | 完整文档骨架模板 |
| `analysis_rules.md` | 脚本分析优先级规则 |
| `entrypoint_detection.md` | 如何识别主入口脚本 |
| `callgraph_rules.md` | 如何追踪调用关系 |
| `ai_readable_notes.md` | 如何写适合 AI 阅读的深层说明 |

---

## 辅助脚本（`scripts/` 目录）

| 脚本 | 用途 |
|------|------|
| `scan_project.py` | 扫描目录结构，输出带注释的文件地图 |
| `extract_imports.py` | 提取 Python/JS 文件的 import 依赖，输出依赖图 |

---

## 安装说明

### 项目级安装（当前项目）

命令文件已位于：`.claude/commands/generate-docs.md`

在当前项目中直接使用：
```
/generate-docs
/generate-docs path/to/subdirectory
```

### 全局安装（所有项目）

将命令文件复制到 Claude Code 全局命令目录：

**macOS / Linux**：
```bash
mkdir -p ~/.claude/commands
cp .claude/commands/generate-docs.md ~/.claude/commands/
```

**Windows**：
```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\commands"
Copy-Item ".claude\commands\generate-docs.md" "$env:USERPROFILE\.claude\commands\"
```

安装后，在任何项目中都可使用 `/generate-docs`。

---

## 使用示例

```bash
# 分析当前目录
/generate-docs

# 分析指定子目录
/generate-docs src/demo_app

# 分析另一个项目
/generate-docs D:\Github\another-project
```

---

## 输出文件

| 文件 | 位置 | 说明 |
|------|------|------|
| `PROJECT_EXPLANATION.md` | 目标项目根目录 | 主输出文档 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0.0 | 2026-04-20 | 初始版本，支持 Python / JS / TS / Shell 项目 |
