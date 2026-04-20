# 主入口脚本识别规则 / Entrypoint Detection Rules

> 识别主入口脚本是生成调用链和流程图的前提。
> 按以下规则，从高置信度到低置信度依次判断。

---

## 规则 1：显式入口模式（置信度：极高）

### Python

```python
# 文件末尾或中部有以下模式 → 这是主入口
if __name__ == "__main__":
    main()
    # 或
    app.run()
    # 或
    asyncio.run(main())
```

识别方法：搜索 `if __name__ == "__main__"` 或 `if __name__ == '__main__'`

### Node.js / TypeScript

```js
// 文件顶部有以下注释 → 通常是入口
#!/usr/bin/env node

// 或文件直接调用（不是函数定义）
app.listen(port, ...)
server.start()
```

### Shell / Bash

```bash
# 文件中直接调用函数（不仅是定义）
#!/bin/bash
main "$@"  # ← 入口
```

---

## 规则 2：文件名模式（置信度：高）

以下文件名几乎总是入口：

| 文件名模式 | 说明 |
|-----------|------|
| `main.py` / `main.js` / `main.ts` | 约定的主入口名 |
| `app.py` / `app.js` | Web 应用入口 |
| `server.py` / `server.js` | 服务器入口 |
| `cli.py` / `cli.js` | 命令行工具入口 |
| `run.py` / `start.py` | 启动脚本 |
| `index.py` / `index.js` | 模块主入口 |
| `__main__.py` | Python 包的主入口（`python -m package`）|
| `entrypoint.py` / `entrypoint.sh` | 明确命名的入口 |

---

## 规则 3：配置文件指定（置信度：高）

查找以下配置文件中指定的入口：

### `pyproject.toml`
```toml
[tool.poetry.scripts]
my-tool = "my_package.cli:main"  # ← 入口是 my_package/cli.py 的 main 函数

[project.scripts]
my-tool = "my_package:main"
```

### `package.json`
```json
{
  "main": "src/index.js",     ← 模块入口
  "scripts": {
    "start": "node server.js" ← 运行入口
  }
}
```

### `Makefile` / `Taskfile`
```makefile
run:
    python src/main.py  # ← 从这里找入口文件
```

### `docker-compose.yml` / `Dockerfile`
```yaml
command: python app.py    # ← 容器启动入口
ENTRYPOINT ["python", "main.py"]
```

---

## 规则 4：被引用次数（置信度：中）

**主入口特征**：它引用（import）其他模块，但几乎不被其他模块引用。

```
高 import 出度 + 低 import 入度 → 很可能是入口
低 import 出度 + 高 import 入度 → 很可能是工具/公共模块
```

---

## 规则 5：命令行参数解析（置信度：中）

包含以下模式的脚本通常是入口：

**Python**：
```python
import argparse
parser = argparse.ArgumentParser(...)
# 或
import click
@click.command()
# 或
import typer
app = typer.Typer()
```

**Node.js**：
```js
const argv = require('yargs').argv
// 或
process.argv
```

---

## 规则 6：README 提示（置信度：中）

查找 README 中的"快速开始"或"运行方式"：

```markdown
## 运行

python main.py  ← 这就是入口
```

---

## 多入口项目处理

有些项目有多个入口（如：多个独立 demo 脚本）。

### 识别方式

- 多个文件都符合规则 1-2
- 文件名有明显的功能区分（如 `demo_audio.py`, `demo_upload.py`）
- 脚本之间无互相引用

### 文档处理方式

在章节 3（文件地图）中用 `[主入口]` 标记所有入口，并在章节 6（调用链）中分别说明每个入口的独立流程。

---

## 排除列表（即使文件名相似，这些不是入口）

| 模式 | 原因 |
|------|------|
| `test_*.py` / `*_test.py` | 测试文件 |
| `conftest.py` | pytest 配置，不是业务入口 |
| `setup.py` / `setup.cfg` | 打包配置 |
| `migrate.py` / `seed.py` | 数据库工具，不是主入口 |
| `*.config.js` / `webpack.config.js` | 构建配置 |
| `__init__.py`（空文件或只有 import） | 包初始化，不是入口 |

---

## 入口脚本在文档中的处理

识别入口后：

1. **文件地图**：标注 `[主入口]`
2. **脚本能力说明**：排在最前，最详细，必须有调用示例
3. **调用链**：从入口函数开始绘制
4. **深度解读**：如果入口脚本复杂（> 100 行），必须进行深度解读
