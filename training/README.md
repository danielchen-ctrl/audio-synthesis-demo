# training 目录说明

当前 `training/` 按“脚本 / 数据 / 文档”拆开：

- 根目录 Python 文件
  - 训练任务生成、回归、模板提取等可执行脚本
- `data/`
  - 训练任务清单与固定场景数据
- `docs/`
  - 训练链路说明与历史实施记录

## 入口

- 使用说明：`training/docs/pipeline-guide.md`
- 历史记录：`training/docs/implementation-report.md`
- 数据样例：
  - `training/data/training_jobs_mvp.jsonl`
  - `training/data/training_jobs_full.jsonl`
  - `training/data/payment_scenarios_5step.json`

## 说明

为了不破坏 `python -m training.xxx` 的运行方式，训练脚本仍保留在 `training/` 根层；这次只把大数据文件和文档抽离出去。
