# 脚本分析优先级规则 / Script Analysis Priority Rules

> 当项目文件数量较多时，按此规则决定分析顺序和详细程度。

---

## 文件读取优先级（从高到低）

### P0 — 必须完整阅读

| 类型 | 识别方式 | 原因 |
|------|---------|------|
| 主入口脚本 | 见 `entrypoint_detection.md` | 理解整体流程的起点 |
| 配置文件 | `*.yaml`, `*.toml`, `*.json`（根目录）, `.env*` | 理解环境假设和参数 |
| 依赖声明 | `requirements*.txt`, `pyproject.toml`, `package.json`, `go.mod` | 理解技术栈和外部依赖 |
| 被多处 import 的模块 | 出现在 3 个以上其他文件的 import 中 | 核心公共接口 |

### P1 — 优先阅读（至少读前 200 行 + 函数签名）

| 类型 | 识别方式 |
|------|---------|
| 核心业务逻辑 | 文件名含 `core`, `engine`, `processor`, `handler`, `service` |
| 数据模型定义 | 文件名含 `model`, `schema`, `types`, `struct` |
| API 定义 | 文件名含 `api`, `routes`, `endpoints` |
| 主要工具函数 | 文件名含 `utils`, `helpers`, `common`，但被多处调用 |

### P2 — 按需阅读（读函数签名和 docstring）

| 类型 | 识别方式 |
|------|---------|
| 辅助脚本 | 被调用次数少（0-1 次） |
| 测试文件 | `test_*.py`, `*_test.py`, `tests/` 目录下 |
| 示例脚本 | 文件名含 `example`, `demo`, `sample` |

### P3 — 可跳过（记录存在即可）

| 类型 | 识别方式 |
|------|---------|
| 自动生成文件 | `*_pb2.py`, `*_generated.*`, `migrations/` |
| 锁定文件 | `*.lock`, `package-lock.json`, `Pipfile.lock` |
| 编译产物 | `*.pyc`, `*.so`, `*.dll`, `dist/`, `build/` |
| 大型数据文件 | `*.csv`, `*.json`（>100KB）, `*.parquet` |

---

## 文件数量上限规则

当项目文件超过 20 个时，按以下策略控制分析范围：

1. **P0 文件**：无上限，全部读取
2. **P1 文件**：最多 8 个，超出时优先选择被引用次数最多的
3. **P2 文件**：最多 5 个，超出时仅列举不详细分析
4. **P3 文件**：仅在文件地图中列出，不分析内容

### 引用次数统计方法

```python
# 对于 Python 项目，统计每个模块被 import 的次数
import re
from pathlib import Path

def count_imports(project_dir: Path) -> dict:
    import_counts = {}
    for py_file in project_dir.rglob("*.py"):
        content = py_file.read_text()
        # 匹配 "from xxx import" 和 "import xxx"
        imports = re.findall(r'from\s+([\w.]+)\s+import|^import\s+([\w.]+)', 
                            content, re.MULTILINE)
        for imp in imports:
            module = imp[0] or imp[1]
            import_counts[module] = import_counts.get(module, 0) + 1
    return import_counts
```

---

## 复杂度评估规则

判断一个脚本是否需要"深度解读"（章节 7），使用以下标准：

### 高复杂度（必须深度解读）

满足以下任意一条：
- 函数数量 > 10 个
- 有循环内的循环（嵌套深度 ≥ 3）
- 有异步逻辑（`async/await`, `asyncio`, `Promise`）
- 有复杂的错误处理链（try/except/finally 嵌套）
- 有全局状态管理（全局变量、类级别缓存）
- 有并发逻辑（threading, multiprocessing, 协程）
- 有复杂的数据转换流水线
- 代码行数 > 300 行

### 中等复杂度（简要说明即可）

- 函数数量 5-10 个
- 有一层错误处理
- 代码行数 100-300 行

### 低复杂度（能力说明即可）

- 函数数量 < 5 个
- 逻辑线性，易读
- 代码行数 < 100 行

---

## 不确定性标注规则

当无法完全确认某个功能或实现时，必须使用以下标注方式：

| 确信程度 | 标注方式 | 示例 |
|---------|---------|------|
| 完全确认（代码中明确） | 直接描述 | "此函数将音频合并为单个文件" |
| 基本确认（逻辑推断） | "（推断）" | "（推断）此参数控制并发数量" |
| 不确定（猜测） | "**推测用途**：" | "**推测用途**：可能用于限流控制" |
| 完全不明 | "**[待确认]**" | "**[待确认]** 此函数用途不明，需要原作者说明" |

---

## 分析质量检查清单

生成文档前，对照此清单验证分析是否完整：

- [ ] 已找到至少一个主入口脚本
- [ ] 已读取所有 P0 文件
- [ ] 已统计关键模块的引用次数
- [ ] 已识别所有外部 API 调用
- [ ] 已识别所有文件系统读写路径
- [ ] 已识别所有环境变量依赖
- [ ] 已评估每个脚本的复杂度
- [ ] 已确定哪些脚本需要深度解读（章节 7）
- [ ] 所有不确定项已标注
