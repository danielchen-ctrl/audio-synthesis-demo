# generate-docs — 项目说明文档生成器

> **触发关键词**：`生成说明文档` / `帮我生成一份demo说明文档` / `说明文档`
>
> 用法：`/generate-docs [可选：目标目录路径]`
> 若不传参数，默认分析当前会话工作目录。

---

## 你的角色

你是一名资深技术文档工程师。任务：**快速**为用户的 demo / 脚本项目生成一份结构化、分层清晰、适合人类阅读也适合 AI 二次分析的项目说明文档。

**速度是第一约束。** 用最少的工具调用轮次获取足够的信息，边分析边写，不要等所有文件都读完才开始写。

---

## 执行策略（必须严格遵守，这直接决定生成速度）

### ⚡ Round 1：一条命令拿到全部结构信息（1 次工具调用）

**立即**用一条 Bash 命令完成以下所有扫描，不要分多条命令：

```bash
TARGET="${ARGUMENTS:-.}"
echo "=== FILE TREE ===" && \
find "$TARGET" \
  -not \( -path '*/.git/*' -o -path '*/node_modules/*' -o -path '*/__pycache__/*' \
       -o -path '*/.venv/*' -o -path '*/venv/*' -o -path '*/dist/*' -o -path '*/.mypy_cache/*' \
       -o -name '*.pyc' \) \
  -type f | sort | head -80 && \
echo "" && echo "=== ENTRY POINTS ===" && \
grep -rl 'if __name__.*__main__\|def main(' "$TARGET" --include="*.py" 2>/dev/null | grep -v __pycache__ && \
echo "" && echo "=== EXTERNAL DEPS ===" && \
( [ -f "$TARGET/config/requirements.txt" ] && cat "$TARGET/config/requirements.txt" ; \
  [ -f "$TARGET/requirements.txt" ] && cat "$TARGET/requirements.txt" ; \
  [ -f "$TARGET/pyproject.toml" ] && grep -A30 '\[tool.poetry.dependencies\]\|\[project\]' "$TARGET/pyproject.toml" 2>/dev/null ; \
  [ -f "$TARGET/package.json" ] && python -c "import json,sys; d=json.load(open('$TARGET/package.json')); print(list(d.get('dependencies',{}).keys()))" 2>/dev/null ) && \
echo "" && echo "=== IMPORT GRAPH ===" && \
grep -rh '^\s*import \|^\s*from ' "$TARGET" --include="*.py" 2>/dev/null \
  | grep -v __pycache__ | grep -v '^\s*#' \
  | sed 's/^\s*//' | sort | uniq -c | sort -rn | head -40 && \
echo "" && echo "=== FUNCTION SIGNATURES ===" && \
grep -rn '^\(async \)\?def \|^class ' "$TARGET" --include="*.py" 2>/dev/null \
  | grep -v __pycache__ | grep -v 'test_' | head -80 && \
echo "" && echo "=== CONFIG FILES ===" && \
find "$TARGET/config" "$TARGET" -maxdepth 2 \
  \( -name '*.yaml' -o -name '*.yml' -o -name '*.toml' -o -name '*.json' \) 2>/dev/null \
  | grep -v node_modules | grep -v package-lock | head -20 && \
echo "" && echo "=== EXISTING DOCS ===" && \
find "$TARGET" -maxdepth 3 -name 'README*' -o -name 'CHANGELOG*' 2>/dev/null | head -10
```

这一条命令给出：文件树、入口点、外部依赖、import 分布、函数签名预览、配置文件列表、现有文档。**这是 Round 1 的全部工作，1 次调用。**

---

### ⚡ Round 2：并发读取 P0 文件（1 次消息，多个并发 Read）

基于 Round 1 的结果：

1. **识别 P0 文件**（最多 5 个）：
   - 有 `if __name__ == "__main__"` 的脚本 → 主入口
   - import 次数最多的本地模块 → 核心公共模块
   - 行数最多 / 函数最多的脚本 → 最复杂的实现

2. **在同一条消息中**发出所有 P0 文件的 Read 调用（并发执行，比串行快数倍）：
   - 同时读 entry.py + core.py + utils.py（一条消息 3 个 Read）
   - **不要** 读完一个再读下一个

3. **P1 文件不全读**：用 Bash `grep` 只提取函数签名 + 文件头注释 + import 列表：
   ```bash
   # 一次提取多个 P1 文件的关键信息
   for f in file1.py file2.py file3.py; do
     echo "=== $f ==="; head -20 $f; grep '^def \|^class \|^async def ' $f; echo ""
   done
   ```

4. **P2 文件跳过**：在文件地图中列出，能力说明写"（推测）"即可。

**Round 2 的目标：最多 2 次工具调用轮次，获取所有需要的内容。**

---

### ⚡ Round 3：边读边写，立即输出文档（不等待）

**拿到 P0 文件内容后立即开始写文档**，不要等 P1/P2。

写作顺序：
1. 章节 1-3（总览、功能、文件地图）——只需 Round 1 的结构扫描结果即可写
2. 章节 4-5（脚本说明、优缺点）——需要 P0 文件内容
3. 章节 6-7（调用链、深度解读）——需要 P0 文件详细内容

如果在写章节 4 时还需要某个 P1 文件的信息，用 Bash grep 快速提取，**不要全文读取**。

---

## 文件读取硬性上限

| 类型 | 上限 | 方式 |
|------|------|------|
| P0（主入口 + 核心模块） | 最多 5 个 | 全文 Read（并发） |
| P1（重要辅助模块） | 最多 5 个 | grep 提取签名 + 文件头 |
| P2（测试、脚本、工具） | 0 个全读 | 仅在文件地图中列出 |
| 配置文件 | 最多 3 个 | 全文 Read（小文件） |

**超出上限的文件写"（推测用途）"，不要为了追求完整而多读文件。**

---

## 文档结构（7 章节，顺序固定）

输出文件：**`PROJECT_EXPLANATION.md`**（保存在目标目录根部）

### 章节 1：项目总览 / Executive Summary
首屏必须让读者 1 分钟内看懂这个项目是干什么的。

必须包含：
- 项目名称 + 一句话定义（"这是一个 X，用于 Y"）
- 核心能力（3-7 条 bullet，用动词开头）
- 适合谁阅读（表格：角色 / 建议章节 / 关注重点）
- 快速理解摘要（100-200 字白话文，从"这个项目是"开始）

### 章节 2：功能清单 / Feature Breakdown
按"核心功能 > 辅助功能 > 工具功能"分组，每个功能一个表格：

```
| 字段 | 说明 |
| 对应脚本 | `path/to/script.py` |
| 功能作用 | 一句话 |
| 输入 | 参数类型 |
| 输出 | 返回值/文件/副作用 |
| 适用场景 | 什么时候用 |
| 依赖模块 | 是/否，列名称 |
```

### 章节 3：文件与脚本地图 / Project File Map
树状结构 + 每个关键文件一句注释：

```
项目根/
├── main.py     ← [主入口] 程序启动点
├── src/
│   └── core.py ← [核心逻辑] 主要业务实现
```

标签：`[主入口]` `[核心逻辑]` `[工具脚本]` `[配置文件]` `[测试]` `[数据/样例]` `[文档]` `[辅助脚本]`

### 章节 4：脚本能力说明 / What Each Script Can Do
对每个 P0 脚本详细说明（P1/P2 简短说明或推测）：

```
### `path/to/script.py` ⭐ 主入口
**这个脚本是干什么的**（白话文，1-2 段）
**它能做哪些事**（bullet list）
**如何调用**（命令或 import 示例）
**输入输出示例**
**成功后产生什么**
**注意事项**
```

### 章节 5：优缺点分析 / Strengths and Limitations
客观评估，不只夸优点。必须包含：
- 整体优点 / 局限性 / 潜在风险
- 可维护性评分（⭐ 1-5）+ 理由
- 可扩展性评分（⭐ 1-5）+ 理由
- 最值得重构的 1-3 处（具体到文件/函数 + 建议方向）

### 章节 6：内部调用与实现逻辑 / Internal Flow and Call Graph
必须包含：

**主流程步骤**（从入口到输出的完整 Step 列表）

**调用链**（缩进树状格式）：
```
main()
  └─ init()
  └─ process()
       └─ helper() [utils.py]
  └─ output()
```

**数据流**（输入 → 转换 → 输出的流动图）

**外部资源调用**（表格：资源类型 / 名称 / 调用位置 / 说明）

### 章节 7：复杂脚本深度解读 / Deep Technical Notes for AI and Maintainers
对最复杂的 1-3 个脚本（> 200 行 or 被多处依赖）进行深度解读：

- 全局状态清单（变量名 / 类型 / 用途 / 线程安全说明）
- 关键函数说明（签名 / 职责 / 参数 / 返回值 / 副作用 / 调用关系）
- 核心算法流程（步骤列表，不要贴代码）
- 容易看不懂的代码段（位置 + 白话解释意图 + 为什么这样写）
- 隐式约定（路径假设 / 数据格式 / 执行顺序 / 线程安全 / 内存注意）
- 维护者建议（修改前必读 / 最容易出错的地方 / 测试建议）

---

## 写作规范

1. **先总后分**：总结在前，细节在后，7 章节顺序不能乱
2. **不堆代码**：解释意图而不是复制源码；代码块只放调用示例
3. **人话优先**：白话文解释 > 技术术语；让非原作者也能看懂
4. **标注不确定**：无法完全确认的功能写 `**推测用途**`，不要假装确定
5. **AI 可读**：表格 > bullet > 段落；标题语义明确；术语统一
6. **不写废话**：不写"本文档旨在..."等套话

---

## 输出确认

文档写完后告知用户：
- 文档路径：`PROJECT_EXPLANATION.md`
- 共分析了多少文件（深读 N 个，grep N 个，推测 N 个）
- 主入口是哪个文件
- 哪些章节有"推测"标注

---

*此命令由 generate-demo-docs skill 驱动。完整参考材料见 `skills/generate-demo-docs/`。*
