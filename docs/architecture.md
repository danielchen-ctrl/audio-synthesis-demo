# 架构说明

## 当前真实结构

> 说明：本文件基于当前仓库实际内容整理；不确定或尚未完全收敛的部分会标注“待补充”。

## 模块关系

### 1. 启动层

当前可运行入口主要包括：

- `start_demo.bat`
  - 最直接的一键启动入口
- `scripts/start_server.bat`
  - 服务启动脚本
- `scripts/start_server.py`
  - Python 启动包装
- `run.py`
- `server.py`
- `app.py`

其中当前真实服务主实现是：

- `embedded_server.py`

`run.py`、`server.py`、`app.py` 主要承担兼容入口角色。

### 2. 服务层

当前仓库的主要服务逻辑集中在：

- `embedded_server.py`

它负责：

- 加载嵌入式 bundle 中的模块与静态资源
- 提供 Web 页面
- 提供文本生成、音频合成、下载等接口
- 管理本地缓存和输出目录

### 3. 前端层

前端资源位于：

- `static/index.html`
- `static/app.js`
- `static/styles.css`

当前前端支持：

- 录入参数
- 生成文本
- 手动编辑文本
- 合成音频
- 下载文本与音频

对应的用户侧启动与分享说明：

- `docs/demo-startup-sharing-guide.md`

### 4. 配置层

配置文件位于：

- `config/app.yaml`
- `config/logging.yaml`
- `config/paths.yaml`
- `config/runtime.yaml`
- `config/runtime.pre_release.yaml`
- `config/text_postprocess_rules.yaml`
- `config/text_quality_rules.yaml`

这些文件主要用于：

- 路径配置
- 运行配置
- 规则配置
- 发布前 source-only 检查配置

### 5. 脚本层

脚本位于：

- `scripts/`

当前主要分为：

- 启动脚本
- 质量检查脚本
- 发布前门禁脚本
- Project Guard / 清理脚本
- 版本辅助脚本
- 定时任务安装脚本

当前正式的发布前门禁入口：

- `scripts/run_pre_release_ci_gate.py`
- `scripts/enforce_pre_release_ci_gate.py`
- `.github/workflows/pre-release-gate.yml`

### 6. 测试层

测试位于：

- `tests/`

当前仓库已有：

- 单元测试
- 配置与规则加载测试
- 回归与 smoke 测试
- 多语言质量相关测试

### 7. 资源与领域数据

`src/demo_app/` 当前主要承载：

- `assets/`
- `domains/`

目前它更偏“资源和领域数据容器”，并非当前真实服务主实现所在位置。

这里后续是否继续收敛为完整应用包结构：**待补充**。

## 当前真实启动链路

```text
start_demo.bat
  -> scripts/start_server.bat
    -> scripts/start_server.py
      -> embedded_server.main()
        -> Tornado Web Server
        -> static/
        -> 本地输出与下载接口
```

## 当前输出与运行目录

- `demo/`
  - 当前演示输出目录
- `runtime/`
  - 本地运行时目录
- `reports/`
  - 检查与回归报告
- `output/`
  - 生成或训练产物

这些目录属于运行产物或生成产物，默认不应随意纳入版本管理。

## 当前技术债

1. 当前真实服务主实现仍集中在 `embedded_server.py`
   - 可维护，但后续如果服务继续变复杂，建议进一步拆分模块
2. `src/demo_app/` 与当前实际运行链路并未完全统一
   - 后续是否收敛：待补充
3. 部分 bundle / 嵌入式依赖仍然存在
   - 这会影响长期的源码化维护边界
