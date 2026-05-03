# 训练数据生成系统 - MVP版本

**版本：**v1.4.6-MVP  
**完成时间：**2026-01-26  
**目标：**生成多职业×多语言×多场景的训练对话数据，形成闭环"场景库→任务生成→批量生成→运行时消费"

---

## 一、系统架构

```
training/
├── scenario_bank.py          # 场景库（390个场景，13职业×30场景）
├── build_training_jobs_mvp.py    # 任务生成器（MVP：生成JSONL任务清单）
├── run_training_generation_mvp.py # 批量生成器（MVP：调用server.py生成对话）
├── docs/pipeline-guide.md    # 使用说明
└── data/                    # 训练任务与固定场景数据

生成流程：
1. scenario_bank.py（已完成）
   ↓
2. build_training_jobs_mvp.py（生成任务清单）
   ↓
3. run_training_generation_mvp.py（批量生成txt+meta）
   ↓
4. output/training/mvp/{profession}/{language}/xxx.txt（训练数据）
```

---

## 二、快速开始（2条命令）

### 步骤1：生成任务清单（JSONL）

```powershell
# Windows PowerShell
cd D:\ui_auto_test\audio-synthesis-demo
python -m training.build_training_jobs_mvp --out training/data/training_jobs_mvp.jsonl --seed 20260126
```

**预期输出：**
```
[MVP任务生成] 总任务数: 390
[MVP任务生成] 按语言: {'中文': 195, '英语': 195}
[MVP任务生成] 按字数: {500: 130, 1500: 130, 3000: 130}
[MVP任务生成] 输出文件: training/data/training_jobs_mvp.jsonl
```

**生成规则：**
- 每职业前5个场景
- 语言：中文、英语
- 字数桶：500, 1500, 3000
- 总任务数：13职业 × 5场景 × 2语言 × 3字数 = 390

### 步骤2：批量生成对话数据

```powershell
# 全量生成（390个任务，约30-60分钟）
python -m training.run_training_generation_mvp --jobs training/data/training_jobs_mvp.jsonl --out_dir output/training/mvp

# 或测试前10个任务（约1-2分钟）
python -m training.run_training_generation_mvp --jobs training/data/training_jobs_mvp.jsonl --out_dir output/training/mvp --max_jobs 10
```

**预期输出：**
```
[MVP批量生成] 总任务数: 390
[MVP批量生成] 成功: 385 (98.7%)
[MVP批量生成] 失败: 5
[按职业统计]
  医疗健康: 成功30, 失败0
  人力资源与招聘: 成功30, 失败0
  ...
[按语言统计]
  中文: 成功195, 失败0
  英语: 成功190, 失败5
```

**输出目录结构：**
```
output/training/mvp/
├── 医疗健康/
│   ├── 中文/
│   │   ├── 医疗健康-01_500_2_3914250785.txt
│   │   ├── 医疗健康-01_500_2_3914250785.meta.json
│   │   ├── 医疗健康-01_1500_2_2847561923.txt
│   │   └── ...
│   └── 英语/
│       ├── 医疗健康-01_500_2_1234567890.txt
│       └── ...
├── 人力资源与招聘/
│   └── ...
└── _failed.jsonl  # 失败任务记录（如果有）
```

---

## 三、生成参数说明

### build_training_jobs_mvp.py 参数

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `--out` | 输出JSONL文件路径 | （必填） | `training/data/training_jobs_mvp.jsonl` |
| `--seed` | 随机种子（可复现） | 20260126 | `20260126` |

**JSONL格式示例：**
```json
{
  "job_function": "医疗健康",
  "work_content": "医疗服务供应商",
  "seniority": "高级职员",
  "scenario": "你是一名外科副主任医生，现在正在跟你的领导王院长谈论关于升职的事情...",
  "core_content": "感谢院长栽培，升职为外科主任，颁发优秀员工奖...",
  "language": "中文",
  "people_count": 2,
  "word_count": 500,
  "seed": 3914250785,
  "meta": {
    "tags": ["升职", "晋升", "沟通", "协调"],
    "scenario_id": "医疗健康-01",
    "bucket": 500
  }
}
```

### run_training_generation_mvp.py 参数

| 参数 | 说明 | 默认值 | 示例 |
|------|------|--------|------|
| `--jobs` | 任务JSONL文件路径 | （必填） | `training/data/training_jobs_mvp.jsonl` |
| `--out_dir` | 输出目录 | （必填） | `output/training/mvp` |
| `--max_jobs` | 最大任务数（测试用） | 999999 | `10`（只跑前10个） |

---

## 四、硬校验规则（自动检查）

每个生成的对话都会进行以下硬校验：

### 1. 核心标记唯一性
- ✅ 必须包含且仅包含1个核心标记
- 中文：`<<核心:...>>`
- 英文：`<<Core:...>>`
- 日文：`<<コア:...>>`
- ❌ 失败条件：缺少标记或重复标记

### 2. 占位符残留检查
- ❌ 禁止输出包含 `[[[CORE` 占位符
- 如果出现，任务失败重试

### 3. 非中文语言的中文占比
- ❌ 英语/日语输出中，中文字符占比必须 <10%
- 确保翻译质量

### 4. Speaker3空话过滤（people_count>=3时）
- ❌ Speaker3不得超过50%是"好的/明白了/收到"等空话
- 确保多人对话参与度

**失败重试机制：**
- 每个任务失败后最多重试2次
- 重试时seed+1（避免完全相同的输出）
- 所有重试都失败的任务记录到 `_failed.jsonl`

---

## 五、输出文件详解

### xxx.txt（对话文本）

```
Speaker 1: 王院长，非常感谢您今天抽时间和我谈升职的事情。
Speaker 2: 不用客气，你的工作表现一直很优秀，这次晋升是你应得的。
Speaker 1: 请问新岗位主要负责哪些工作？
Speaker 2: 新岗位主要包括科室管理、业务指导、人员培养，以及与医院各部门的协调沟通。<<核心:感谢院长栽培，升职为外科主任，颁发优秀员工奖。>>
Speaker 1: 我会全力以赴，不辜负您的期望。
...
```

**格式规范：**
- 每行：`Speaker N: 对话内容`
- 包含1次核心标记（红色显示用）

### xxx.meta.json（元数据）

```json
{
  "job_function": "医疗健康",
  "language": "中文",
  "scenario": "你是一名外科副主任医生...",
  "core_content": "感谢院长栽培...",
  "people_count": 2,
  "word_count": 500,
  "seed": 3914250785,
  "effective_params": {
    "scenario_head": "你是一名外科副主任医生，现在正在跟你的领导王院长谈论关于升职...",
    "core_head": "感谢院长栽培，升职为外科主任，颁发优秀员工奖...",
    "people_count": 2,
    "word_count": 500,
    "language": "中文"
  },
  "debug_info": {
    "scene_type": "promotion_meeting",
    "cast_count": 2,
    "line_count": 18,
    "total_chars": 512,
    "from_v2": false,
    "seed": 3914250785
  },
  "stats": {
    "line_count": 18,
    "total_chars": 512,
    "speaker_distribution": {
      "Speaker 1": 9,
      "Speaker 2": 9
    }
  }
}
```

**字段说明：**
- `effective_params`: 实际生效的参数（用于验证参数链路）
- `debug_info.from_v2`: 是否使用V2生成器（当前MVP全部false）
- `stats.speaker_distribution`: 每个speaker的发言行数（用于平衡检查）

---

## 六、常见问题

### Q1：为什么有些任务失败？

**失败原因Top3：**
1. **翻译服务超时**（英语/日语生成时）
   - 解决：重试时会自动处理
2. **核心标记重复**
   - 原因：生成逻辑在多个地方插入核心内容
   - 解决：后续版本统一插入策略
3. **中文占比过高**（英语输出）
   - 原因：翻译服务失败回退到中文
   - 解决：检查网络或使用backup翻译服务

### Q2：生成速度很慢怎么办？

**优化建议：**
1. 使用 `--max_jobs 50` 先测试小批量
2. 全量生成390任务约需30-60分钟（取决于字数和翻译服务）
3. 可以分批运行：
   ```powershell
   # 先跑中文（195个，约15分钟）
   python -m training.run_training_generation_mvp --jobs training/data/training_jobs_mvp.jsonl --out_dir output/training/mvp --max_jobs 195
   
   # 再跑英文（195个，约25分钟，因为翻译耗时）
   python -m training.run_training_generation_mvp --jobs training/data/training_jobs_mvp.jsonl --out_dir output/training/mvp
   ```

### Q3：如何验证生成质量？

**手工抽样检查：**
```powershell
# 随机查看一个生成的txt
notepad output/training/mvp\医疗健康\中文\医疗健康-01_500_2_3914250785.txt

# 检查meta.json
notepad output/training/mvp\医疗健康\中文\医疗健康-01_500_2_3914250785.meta.json
```

**自动化测试：**
```powershell
# 运行smoke test（见第八节）
python -m pytest tests/test_training_pipeline_smoke.py -v
```

### Q4：生成的对话质量不好怎么办？

**MVP版本限制：**
- 当前使用fallback生成器（V2禁用），质量受限
- 长文本（3000字）可能有重复
- 英语翻译质量依赖翻译服务

**改进方向（后续版本）：**
1. 启用V2智能生成器（需修复编码问题）
2. 扩展domain_kb到11个职业
3. 实现template_bank自动抽取和消费
4. 长文本分段生成策略

---

## 七、MVP vs 完整版对比

| 功能 | MVP版本 | 完整版（FULL） |
|------|---------|--------------|
| 场景库 | ✅ 390场景（13×30） | ✅ 390场景 |
| 任务生成 | ✅ 每职业5场景，中英2语言 | ✅ 全30场景，9语言 |
| 总任务数 | 390 | ~7800 |
| 生成器 | ✅ Fallback生成器 | ✅ Fallback生成器 |
| domain_kb | ✅ 已接入（4个职业） | ✅ 已接入 |
| template_bank | ❌ 未实现 | ❌ 待实现 |
| 硬校验 | ✅ 6项 | ✅ 8项 |
| 预估耗时 | 30-60分钟 | 10-15小时 |

---

## 七(A)、FULL版本使用指南

### 1. 生成FULL任务清单（~7800任务）

```powershell
# Windows PowerShell
cd D:\ui_auto_test\audio-synthesis-demo
python -m training.build_training_jobs_full --out training/data/training_jobs_full.jsonl --seed 20260126
```

**生成规则：**
- **中英日三语言**：全30场景 × 3语言 × 3字数桶 × 2人数 = ~5400任务
- **其他6语言**（韩、法、德、西、葡、粤）：前10场景 × 6语言 × 3字数桶 × 2人数 = ~2340任务
- **总计**：~7800任务

**预期输出：**
```
[训练任务生成器 - FULL版]
  基础种子: 20260126
  输出文件: training/data/training_jobs_full.jsonl

[医疗健康] 共30个场景
[人力资源与招聘] 共30个场景
...

[完成]
  总任务数: 7800
  输出文件: training/data/training_jobs_full.jsonl

[语言分布]
  中文: 2340任务 (fallback: 0, 0.0%)
  英语: 2340任务 (fallback: 5, 0.2%)
  日语: 2340任务 (fallback: 12, 0.5%)
  韩语: 780任务 (fallback: 23, 2.9%)
  法语: 780任务 (fallback: 18, 2.3%)
  ...
```

### 2. 批量生成对话数据（FULL版）

```powershell
# 全量生成（~7800任务，预计10-15小时）
python -m training.run_training_generation_mvp --jobs training/data/training_jobs_full.jsonl --out_dir output/training/full

# 或分批生成（每批1000个）
python -m training.run_training_generation_mvp --jobs training/data/training_jobs_full.jsonl --out_dir output/training/full --max_jobs 1000
```

**注意事项：**
- FULL版耗时长（~10-15小时），建议分批运行或后台运行
- 支持断点续传（已生成的文件不会重复生成）
- 失败任务会自动重试2次，最终失败的记录到 `_failed.jsonl`

### 3. FULL版8项硬校验

| 校验项 | 说明 | 阈值 |
|--------|------|------|
| 1. 任务清单生成 | JSONL格式完整性 | ~7800任务 |
| 2. 批量生成成功率 | 对话生成成功比例 | ≥95% |
| 3. 核心标记唯一性 | `<<核心:...>>`标记数量 | 1-2个 |
| 4. 无占位符残留 | 禁止`[[[CORE`、`{{{`等 | 0个 |
| 5. 中文占比检查 | 非中文语言中文字符占比 | <15% |
| 6. meta.json完整性 | 元数据字段完整性 | 全字段存在 |
| 7. 字数合规性 | 实际字数与目标字数偏差 | ±30% |
| 8. 对话轮次合理性 | 对话轮次和speaker分布 | 10-200轮 |

### 4. 运行FULL版测试

```powershell
# 运行FULL版测试（抽样10个任务验证8项校验）
python tests/test_training_full.py

# 或使用pytest
python -m pytest tests/test_training_full.py -v -s
```

**测试输出示例：**
```
[FULL Test] 步骤1：生成FULL任务清单...
[OK] 生成任务数: 7812
[OK] 语言分布: {"中文": 2340, "英语": 2340, ...}

[FULL Test] 步骤2：批量生成对话（抽样10个任务）...
[OK] 生成的txt文件: 10
[OK] 生成的meta文件: 10

[FULL Test] 步骤3：验证核心标记...
[OK] 医疗健康-01_500_2_3914250785.txt: 核心标记 x1

...（8项校验全部通过）

测试结果: 8 通过, 0 失败
```

### 5. FULL版与MVP版对比

| 特性 | MVP版 | FULL版 |
|------|-------|--------|
| 场景数量 | 每职业5个 | 每职业30个 |
| 语言覆盖 | 中英2语言 | 中英日+6语言（9种） |
| 任务总数 | 390 | ~7800 |
| 生成时间 | 30-60分钟 | 10-15小时 |
| 硬校验 | 6项 | 8项 |
| 推荐用途 | 快速测试验证 | 正式训练数据集 |

---

## 八、自动化测试

### 1. Smoke Test（快速验证 - MVP版）

```powershell
# 运行smoke test（390任务，6项校验）
python tests/test_training_pipeline_smoke.py

# 或使用pytest
python -m pytest tests/test_training_pipeline_smoke.py -v -s
```

**测试覆盖：**
- 任务生成（JSONL格式）
- 批量生成（抽样4个任务）
- 6项硬校验：核心标记、占位符、中文占比、meta.json完整性等

### 2. FULL Test（完整验证 - FULL版）

```powershell
# 运行FULL版测试（~7800任务，8项校验）
python tests/test_training_full.py

# 或使用pytest
python -m pytest tests/test_training_full.py -v -s
```

**测试覆盖：**
- 任务生成（~7800任务，9语言全覆盖）
- 批量生成（抽样10个任务）
- **8项硬校验**（新增2项）：
  1. ✅ 任务清单生成
  2. ✅ 批量生成成功率
  3. ✅ 核心标记唯一性
  4. ✅ 无占位符残留
  5. ✅ 中文占比检查
  6. ✅ meta.json完整性
  7. ✅ **字数合规性**（新增：±30%容忍度）
  8. ✅ **对话轮次合理性**（新增：10-200轮，speaker分布平衡）

### 3. 回归测试（全量验证）

```powershell
# MVP版：生成全部390任务并验证
python -m training.run_training_generation_mvp --jobs training/data/training_jobs_mvp.jsonl --out_dir output/training/mvp

# FULL版：生成全部~7800任务并验证（约10-15小时）
python -m training.run_training_generation_mvp --jobs training/data/training_jobs_full.jsonl --out_dir output/training/full

# 检查成功率（应 >95%）
# 查看 [MVP批量生成] 成功: XXX (XX.X%)
```

### 4. 测试策略建议

| 开发阶段 | 推荐测试 | 耗时 | 说明 |
|---------|---------|------|------|
| 快速验证 | Smoke Test | 1-2分钟 | 验证基本功能 |
| 功能开发 | FULL Test | 3-5分钟 | 验证8项校验 |
| 发布前 | 回归测试（MVP） | 30-60分钟 | 全量390任务 |
| 正式训练 | 回归测试（FULL） | 10-15小时 | 全量7800任务 |

---

## 九、下一步计划

### 短期（1-2周）：
- ✅ A1: domain_kb接入（已完成）
- ✅ A2: build_training_jobs_mvp（已完成）
- ✅ A3: run_training_generation_mvp（已完成）
- ✅ A4: README + smoke test（已完成）

### 中期（2-4周）：
- B1: 扩展domain_kb到13个职业
- B2: 修复V2生成器编码问题并启用
- B3: 实现template_bank抽取（build_template_bank.py）
- B4: server.py接入template_bank运行时消费

### 长期（1-2月）：
- C1: 完整版任务生成（全30场景×9语言~7800任务）
- C2: 长文本（10000字）质量优化
- C3: 多人对话（5-10人）参与度优化
- C4: 生成语料质量自动评估系统

---

## 十、联系与反馈

**技术支持：**
- 查看 `demo/使用说明.md` 了解系统架构
- 查看 `demo/domain_kb_integration_verification.md` 了解domain_kb验证方法
- 查看 `demo/训练系统_当前状态与下一步.md` 了解最新进展

**问题反馈：**
- 失败任务记录在 `output/training/mvp/_failed.jsonl`
- 运行日志包含详细错误信息和重试记录

---

**MVP系统已就绪，开始生成训练数据！**🚀


