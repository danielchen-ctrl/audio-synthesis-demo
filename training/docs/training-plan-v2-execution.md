# 训练方案 v2 执行文档

> 最后更新：2026-05-03  
> 状态：**代码已就绪，等待在主项目上执行**  
> 分支：`codex/fix/legacy-generation-adapter`（已有全部修复）

---

## 一、总览

训练方案 v2 共 6 个批次，总计 **65,628 个任务**，覆盖 3 种语言（中文、英语、日语）× 22 个行业模板 × 多人数/字数组合。

| 批次 | 描述 | 任务数 | 预估时间* |
|------|------|--------|----------|
| B0 smoke | 验证批：确认流程正常 | 594 | ~5h |
| B1 foundation | 模板底座：22模板全覆盖 | 3,960 | ~33h |
| B2 positive_pairs | 正配对强化 | 16,038 | ~5.5d |
| B3 cross_combo_base | 全交叉基础覆盖 | 24,948 | ~8.5d |
| B4 high_risk_boost | 高风险泛化强化 | 18,900 | ~6.5d |
| B5 extreme_50k | 50000字极限强化 | 1,188 | ~10h |

*按每任务约 30 秒单进程估算，实际取决于机器。

---

## 二、前置条件检查

在主项目目录确认以下文件存在：

```bash
ls build/demo_app/SceneDialogueDemo.exe   # LLM 引擎
ls build/DialogDemo/DialogDemo.pkg        # 静态资源（可选，无此文件时跳过静态提取）
ls training/data/training_jobs_b0_smoke.jsonl  # B0 任务文件（已提交）
```

安装依赖：

```bash
pip install -r config/requirements.txt
```

---

## 三、执行命令

### 全量跑（推荐）

```bash
python tools/training/run_all_batches.py
```

### 断点续跑（中途中断后）

```bash
python tools/training/run_all_batches.py --resume
```

### 只跑指定批次

```bash
# 只跑 B0 + B1（最核心的两批）
python tools/training/run_all_batches.py --only-batches b0_smoke b1_foundation

# 跳过已完成的批次，从 B2 开始
python tools/training/run_all_batches.py --skip-batches b0_smoke b1_foundation
```

### 单独跑某个批次（绕过编排脚本）

```bash
python tools/training/run_training_plan.py \
  --batch b0_smoke \
  --out_dir output/training_v2 \
  --keep-failed-samples \
  --max_retries 2
```

---

## 四、数据管理

### 输出目录结构

```
output/training_v2/
  _master_log.jsonl            ← 跨批次主日志（每批次一行汇总）
  b0_smoke/
    passed/                    ← 有效训练数据 ✅ 保留
    failed_samples/            ← B0 失败样本（供分析，手动清理）
    _index.jsonl               ← 所有任务最终状态 ✅ 保留
    _failed.jsonl              ← 失败原因索引 ✅ 保留
  b1_foundation/
    passed/                    ← 有效训练数据 ✅ 保留
    _index.jsonl               ✅ 保留
    _failed.jsonl              ✅ 保留
    (failed_samples/ 自动清理)
  b2_positive_pairs/ ...       ← 同上
```

### 清理规则

- `passed/`：**永远保留**，这是最终训练数据
- `failed_samples/`：B0 手动保留供分析；B1-B5 批次结束后自动清理
- `_index.jsonl` / `_failed.jsonl`：保留，文件小，用于进度查询和复盘
- `_master_log.jsonl`：保留，跨批次汇总

### B2-B4 任务文件

B2（14MB）/ B3（22MB）/ B4（17MB）的 jobs JSONL 未提交 git，首次运行时自动生成（约 10-30 秒）并缓存到 `training/data/`。

---

## 五、进度查询

### 查看某批次通过率

```bash
python3 - <<'EOF'
import json
batch = "b0_smoke"          # 改成要查的批次
p = f"output/training_v2/{batch}/_index.jsonl"
records = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
by_tid = {}
for r in records: by_tid[r["task_id"]] = r
final = list(by_tid.values())
passed = sum(1 for r in final if r["passed"])
print(f"{batch}: {passed}/{len(final)} 通过 ({passed/len(final):.1%})")
# 按语言细分
from collections import defaultdict
by_lang = defaultdict(lambda: [0,0])
for r in final:
    by_lang[r.get("language","?")][0] += r["passed"]
    by_lang[r.get("language","?")][1] += 1
for lang, (p, t) in sorted(by_lang.items()):
    print(f"  {lang}: {p}/{t} ({p/t:.1%})")
EOF
```

### 查看主日志

```bash
python3 - <<'EOF'
import json
for line in open("output/training_v2/_master_log.jsonl", encoding="utf-8"):
    s = json.loads(line)
    if s.get("event") == "all_batches_complete": continue
    print(f"{s['batch']:<22} {s['passed']:>5}/{s['total']:<6} {s['pass_rate']:.1%}  {s['elapsed_seconds']//60}min")
EOF
```

### 统计已生成的有效数据量

```bash
find output/training_v2 -name "*.txt" -path "*/passed/*" | wc -l
find output/training_v2 -name "*.txt" -path "*/passed/*" -exec wc -c {} + | tail -1
```

---

## 六、B0 门控逻辑

`run_all_batches.py` 在 B0 结束后检查通过率：

- **≥ 30%**：继续执行 B1-B5
- **< 30%**：终止，提示排查 `output/training_v2/b0_smoke/failed_samples/`

如果需要调整门槛：

```bash
python tools/training/run_all_batches.py --b0-min-pass-rate 0.40
```

---

## 七、常见问题处理

### 中途中断后续跑

```bash
python tools/training/run_all_batches.py --resume
```

`--resume` 会读取各批次 `_index.jsonl` 里 `passed=true` 的 task_id，跳过已完成任务。

### 某批次跑了一部分，想重跑失败的任务

失败任务不写入 `passed=true`，直接用 `--resume` 重跑即可。

### 通过率异常低

1. 看失败原因：
```bash
python3 -c "
import json
lines = [json.loads(l) for l in open('output/training_v2/b0_smoke/_failed.jsonl', encoding='utf-8') if l.strip()]
from collections import Counter
errors = Counter(l.get('error','')[:80] for l in lines)
for e, c in errors.most_common(10): print(c, e)
"
```

2. 看失败样本的 score：
```bash
python3 -c "
import json, glob
for f in glob.glob('output/training_v2/b0_smoke/failed_samples/**/*.score.json', recursive=True)[:5]:
    d = json.load(open(f, encoding='utf-8'))
    print(d['score'], [x['code']+':'+x['severity'] for x in d['findings']])
"
```

### bundle 无法加载（Missing asset archive）

确认 `build/demo_app/SceneDialogueDemo.exe` 存在。`build/DialogDemo/DialogDemo.pkg` 不存在时会跳过静态资源提取，不影响训练。

---

## 八、训练数据使用

训练完成后，有效数据在 `output/training_v2/*/passed/`，每个样本包含：

- `*.txt`：对话正文（`Speaker N: 内容` 格式）
- `*.meta.json`：生成参数（scenario、language、people_count 等）
- `*.score.json`：质量评分详情

导出为 few-shot 语料库（后续工具 `export_fewshot_candidates.py` 待实现）：

```bash
# 后续补充：按域/语言/字数筛选优质样本，写入 demo/training_long_dialogue/
```

---

## 九、已修复的 Bug（本次会话）

| 问题 | 文件 | 修复方式 |
|------|------|---------|
| `Role` 无 `responsibility` 属性 | `embedded_server_main.py` | 预加载 `dialogue_intelligence_engine.pyc`，patch `Role.__init__` |
| `sys` NameError in bundle | `embedded_server_main.py` | 预加载 `industry_template_loader.pyc`，注入 `sys` |
| `missing_core_marker` 拦截全部任务 | `quality_scoring.py` | severity `"error"` → `"warning"` |
| validator 重复报错 | `dialogue_validators.py` | 删除 core marker 校验 |
| 缺少 `.pkg` 时崩溃 | `embedded_server_main.py` | `_cache_is_fresh()` / `ensure_embedded_runtime()` 改为条件检查 |

相关提交：`9fcaefa4`, `1f9867bc`, `054d8af8`
