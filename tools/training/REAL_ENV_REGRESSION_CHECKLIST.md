# 训练导出真实环境回归清单

## 目标

确认统一训练计划在真实运行时满足下面两点：

1. 高分样本继续正常落盘到 `passed/`
2. 低分样本在开启 `--keep-failed-samples` 后，会落盘到 `failed_samples/`，并同时导出 `.txt`、`.meta.json`、`.score.json`

## 运行命令

先跑一个会保留低分样本的阶段：

```bash
python tools/training/run_training_plan.py \
  --stage foundation_templates \
  --storage-dir output/training/regression_run \
  --keep-failed-samples
```

如果你还想确认默认行为，再跑一次不带保留开关的版本：

```bash
python tools/training/run_training_plan.py \
  --stage foundation_templates \
  --storage-dir output/training/regression_run_no_failed
```

## 检查项

- `output/training/regression_run/_index.jsonl` 中应同时出现 `passed=true` 和 `passed=false` 的记录
- `output/training/regression_run/failed_samples/` 下至少应有一个失败样本目录
- 每个失败样本目录内都应包含同名的 `.txt`、`.meta.json`、`.score.json`
- 任意一个失败样本的 `.score.json` 中应包含 `passed`、`score`、`metrics`、`findings`
- 任意一个失败样本的 `.meta.json` 中 `quality.findings` 应与对应 `.score.json` 的 `findings` 一致
- 不带 `--keep-failed-samples` 的输出目录中，不应生成失败样本的 `.txt`、`.meta.json`、`.score.json`
- 两次运行都应持续写入 `_index.jsonl`；失败任务仍应写入 `_failed.jsonl`

## 建议额外抽查

- 找一个明显低分样本，确认 `findings` 里的 `code` 和 `message` 对排查问题足够直观
- 找一个通过样本，确认路径仍然落在 `passed/<stage>/<job_function>/<language>/`
