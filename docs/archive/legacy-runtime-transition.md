# Legacy Runtime Transition

## 背景

仓库早期曾尝试把运行主链收敛到 `src/demo_app/` 下的 source-first 服务架构，包括：

- `src/demo_app/server.py`
- `src/demo_app/text_service.py`
- `src/demo_app/audio_service.py`
- `src/demo_app/runtime_bridge.py`
- `src/demo_app/runtime_patches*.py`
- `src/demo_app/legacy_runtime_*`

这些文件和配套测试、脚本一度承担过重构实验或过渡职责。

## 当前真实状态

截至当前仓库版本，真实可运行链路已经统一为：

```text
start_demo.bat
  -> scripts/start_server.bat
    -> scripts/start_server.py
      -> embedded_server.py
```

也就是说：

- `embedded_server.py` 才是当前真实服务主实现
- `server.py` / `run.py` / `app.py` 只是兼容入口
- `scripts/run_pre_release_ci_gate.py` 才是当前正式门禁入口

## 为什么归档这条说明

旧的 source-first 架构并没有在当前 checkout 中保留完整实现，但历史文档、旧脚本名和部分测试仍可能让维护者误以为：

- 服务主实现还在 `src/demo_app/`
- `scripts/run_pre_release_source_only_check.py` 仍是正式入口
- `app.py` 仍会启动桌面版独立主链

这些判断在当前仓库里都不再成立。

## 当前保留策略

为了降低误导和兼容旧使用习惯，当前做法是：

1. 保留根入口文件，但它们只做薄兼容：
   - `server.py`
   - `run.py`
   - `app.py`
2. 保留旧脚本名，但让它们转发到真实入口：
   - `scripts/run_pre_release_source_only_check.py`
3. 把旧 source-first 运行链视为“历史过渡方案”，不再作为当前架构说明依据。

## 后续建议

如果未来继续做更彻底的源码化重构，建议新主链在真正落地后再回到 `src/demo_app/`，并同步：

- 替换兼容入口
- 更新 `README.md`
- 更新 `docs/architecture.md`
- 更新 `docs/project_structure.md`
- 删除或归档旧的过渡文档
