# 调用关系追踪规则 / Call Graph Rules

> 如何从代码中提取模块间调用关系，并以清晰格式呈现在文档中。

---

## 第一步：收集所有 import 关系

### Python

扫描每个 `.py` 文件，提取：

```python
# 绝对 import（导入外部或顶层包）
import module_name
from package import module
from package.submodule import Class, function

# 相对 import（同包内）
from . import sibling
from .. import parent_module
from .utils import helper
```

**记录格式**：
```
文件 A → 依赖 → 文件 B（具体 import 的名称）
```

### JavaScript / TypeScript

```js
// CommonJS
const module = require('./path/to/module')
// ESModule
import { func } from './utils'
import * as helpers from '../helpers'
// 动态 import
const mod = await import('./lazy-module')
```

### Shell

```bash
source ./common.sh
. ../lib/utils.sh
```

---

## 第二步：识别函数级调用关系

在读取文件内容后，追踪：

### 哪些函数被哪些函数调用

示例（Python）：
```python
def main():
    config = load_config()        # main → load_config
    processor = Processor(config) # main → Processor.__init__
    result = processor.run()      # main → Processor.run

def Processor.run(self):
    data = self._preprocess()     # Processor.run → _preprocess
    output = transform(data)      # Processor.run → transform (from utils.py)
```

提取出：
```
main()
  └─ load_config()
  └─ Processor.__init__()
  └─ Processor.run()
       └─ Processor._preprocess()
       └─ transform() [utils.py]
```

### 追踪深度建议

- **最多追踪 4 层深度**，超过 4 层时标注 `...（更深层省略）`
- 外部库调用（如 `requests.get()`, `json.loads()`）只记录名称，不展开
- 标准库调用（如 `os.path.join()`）一般不需要展开

---

## 第三步：识别数据流

除调用链外，还需要追踪数据在模块间的流动方式。

### 数据流识别方法

**函数参数传递**：
```python
raw_data = read_file(path)        # raw_data: str
parsed = parse(raw_data)          # 输入 str → 输出 dict
result = process(parsed)          # 输入 dict → 输出 list
write_output(result)              # 输入 list → 写文件
```

数据流：
```
文件路径 → read_file() → raw str
→ parse() → dict 对象
→ process() → list 结果
→ write_output() → 输出文件
```

**共享状态**（全局变量、类属性）：
```python
# 全局缓存（多个函数共享）
_cache: dict = {}

def get_item(key):
    if key in _cache:
        return _cache[key]
    ...

def set_item(key, value):
    _cache[key] = value
```

记录：`_cache` 是跨函数共享的状态，由 `get_item()` 和 `set_item()` 共同维护。

---

## 第四步：识别外部系统调用

在调用链中特别标注外部调用：

| 调用类型 | 识别关键词 | 标注方式 |
|---------|-----------|---------|
| HTTP/API | `requests`, `aiohttp`, `fetch`, `axios`, `urllib` | `[HTTP → 外部API]` |
| 文件系统 | `open()`, `Path.read_text()`, `fs.readFileSync()` | `[文件读写]` |
| 数据库 | `sqlite3`, `psycopg2`, `mongoose`, `prisma` | `[数据库]` |
| 进程调用 | `subprocess.run()`, `os.system()`, `exec()` | `[子进程]` |
| 消息队列 | `pika`, `kafka-python`, `redis` | `[消息队列]` |
| 音频/视频处理 | `ffmpeg`, `pydub`, `librosa` | `[媒体处理]` |
| TTS/ASR | `edge_tts`, `kokoro`, `whisper` | `[语音合成/识别]` |
| LLM API | `openai`, `anthropic`, `requests` to LLM endpoints | `[LLM API]` |

---

## 调用链文档格式

### 简单线性流程

```
main()
  └─ setup()
  └─ process()
  └─ output()
```

### 分支流程

```
main()
  ├─ [成功路径] process()
  │    └─ save_result()
  └─ [失败路径] handle_error()
       └─ log_error()
```

### 并发流程

```
main()
  └─ asyncio.gather()
       ├─ [并发] task_1()   ← 同时执行
       ├─ [并发] task_2()   ← 同时执行
       └─ [并发] task_3()   ← 同时执行
  └─ merge_results()
```

### 带外部调用的流程

```
generate_audio()
  └─ build_prompt() [prompt_builder.py]
  └─ call_llm()
       └─ [HTTP → OpenAI API]
  └─ synthesize_speech()
       └─ [TTS → edge_tts]
  └─ save_audio()
       └─ [文件写入 → output/audio/*.mp3]
```

---

## 无法确认调用关系时的处理

### 动态调用（难以静态分析）

```python
# 动态 import
module = importlib.import_module(module_name)
func = getattr(module, func_name)
func()
```

文档写法：
> **[动态调用]** 此处通过 `importlib.import_module()` 动态加载模块，具体调用哪个模块取决于运行时的 `module_name` 参数，无法静态分析。

### 回调函数

```python
processor.on_complete(callback)  # callback 是外部传入的
```

文档写法：
> **[回调]** `on_complete` 在处理完成后调用外部传入的 `callback` 函数，具体行为依赖调用方。

---

## 调用关系简化原则

当项目特别复杂时，按以下原则简化：

1. **只展示核心路径**：跳过边缘路径（错误处理、日志、调试代码）
2. **合并重复调用**：`for item in items: process(item)` → `process() × N`
3. **折叠内部实现**：对于简单 getter/setter，不展开内部
4. **注明省略**：如果有省略，写 `（…省略 N 个子调用）`
