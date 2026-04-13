# 开发流程

## 先看什么

当前仓库已经收成了更轻量的结构，建议按这个顺序理解：

1. `docs/README.md`
2. `docs/product/online-audio-generation-prd.md`
3. `docs/guides/development-workflow.md`

## 本地启动

推荐入口：

- `start_demo.bat`

如果要直接用 Python 入口：

- `python server.py`

服务启动后访问：

- `http://127.0.0.1:8899/`

## 目录约定

- `src/demo_app/`
  - 服务主实现与核心逻辑
- `static/`
  - 页面、脚本、样式
- `config/`
  - 当前 demo 运行配置
- `scripts/`
  - 启动、检查、维护脚本
- `tools/`
  - 临时生成、分析、验证类工具
- `training/`
  - 训练语料脚本、训练数据、训练文档
- `docs/`
  - 当前仍保留的文档

## GitHub 工作方式

默认流程：

1. 从 `main` 切分支
2. 在独立分支开发
3. 本地自测
4. 提交并推送
5. 发起 PR
6. PR 合并后，再同步正式目录

建议分支前缀：

- `codex/feature/*`
- `codex/fix/*`
- `codex/chore/*`
- `codex/docs/*`

## 提交前建议检查

至少执行：

- `python -m py_compile server.py src\\demo_app\\embedded_server_main.py`
- `python -m unittest tests.test_multilingual_naturalness`

如果改了脚本或仓库结构，再补：

- `python scripts\\run_pre_release_ci_gate.py`

## 说明

- 根目录只保留两个直接入口：`server.py` 和 `start_demo.bat`
- 历史 legacy、运行残留、临时输出不再放回根目录
- 新增文档优先放进 `docs/guides` 或 `docs/product`
