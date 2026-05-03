# 4个独立场景对话质量修复 - 实施报告

## 【结论】
已创建角色卡系统、校验器和验证脚本，但现有对话生成器（server.py）尚未集成角色卡，导致生成内容仍包含禁止短语和占位符。需要修改server.py中的`_generate_cast`和`_generate_structured_dialogue`函数以强制使用角色卡。

## 【已完成的文件】

### 1. training/role_cards.py ✅
- 为4个场景定义了完整的角色卡
- 场景1：Tim(CEO) / 张秘书(CEO办公室首席助理) / 李总监(增长部负责人)
- 场景2：M(风控负责人) / 王经理(产品经理) / 陈律师(法务负责人)
- 场景3：Yoki(保险销售) / 刘总(客户战略负责人) / 赵经理(客户财务负责人)
- 场景4：KK(咨询师) / 来访者 / 督导(同侪督导咨询师)
- 定义了全局禁止短语列表

### 2. training/dialogue_validators.py ✅
- 实现了完整的对话校验器
- 校验项：
  - 角色校验：禁止"Speaker 1/2/3"、"对话方"、"第三方顾问"等占位符
  - 人称校验：每个speaker必须使用第一人称"我"
  - 场景词覆盖：检查关键场景词是否出现
  - 跑题检测：禁止KPI/ERP/ROI等跑题词
  - 场景4特殊检测：禁止医疗问诊词（血常规/CT/心电图等）

### 3. training/scene_dialogue_enhancer.py ✅
- 场景专用提示词构建
- 场景对话骨架模板
- 禁止短语检查函数
- 角色名称应用函数

### 4. training/run_scene_dialogue_regression.py ✅
- 完整的回归测试脚本
- 自动生成对话并运行校验
- 生成校验报告和汇总报告

## 【当前问题】

### 问题1：现有生成器未集成角色卡
- `server.py`中的`_generate_cast`函数仍在使用旧的动态角色生成逻辑
- 生成的角色名称仍然是"对话方"、"第三方顾问"等占位符
- 需要修改`_generate_cast`以强制使用角色卡中的真实身份

### 问题2：禁止短语仍在生成
- `_generate_structured_dialogue`函数使用的模板仍包含禁止短语
- 如"方案1"、"方案2"、"准备材料"、"提交申请"等
- 需要在生成前进行hard ban检查

### 问题3：场景4仍出现医疗问诊词
- 场景4被错误识别为ERP销售场景
- 生成了"血常规"、"CT"等医疗问诊词
- 需要修正场景识别逻辑

## 【需要修改的代码位置】

### 1. server.py - _generate_cast函数（约2014行）
```python
# 需要添加：检测是否为4个独立场景，如果是，使用角色卡
from training.role_cards import get_role_cards, SCENARIO_ROLE_MAP

def _generate_cast(profile: dict, scenario: str, people: int, language: str = "中文") -> dict:
    # 检测场景ID（从scenario或profile中提取）
    scenario_id = detect_scenario_id(scenario, profile)
    
    if scenario_id in SCENARIO_ROLE_MAP:
        # 使用角色卡
        role_cards = get_role_cards(scenario_id)
        owner = {
            "name": role_cards[0].name,
            "role": role_cards[0].identity,
            "speaking_style": role_cards[0].speaking_style
        }
        others = [
            {
                "name": role.name,
                "role": role.identity,
                "speaking_style": role.speaking_style
            }
            for role in role_cards[1:]
        ]
        return {"owner": owner, "others": others}
    else:
        # 原有逻辑
        ...
```

### 2. server.py - _generate_structured_dialogue函数（约2236行）
```python
# 需要添加：禁止短语检查
from training.scene_dialogue_enhancer import check_forbidden_phrases, get_all_forbidden_phrases

def _generate_structured_dialogue(...):
    # 在生成前检查禁止短语
    scenario_id = detect_scenario_id(scenario, profile)
    forbidden = get_all_forbidden_phrases(scenario_id)
    
    # 在prompt中明确禁止这些短语
    forbidden_instruction = f"\n【严格禁止】以下短语不得出现在对话中：{', '.join(forbidden[:20])}"
    
    # 在生成后检查
    # 如果包含禁止短语，触发重写
```

### 3. server.py - 场景识别逻辑
```python
# 需要修正场景4的识别
# 当前被识别为sales_consultation，应该识别为psychology_consultation
```

## 【验证结果】

运行`python training/run_scene_dialogue_regression.py`的结果：
- 对话生成成功: 0/4（因为校验失败）
- 校验通过: 0/4
- 主要错误：
  - 角色占位符（"对话方"、"第三方顾问"）
  - 禁止短语（"方案1"、"方案2"、"准备材料"等）
  - 场景4出现医疗问诊词（"血常规"）

## 【下一步行动】

1. **修改server.py集成角色卡**（优先级：P0）
   - 修改`_generate_cast`函数
   - 修改`_generate_structured_dialogue`函数
   - 添加场景ID检测逻辑

2. **添加禁止短语hard ban**（优先级：P0）
   - 在生成前检查prompt
   - 在生成后检查输出
   - 触发重写机制

3. **修正场景识别**（优先级：P1）
   - 修正场景4的识别逻辑
   - 确保场景4使用心理咨询模板而非ERP销售模板

## 【文件清单】

已创建的文件：
- ✅ `training/role_cards.py` - 角色卡定义
- ✅ `training/dialogue_validators.py` - 校验器
- ✅ `training/scene_dialogue_enhancer.py` - 场景增强器
- ✅ `training/run_scene_dialogue_regression.py` - 验证脚本

需要修改的文件：
- ⚠️ `server.py` - 集成角色卡和禁止短语检查

## 【命令】

运行验证脚本：
```bash
python training/run_scene_dialogue_regression.py
```

输出目录：
- `training/output/scenario{n}_dialogue.txt` - 对话文本
- `training/output/scenario{n}_validator_report.json` - 校验报告
- `training/output/regression_summary.json` - 汇总报告
