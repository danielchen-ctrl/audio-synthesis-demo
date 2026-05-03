# -*- coding: utf-8 -*-
"""
训练方案 v2 数据定义
=====================
包含：
- 21 个手动主题（MANUAL_TOPICS）
- 22 个预置模板（PRESET_TEMPLATES）
- 正配对关系（POSITIVE_PAIRS，22 组）
- B4 高风险非正配对（B4_RISK_PAIRINGS，105 组）
- B5 精选组合（B5_EXTREME_COMBOS，66 组）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ─────────────────────────────────────────────
# 手动主题（21 条）
# ─────────────────────────────────────────────
@dataclass
class ManualTopic:
    topic_id: str           # 唯一 ID，用于任务生成
    topic_cn: str           # 中文主题描述
    roles_cn: List[str]     # 可参与角色
    keywords: List[str]     # 主题关键词


MANUAL_TOPICS: List[ManualTopic] = [
    ManualTopic(
        topic_id="m01_hypertension_followup",
        topic_cn="高血压患者复诊后的用药和生活习惯随访沟通",
        roles_cn=["全科医生", "慢病管理护士", "患者本人", "家属", "健康管理师"],
        keywords=["高血压", "复诊", "用药", "生活习惯", "随访"],
    ),
    ManualTopic(
        topic_id="m02_ops_recruitment",
        topic_cn="运营岗位离职后紧急补岗的招聘进度沟通",
        roles_cn=["HRBP", "招聘专员", "用人部门负责人", "运营经理", "候选人"],
        keywords=["运营岗", "离职", "补岗", "招聘进度", "面试"],
    ),
    ManualTopic(
        topic_id="m03_celebrity_endorsement",
        topic_cn="某艺人下季度品牌代言和商务合作机会讨论",
        roles_cn=["经纪人", "商务负责人", "品牌市场经理", "艺人统筹", "法务"],
        keywords=["艺人", "品牌代言", "商务合作", "档期", "报价"],
    ),
    ManualTopic(
        topic_id="m04_project_delivery",
        topic_cn="工程项目临近交付前的进度风险和验收安排讨论",
        roles_cn=["项目经理", "工程总监", "施工负责人", "监理", "甲方代表"],
        keywords=["工程交付", "进度风险", "验收", "延期", "现场协调"],
    ),
    ManualTopic(
        topic_id="m05_ev_launch",
        topic_cn="新能源车型上市前的区域投放和销售策略讨论",
        roles_cn=["产品经理", "区域销售经理", "市场经理", "经销商负责人", "运营分析师"],
        keywords=["新能源车", "上市", "区域投放", "销售策略", "渠道"],
    ),
    ManualTopic(
        topic_id="m06_consulting_expand",
        topic_cn="面向制造业客户的新咨询项目拓展沟通",
        roles_cn=["咨询顾问", "客户经理", "合伙人", "行业专家", "售前顾问"],
        keywords=["制造业客户", "咨询项目", "客户拓展", "需求诊断", "商机"],
    ),
    ManualTopic(
        topic_id="m07_legal_retainer",
        topic_cn="企业年度法律顾问专项服务内容和交付安排讨论",
        roles_cn=["法务经理", "外部律师", "企业负责人", "合同专员", "合规顾问"],
        keywords=["法律顾问", "专项服务", "合同审查", "合规", "交付"],
    ),
    ManualTopic(
        topic_id="m08_wealth_management",
        topic_cn="中高净值客户年度资产配置方案沟通",
        roles_cn=["理财顾问", "投资经理", "私人银行顾问", "客户本人", "风控顾问"],
        keywords=["高净值客户", "资产配置", "风险偏好", "收益目标", "投资组合"],
    ),
    ManualTopic(
        topic_id="m09_member_repurchase",
        topic_cn="提升老会员复购率的运营活动方案讨论",
        roles_cn=["会员运营", "门店店长", "数据分析师", "市场经理", "客服主管"],
        keywords=["会员运营", "复购率", "优惠券", "用户分层", "活动方案"],
    ),
    ManualTopic(
        topic_id="m10_insurance_qc",
        topic_cn="保险销售录音中的话术合规和质检问题复盘",
        roles_cn=["质检专员", "保险顾问", "销售主管", "合规经理", "培训讲师"],
        keywords=["保险销售", "录音质检", "话术合规", "风险提示", "整改"],
    ),
    ManualTopic(
        topic_id="m11_realestate_destock",
        topic_cn="新楼盘库存去化压力和渠道促销策略讨论",
        roles_cn=["项目营销总", "置业顾问", "渠道经理", "策划经理", "案场经理"],
        keywords=["楼盘去化", "库存压力", "渠道分销", "促销", "成交转化"],
    ),
    ManualTopic(
        topic_id="m12_ai_paid_conversion",
        topic_cn="AI产品免费用户向付费会员转化方案讨论",
        roles_cn=["产品经理", "增长运营", "数据分析师", "用户研究员", "客服负责人"],
        keywords=["AI产品", "免费用户", "付费会员", "转化率", "订阅"],
    ),
    ManualTopic(
        topic_id="m13_production_efficiency",
        topic_cn="生产线效率提升和瓶颈工序优化会议讨论",
        roles_cn=["生产主管", "工艺工程师", "设备工程师", "质量工程师", "厂长"],
        keywords=["产线效率", "瓶颈工序", "良品率", "设备稼动率", "提效"],
    ),
    ManualTopic(
        topic_id="m14_content_weekly",
        topic_cn="内容平台本周增长数据和商业化策略周会",
        roles_cn=["内容运营", "增长负责人", "商业化负责人", "数据分析师", "产品经理"],
        keywords=["内容平台", "增长数据", "商业化", "战略周会", "复盘"],
    ),
    ManualTopic(
        topic_id="m15_ad_compliance",
        topic_cn="新广告投放素材的合规风险审核讨论",
        roles_cn=["法务", "广告投放经理", "品牌经理", "合规专员", "内容审核员"],
        keywords=["广告素材", "合规审核", "宣传用语", "监管要求", "风险"],
    ),
    ManualTopic(
        topic_id="m16_insurance_sales_insight",
        topic_cn="保险产品销售转化数据和客户异议洞察分析",
        roles_cn=["销售经理", "保险顾问", "数据分析师", "培训负责人", "产品经理"],
        keywords=["保险产品", "销售转化", "客户异议", "销售洞察", "成交原因"],
    ),
    ManualTopic(
        topic_id="m17_payment_integration",
        topic_cn="支付项目上线前的接入联调、下单回调和主流程验收讨论",
        roles_cn=["测试负责人", "测试工程师", "后端开发", "支付研发", "第三方支付对接人", "产品经理", "项目经理"],
        keywords=["支付接入", "第三方支付", "下单", "支付回调", "状态同步", "联调验收", "签名校验"],
    ),
    ManualTopic(
        topic_id="m18_payment_risk_reconciliation",
        topic_cn="支付系统上线前的退款安全、对账差错和稳定性准入评估",
        roles_cn=["测试负责人", "测试工程师", "风控工程师", "财务对账专员", "后端开发", "SRE", "架构师"],
        keywords=["退款安全", "重复退款", "越权", "支付对账", "金额不一致", "压测", "准入评估", "资金安全"],
    ),
    ManualTopic(
        topic_id="m19_moments_publish",
        topic_cn="朋友圈动态发布、图文内容发布和多端分发一致性测试讨论",
        roles_cn=["测试工程师", "客户端开发", "前端开发", "小程序开发", "后端开发", "产品经理", "内容运营"],
        keywords=["朋友圈", "动态发布", "图文发布", "多端分发", "App", "Web", "小程序", "状态同步", "发布失败"],
    ),
    ManualTopic(
        topic_id="m20_moments_interaction",
        topic_cn="朋友圈点赞评论、互动计数和多端状态一致性测试讨论",
        roles_cn=["测试工程师", "客户端开发", "后端开发", "产品经理", "数据工程师"],
        keywords=["点赞", "评论", "互动计数", "多端展示", "状态回显", "重复点击", "并发互动", "数据一致"],
    ),
    ManualTopic(
        topic_id="m21_moments_privacy",
        topic_cn="朋友圈隐私可见范围、内容审核和权限控制测试讨论",
        roles_cn=["测试工程师", "隐私合规专员", "内容审核员", "风控策略", "算法工程师", "后端开发", "产品经理"],
        keywords=["隐私可见", "好友可见", "分组可见", "权限校验", "敏感词", "图片审核", "违规内容", "审核拦截"],
    ),
]


# ─────────────────────────────────────────────
# 预置模板（22 条）
# ─────────────────────────────────────────────
@dataclass
class PresetTemplate:
    template_id: str
    name_cn: str            # 模板名称（如"医疗健康｜慢病随访"）
    industry: str           # 行业分类
    scenario_cn: str        # 场景描述（用作 scenario 字段）
    core_content_cn: str    # 核心内容（用作 core_content 字段）
    roles_cn: List[str]     # 推荐角色列表
    must_keywords: List[str]
    soft_keywords: List[str]
    forbidden_keywords: List[str] = field(default_factory=list)


PRESET_TEMPLATES: List[PresetTemplate] = [
    PresetTemplate(
        template_id="t01_medical_chronic",
        name_cn="医疗健康｜慢病随访",
        industry="医疗健康",
        scenario_cn="慢病患者定期随访沟通，医生、护士与患者及家属共同回顾近期健康指标、用药依从情况和生活方式调整效果，制定下一阶段健康管理计划。",
        core_content_cn="回顾血压血糖等近期指标变化，确认用药依从性问题，讨论生活方式干预建议，明确随访频率和下次检查计划，识别高风险信号并制定应对预案。",
        roles_cn=["全科医生", "慢病管理护士", "健康管理师", "患者本人", "患者家属"],
        must_keywords=["慢病", "随访", "用药", "血压", "血糖", "复诊", "生活方式"],
        soft_keywords=["风险预警", "健康干预", "指标异常", "随访计划", "依从性"],
        forbidden_keywords=["支付回调", "幂等", "压测", "楼盘去化", "广告极限词", "代言费", "ROI评估"],
    ),
    PresetTemplate(
        template_id="t02_hr_recruitment",
        name_cn="人力资源与招聘｜招聘补岗",
        industry="人力资源与招聘",
        scenario_cn="某岗位员工突然离职，用人部门紧急启动补岗需求，HRBP与招聘专员对齐岗位要求、候选人筛选进度和面试安排，确保到岗时间可控。",
        core_content_cn="明确岗位空缺紧急程度和HC来源，同步当前候选人漏斗状态，讨论面试流程加速方案，确认offer审批链路，对齐最晚到岗时间节点。",
        roles_cn=["HRBP", "招聘专员", "用人部门负责人", "部门经理", "候选人"],
        must_keywords=["岗位空缺", "补岗", "候选人", "面试", "到岗", "招聘进度"],
        soft_keywords=["HC申请", "紧急招聘", "offer沟通", "用人部门", "人才库"],
        forbidden_keywords=["支付回调", "幂等", "代言费", "楼盘去化", "医嘱", "压测"],
    ),
    PresetTemplate(
        template_id="t03_entertainment_celebrity",
        name_cn="娱乐/媒体｜艺人商业化",
        industry="娱乐/媒体",
        scenario_cn="艺人经纪团队与品牌方就下季度代言合作展开商务洽谈，讨论合作权益、报价体系、档期安排和宣发资源匹配。",
        core_content_cn="明确品牌诉求与艺人粉丝画像的匹配度，讨论代言费报价区间和权益清单，确认档期冲突和宣发资源投入，对齐合同核心条款和法务审核节点。",
        roles_cn=["经纪人", "商务负责人", "品牌市场经理", "艺人统筹", "法务"],
        must_keywords=["艺人", "品牌代言", "商务合作", "档期", "报价", "宣发"],
        soft_keywords=["粉丝画像", "商业价值", "合作权益", "曝光量"],
        forbidden_keywords=["支付回调", "幂等", "压测", "楼盘去化", "血压", "随访", "工序"],
    ),
    PresetTemplate(
        template_id="t04_engineering_delivery",
        name_cn="建筑与工程行业｜项目交付",
        industry="建筑与工程行业",
        scenario_cn="工程项目进入交付冲刺阶段，项目经理与施工负责人、监理和甲方代表召开交付协调会，梳理剩余工作量、风险点和验收安排。",
        core_content_cn="盘点当前进度与交付节点差距，识别关键路径上的阻塞项，讨论延期风险和赶工方案，确认验收标准和竣工验收流程，明确各方责任分工。",
        roles_cn=["项目经理", "工程总监", "施工负责人", "监理", "甲方代表"],
        must_keywords=["工程进度", "交付节点", "验收", "延期", "施工质量", "现场协调"],
        soft_keywords=["成本控制", "分包管理", "材料到货", "竣工验收"],
        forbidden_keywords=["支付回调", "幂等", "压测", "代言费", "血压", "随访", "广告极限词"],
    ),
    PresetTemplate(
        template_id="t05_auto_launch",
        name_cn="汽车行业｜车型投放",
        industry="汽车行业",
        scenario_cn="新车型即将上市，产品、销售和市场团队召开区域投放策略会，讨论渠道铺货节奏、竞品应对和区域差异化策略。",
        core_content_cn="明确各区域投放优先级和铺货时间表，分析主要竞品定价和配置差异，讨论试驾转化提升方案，对齐促销政策和经销商激励方案，确认销售目标分解。",
        roles_cn=["产品经理", "区域销售经理", "市场经理", "经销商负责人", "运营分析师"],
        must_keywords=["新车上市", "车型", "投放", "渠道", "销售目标", "竞品", "区域策略"],
        soft_keywords=["用户画像", "试驾转化", "价格策略", "经销商激励"],
        forbidden_keywords=["支付回调", "幂等", "随访", "血压", "广告极限词", "代言费"],
    ),
    PresetTemplate(
        template_id="t06_consulting_expansion",
        name_cn="咨询/专业服务｜客户拓展",
        industry="咨询/专业服务",
        scenario_cn="咨询团队就某潜在客户的新项目机会展开内部拓展讨论，分析客户需求、决策链路和竞争态势，制定拜访和提案策略。",
        core_content_cn="梳理客户业务痛点和采购决策链，分析现有竞争格局，讨论差异化价值主张，制定首次拜访议程和提案框架，明确跟进时间节点和负责人。",
        roles_cn=["咨询顾问", "客户经理", "合伙人", "行业专家", "售前顾问"],
        must_keywords=["客户线索", "商机", "需求诊断", "方案建议", "客户拜访", "合作机会"],
        soft_keywords=["决策链路", "行业痛点", "转化跟进", "项目报价"],
        forbidden_keywords=["支付回调", "幂等", "压测", "随访", "血压", "代言费"],
    ),
    PresetTemplate(
        template_id="t07_legal_retainer",
        name_cn="法律服务｜法顾专项",
        industry="法律服务",
        scenario_cn="企业法务负责人与外部律师就年度法律顾问专项服务的内容范围、交付安排和重点事项展开工作会谈。",
        core_content_cn="明确专项服务覆盖范围和优先级，讨论合同审查、合规咨询和风险提示的交付节点，梳理已识别的法律风险和处理方案，确认服务边界和响应时效。",
        roles_cn=["法务经理", "外部律师", "企业负责人", "合同专员", "合规顾问"],
        must_keywords=["法律顾问", "专项服务", "合同审查", "合规", "法律风险", "交付"],
        soft_keywords=["服务边界", "法律意见", "争议处理", "客户需求"],
        forbidden_keywords=["支付回调", "幂等", "压测", "楼盘去化", "血压", "代言费", "产线"],
    ),
    PresetTemplate(
        template_id="t08_wealth_allocation",
        name_cn="金融/投资｜资产配置",
        industry="金融/投资",
        scenario_cn="理财顾问与高净值客户就年度资产配置方案进行深度沟通，回顾过去一年收益情况，根据市场环境变化和客户风险偏好调整投资组合。",
        core_content_cn="回顾当前持仓表现和风险暴露，分析客户风险承受能力变化，讨论各资产类别的配置调整方案，制定再平衡计划，明确流动性管理安排和下次复盘时间。",
        roles_cn=["理财顾问", "投资经理", "私人银行顾问", "客户本人", "风控顾问"],
        must_keywords=["资产配置", "投资组合", "风险偏好", "收益目标", "市场波动", "再平衡"],
        soft_keywords=["基金配置", "股票债券", "流动性管理", "长期规划"],
        forbidden_keywords=["支付回调", "幂等", "压测", "随访", "代言费", "楼盘去化", "产线"],
    ),
    PresetTemplate(
        template_id="t09_retail_repurchase",
        name_cn="零售行业｜会员复购",
        industry="零售行业",
        scenario_cn="零售品牌会员运营团队讨论如何提升老会员复购率，制定针对沉睡用户的唤醒活动方案，优化积分权益体系。",
        core_content_cn="分析当前复购率趋势和用户分层数据，识别沉睡会员特征，讨论优惠券和积分权益设计方案，制定私域触达策略，确认活动预算和效果追踪指标。",
        roles_cn=["会员运营", "门店店长", "数据分析师", "市场经理", "客服主管"],
        must_keywords=["会员运营", "复购率", "用户分层", "优惠券", "积分权益", "沉睡唤醒"],
        soft_keywords=["私域触达", "客单价", "消费频次", "复购转化"],
        forbidden_keywords=["支付回调", "幂等", "压测", "随访", "代言费", "工程验收", "产线"],
    ),
    PresetTemplate(
        template_id="t10_insurance_qc",
        name_cn="保险行业｜保险质检",
        industry="保险行业",
        scenario_cn="保险公司质检专员与销售主管就近期销售录音的话术合规问题进行复盘，讨论违规判定标准和整改建议。",
        core_content_cn="回顾典型质检案例中的合规问题，明确违规话术类型和判定依据，讨论风险提示和客户确认环节的标准化要求，制定培训整改计划，更新质检规则。",
        roles_cn=["质检专员", "保险顾问", "销售主管", "合规经理", "培训讲师"],
        must_keywords=["话术合规", "销售录音", "质检", "违规", "风险提示", "整改"],
        soft_keywords=["误导销售", "客户确认", "保单说明", "回访检查"],
        forbidden_keywords=["支付回调", "幂等", "压测", "代言费", "楼盘去化", "血压", "产线"],
    ),
    PresetTemplate(
        template_id="t11_realestate_destock",
        name_cn="房地产｜项目去化",
        industry="房地产",
        scenario_cn="楼盘销售团队就当前库存去化压力召开策略会，讨论渠道分销方案优化、促销政策调整和客户到访转化提升措施。",
        core_content_cn="分析当前去化率和库存结构，讨论渠道佣金和分销商激励方案，制定近期促销政策，优化客户到访和认购转化流程，明确各渠道的周度任务目标。",
        roles_cn=["项目营销总", "置业顾问", "渠道经理", "策划经理", "案场经理"],
        must_keywords=["去化率", "楼盘销售", "库存", "成交转化", "渠道分销", "促销"],
        soft_keywords=["客户到访", "认购签约", "竞品楼盘", "价格策略"],
        forbidden_keywords=["支付回调", "幂等", "压测", "代言费", "血压", "随访", "产线"],
    ),
    PresetTemplate(
        template_id="t12_ai_paid_conversion",
        name_cn="人工智能/科技｜付费转化",
        industry="人工智能/科技",
        scenario_cn="AI产品团队讨论免费用户向付费订阅转化的提升方案，分析转化漏斗数据，优化付费引导路径和权益说明。",
        core_content_cn="分析当前免费到付费的转化漏斗各环节流失原因，讨论功能触达和价值感知提升方案，优化价格套餐和权益说明，制定转化实验计划和追踪指标。",
        roles_cn=["产品经理", "增长运营", "数据分析师", "用户研究员", "客服负责人"],
        must_keywords=["免费试用", "订阅转化", "付费", "转化漏斗", "功能触达", "权益"],
        soft_keywords=["用户留存", "付费意愿", "价格套餐", "增值服务"],
        forbidden_keywords=["支付回调", "幂等", "压测", "代言费", "楼盘去化", "血压", "产线"],
    ),
    PresetTemplate(
        template_id="t13_manufacturing_efficiency",
        name_cn="制造业｜产线提效",
        industry="制造业",
        scenario_cn="工厂生产团队就产线效率提升和瓶颈工序优化召开专题会议，分析设备稼动率数据，讨论自动化改造方案。",
        core_content_cn="盘点主要瓶颈工序和停机原因，分析设备稼动率和良品率数据，讨论工序优化和自动化改造方案，制定近期排产计划调整方案，确认提效目标和考核指标。",
        roles_cn=["生产主管", "工艺工程师", "设备工程师", "质量工程师", "厂长"],
        must_keywords=["产线效率", "设备稼动率", "瓶颈工序", "良品率", "自动化", "产能"],
        soft_keywords=["工时优化", "排产计划", "异常停机", "降本增效"],
        forbidden_keywords=["支付回调", "幂等", "压测", "代言费", "楼盘去化", "血压", "随访"],
    ),
    PresetTemplate(
        template_id="t14_media_weekly",
        name_cn="娱乐/媒体｜战略周会",
        industry="娱乐/媒体",
        scenario_cn="内容平台核心团队召开周度战略会议，复盘本周增长数据和内容表现，讨论商业化进展和下周重点工作安排。",
        core_content_cn="回顾本周用户增长、内容消费和商业化关键指标，识别数据异常和风险事项，讨论重点项目进展，协调各团队资源，明确下周优先级和目标。",
        roles_cn=["内容运营", "增长负责人", "商业化负责人", "数据分析师", "产品经理"],
        must_keywords=["内容策略", "平台增长", "商业化", "数据复盘", "战略目标", "重点项目"],
        soft_keywords=["用户增长", "资源协调", "风险事项", "下周计划"],
        forbidden_keywords=["支付回调", "幂等", "压测", "楼盘去化", "血压", "随访", "产线"],
    ),
    PresetTemplate(
        template_id="t15_legal_ad_compliance",
        name_cn="法律服务｜广告合规",
        industry="法律服务",
        scenario_cn="品牌方法务与广告投放团队就新一批投放素材的合规风险进行审核讨论，识别极限词和违规宣传风险。",
        core_content_cn="逐项审查投放素材中的宣传用语合规性，识别极限词和误导性表述，讨论整改建议，明确监管要求和资质证明提交节点，确认投放时间表调整方案。",
        roles_cn=["法务", "广告投放经理", "品牌经理", "合规专员", "内容审核员"],
        must_keywords=["广告审查", "合规风险", "宣传用语", "极限词", "误导宣传", "整改"],
        soft_keywords=["资质要求", "法务审核", "监管要求", "投放素材"],
        forbidden_keywords=["支付回调", "幂等", "压测", "楼盘去化", "血压", "随访", "产线", "代言费"],
    ),
    PresetTemplate(
        template_id="t16_insurance_sales_insight",
        name_cn="保险行业｜销售洞察",
        industry="保险行业",
        scenario_cn="保险销售团队通过数据分析复盘本期产品销售表现，分析客户成交和拒保原因，提炼话术改进建议。",
        core_content_cn="分析本期各产品线成交数据和拒保率，梳理主要客户异议类型和处理话术，讨论高转化渠道特征，制定下期销售重点和培训计划，明确数据追踪维度。",
        roles_cn=["销售经理", "保险顾问", "数据分析师", "培训负责人", "产品经理"],
        must_keywords=["销售线索", "成交原因", "拒保", "异议处理", "转化路径", "渠道表现"],
        soft_keywords=["客户画像", "产品匹配", "保费贡献", "销售话术"],
        forbidden_keywords=["支付回调", "幂等", "压测", "代言费", "楼盘去化", "血压", "产线"],
    ),
    PresetTemplate(
        template_id="t17_payment_integration",
        name_cn="测试开发｜支付接入与交易链路",
        industry="测试开发",
        scenario_cn="支付功能上线前，测试团队与研发和第三方支付对接人共同评审接入联调方案，验证下单、支付回调和状态同步的主流程。",
        core_content_cn="确认第三方支付渠道配置和证书签名，验证下单接口参数和订单创建逻辑，测试支付回调和异步通知的幂等处理，明确沙箱验证结果和上线门禁标准。",
        roles_cn=["测试负责人", "测试工程师", "后端开发", "支付研发", "第三方支付对接人", "产品经理", "项目经理"],
        must_keywords=["支付接入", "第三方支付", "接口联调", "参数签名", "下单接口", "支付回调", "状态同步", "幂等"],
        soft_keywords=["支付网关", "渠道配置", "沙箱环境", "证书配置", "异步通知"],
        forbidden_keywords=["楼盘去化", "血压", "随访", "代言费", "极限词", "产线", "资产配置"],
    ),
    PresetTemplate(
        template_id="t18_payment_refund_security",
        name_cn="测试开发｜退款与资金安全",
        industry="测试开发",
        scenario_cn="支付系统上线前，测试团队与风控和财务就退款安全性进行专项评审，覆盖重复退款、越权退款和资金安全风险。",
        core_content_cn="验证退款申请和审核流程的权限控制，测试重复退款和金额越界场景，确认风控拦截规则和退款状态同步机制，明确异常退款的人工干预流程和资金安全兜底方案。",
        roles_cn=["测试工程师", "风控工程师", "后端开发", "财务", "产品经理", "支付研发"],
        must_keywords=["退款", "重复退款", "越权退款", "金额校验", "风控拦截", "资金安全", "退款状态"],
        soft_keywords=["原路退回", "退款审核", "退款回调", "异常退款", "权限校验"],
        forbidden_keywords=["楼盘去化", "血压", "随访", "代言费", "极限词", "产线", "资产配置"],
    ),
    PresetTemplate(
        template_id="t19_payment_reconciliation",
        name_cn="测试开发｜对账与稳定性准入",
        industry="测试开发",
        scenario_cn="支付系统上线前，测试团队与财务、SRE和架构师就对账准确性和系统稳定性进行准入评估，明确发布门禁标准。",
        core_content_cn="核查交易流水和渠道账单的差错处理机制，确认漏单和多单场景的补偿逻辑，评审容量和性能基线数据，讨论熔断限流策略，确定稳定性准入标准和发布门禁。",
        roles_cn=["性能测试工程师", "测试工程师", "财务对账专员", "后端开发", "SRE", "架构师", "项目负责人"],
        must_keywords=["账单核对", "交易流水", "金额不一致", "漏单", "对账", "差错处理", "稳定性", "发布门禁"],
        soft_keywords=["容量评估", "性能基线", "错误率", "熔断限流", "补偿机制"],
        forbidden_keywords=["楼盘去化", "血压", "随访", "代言费", "极限词", "产线", "资产配置"],
    ),
    PresetTemplate(
        template_id="t20_moments_publish",
        name_cn="测试开发｜朋友圈内容发布与多端分发",
        industry="测试开发",
        scenario_cn="朋友圈内容发布功能测试评审，覆盖动态发布、图文视频处理和 App/Web/小程序多端分发一致性。",
        core_content_cn="验证各类内容发布入口和草稿保存逻辑，测试图片视频上传和内容校验，确认多端分发后的状态同步和数据一致性，明确发布失败的错误处理和重试机制。",
        roles_cn=["测试工程师", "客户端开发", "前端开发", "小程序开发", "后端开发", "产品经理", "内容运营"],
        must_keywords=["动态发布", "内容流", "发布入口", "图片视频", "多端同步", "状态一致", "发布失败"],
        soft_keywords=["草稿保存", "内容校验", "消息分发", "数据同步", "App端", "Web端", "小程序端"],
        forbidden_keywords=["楼盘去化", "血压", "随访", "代言费", "极限词", "产线", "资产配置", "支付回调"],
    ),
    PresetTemplate(
        template_id="t21_moments_interaction",
        name_cn="测试开发｜社交互动与状态一致性",
        industry="测试开发",
        scenario_cn="朋友圈点赞评论功能测试评审，重点验证互动计数准确性、状态回显和多端展示一致性，覆盖并发和边界场景。",
        core_content_cn="验证点赞和评论的计数准确性和端间一致，测试重复点击和取消操作的幂等性，模拟并发互动场景下的数据正确性，确认互动通知和消息推送逻辑，明确数据刷新策略。",
        roles_cn=["测试工程师", "客户端开发", "后端开发", "产品经理", "数据工程师"],
        must_keywords=["点赞评论", "计数准确", "状态回显", "多端展示", "并发互动", "端间一致"],
        soft_keywords=["取消操作", "重复点击", "互动通知", "数据刷新"],
        forbidden_keywords=["楼盘去化", "血压", "随访", "代言费", "极限词", "产线", "资产配置", "支付回调"],
    ),
    PresetTemplate(
        template_id="t22_moments_privacy",
        name_cn="测试开发｜隐私权限与内容审核",
        industry="测试开发",
        scenario_cn="朋友圈隐私和内容审核功能测试评审，覆盖可见范围权限控制、敏感词检测和违规内容拦截。",
        core_content_cn="验证好友可见、分组可见、仅自己可见等权限控制逻辑，测试黑名单和屏蔽用户场景，确认敏感词和违规图片视频的检测和拦截机制，明确人工复审触发条件和处理流程。",
        roles_cn=["测试工程师", "隐私合规专员", "内容审核员", "风控策略", "算法工程师", "后端开发", "产品经理"],
        must_keywords=["隐私可见", "权限控制", "可见范围", "敏感词检测", "违规内容", "审核拦截"],
        soft_keywords=["好友可见", "分组可见", "黑名单", "图片审核", "人工复审"],
        forbidden_keywords=["楼盘去化", "血压", "随访", "代言费", "极限词", "产线", "资产配置", "支付回调"],
    ),
]

# 快速查找
TEMPLATE_BY_ID: Dict[str, PresetTemplate] = {t.template_id: t for t in PRESET_TEMPLATES}
TOPIC_BY_ID: Dict[str, ManualTopic] = {m.topic_id: m for m in MANUAL_TOPICS}


# ─────────────────────────────────────────────
# 正配对关系（22 组）
# 手动主题 topic_id → 预置模板 template_id(s)
# ─────────────────────────────────────────────
# 注：m18 是"一对二"正配对
POSITIVE_PAIRS: List[Tuple[str, str]] = [
    ("m01_hypertension_followup",       "t01_medical_chronic"),
    ("m02_ops_recruitment",             "t02_hr_recruitment"),
    ("m03_celebrity_endorsement",       "t03_entertainment_celebrity"),
    ("m04_project_delivery",            "t04_engineering_delivery"),
    ("m05_ev_launch",                   "t05_auto_launch"),
    ("m06_consulting_expand",           "t06_consulting_expansion"),
    ("m07_legal_retainer",              "t07_legal_retainer"),
    ("m08_wealth_management",           "t08_wealth_allocation"),
    ("m09_member_repurchase",           "t09_retail_repurchase"),
    ("m10_insurance_qc",                "t10_insurance_qc"),
    ("m11_realestate_destock",          "t11_realestate_destock"),
    ("m12_ai_paid_conversion",          "t12_ai_paid_conversion"),
    ("m13_production_efficiency",       "t13_manufacturing_efficiency"),
    ("m14_content_weekly",              "t14_media_weekly"),
    ("m15_ad_compliance",               "t15_legal_ad_compliance"),
    ("m16_insurance_sales_insight",     "t16_insurance_sales_insight"),
    ("m17_payment_integration",         "t17_payment_integration"),
    ("m18_payment_risk_reconciliation", "t18_payment_refund_security"),   # 一对二，第一个
    ("m18_payment_risk_reconciliation", "t19_payment_reconciliation"),    # 一对二，第二个
    ("m19_moments_publish",             "t20_moments_publish"),
    ("m20_moments_interaction",         "t21_moments_interaction"),
    ("m21_moments_privacy",             "t22_moments_privacy"),
]


# ─────────────────────────────────────────────
# B4 高风险非正配对（105 组）
# 原则：跨行业强混搭 — 选最容易串味的非本行业模板
# ─────────────────────────────────────────────
B4_RISK_PAIRINGS: List[Tuple[str, str]] = [
    # m01 高血压复诊 → 5个高风险非正配对
    ("m01_hypertension_followup", "t15_legal_ad_compliance"),       # 合规审查口吻容易污染医疗
    ("m01_hypertension_followup", "t10_insurance_qc"),              # 质检/合规话语体系重叠
    ("m01_hypertension_followup", "t08_wealth_allocation"),         # 风险评估语言重叠
    ("m01_hypertension_followup", "t12_ai_paid_conversion"),        # 用户留存/用户激活语言
    ("m01_hypertension_followup", "t22_moments_privacy"),           # 隐私/权限审核口吻

    # m02 运营补岗 → 5个高风险
    ("m02_ops_recruitment",       "t06_consulting_expansion"),      # 商机挖掘和候选人挖掘语言重叠
    ("m02_ops_recruitment",       "t16_insurance_sales_insight"),   # 销售漏斗和招聘漏斗类似
    ("m02_ops_recruitment",       "t12_ai_paid_conversion"),        # 转化率/漏斗语言
    ("m02_ops_recruitment",       "t14_media_weekly"),              # 周会汇报格式容易污染
    ("m02_ops_recruitment",       "t13_manufacturing_efficiency"),  # 效率/产能语言

    # m03 艺人代言 → 5个高风险
    ("m03_celebrity_endorsement", "t15_legal_ad_compliance"),       # 合同/合规最容易串味
    ("m03_celebrity_endorsement", "t08_wealth_allocation"),         # ROI/价值评估语言
    ("m03_celebrity_endorsement", "t06_consulting_expansion"),      # 商务拓展语言类似
    ("m03_celebrity_endorsement", "t09_retail_repurchase"),         # 品牌复购/粉丝忠诚度
    ("m03_celebrity_endorsement", "t12_ai_paid_conversion"),        # 商业化变现语言

    # m04 工程交付验收 → 5个高风险
    ("m04_project_delivery",      "t17_payment_integration"),       # 验收/联调/上线门禁重叠
    ("m04_project_delivery",      "t19_payment_reconciliation"),    # 稳定性准入/验收标准
    ("m04_project_delivery",      "t13_manufacturing_efficiency"),  # 质量/产能/效率语言
    ("m04_project_delivery",      "t06_consulting_expansion"),      # 客户交付/提案语言
    ("m04_project_delivery",      "t07_legal_retainer"),            # 合同/交付义务语言

    # m05 新能源车型投放 → 5个高风险
    ("m05_ev_launch",             "t09_retail_repurchase"),         # 促销/渠道策略重叠
    ("m05_ev_launch",             "t12_ai_paid_conversion"),        # 数字化产品上市语言
    ("m05_ev_launch",             "t11_realestate_destock"),        # 库存/渠道去化类似
    ("m05_ev_launch",             "t06_consulting_expansion"),      # 市场拓展语言
    ("m05_ev_launch",             "t14_media_weekly"),              # 数据复盘/策略周会

    # m06 制造业咨询拓展 → 5个高风险
    ("m06_consulting_expand",     "t13_manufacturing_efficiency"),  # 制造业术语容易反渗
    ("m06_consulting_expand",     "t08_wealth_allocation"),         # 投资/ROI语言
    ("m06_consulting_expand",     "t02_hr_recruitment"),            # 人才引进作为业务拓展
    ("m06_consulting_expand",     "t07_legal_retainer"),            # 专业服务交付重叠
    ("m06_consulting_expand",     "t16_insurance_sales_insight"),   # 销售洞察/商机分析

    # m07 法律顾问专项 → 5个高风险
    ("m07_legal_retainer",        "t15_legal_ad_compliance"),       # 同行业最易串味
    ("m07_legal_retainer",        "t10_insurance_qc"),              # 合规审查流程重叠
    ("m07_legal_retainer",        "t08_wealth_allocation"),         # 金融顾问/法律顾问平行结构
    ("m07_legal_retainer",        "t06_consulting_expansion"),      # 专业服务拓展
    ("m07_legal_retainer",        "t12_ai_paid_conversion"),        # 订阅服务/合同续签

    # m08 高净值资产配置 → 5个高风险
    ("m08_wealth_management",     "t16_insurance_sales_insight"),   # 金融产品销售最易串味
    ("m08_wealth_management",     "t11_realestate_destock"),        # 资产投资/房产渠道
    ("m08_wealth_management",     "t06_consulting_expansion"),      # 专业顾问语言
    ("m08_wealth_management",     "t12_ai_paid_conversion"),        # 产品订阅/价值提案
    ("m08_wealth_management",     "t07_legal_retainer"),            # 风控/合规语言

    # m09 老会员复购 → 5个高风险
    ("m09_member_repurchase",     "t12_ai_paid_conversion"),        # 订阅/升级漏斗极易串
    ("m09_member_repurchase",     "t16_insurance_sales_insight"),   # 客户留存/转化分析
    ("m09_member_repurchase",     "t14_media_weekly"),              # 营销策略复盘
    ("m09_member_repurchase",     "t05_auto_launch"),               # 促销/渠道策略
    ("m09_member_repurchase",     "t11_realestate_destock"),        # 折扣/去化语言

    # m10 保险质检 → 5个高风险
    ("m10_insurance_qc",          "t16_insurance_sales_insight"),   # 同行业最易串味
    ("m10_insurance_qc",          "t15_legal_ad_compliance"),       # 合规审查流程高度重叠
    ("m10_insurance_qc",          "t02_hr_recruitment"),            # 绩效考核类似质检
    ("m10_insurance_qc",          "t22_moments_privacy"),           # 内容审核/质检流程
    ("m10_insurance_qc",          "t14_media_weekly"),              # 数据复盘格式

    # m11 楼盘去化 → 5个高风险
    ("m11_realestate_destock",    "t09_retail_repurchase"),         # 促销/渠道最易串味
    ("m11_realestate_destock",    "t05_auto_launch"),               # 产品上市/库存管理
    ("m11_realestate_destock",    "t08_wealth_allocation"),         # 投资性房产
    ("m11_realestate_destock",    "t16_insurance_sales_insight"),   # 销售分析语言
    ("m11_realestate_destock",    "t06_consulting_expansion"),      # 地产咨询

    # m12 AI付费转化 → 5个高风险
    ("m12_ai_paid_conversion",    "t09_retail_repurchase"),         # 会员订阅极易串
    ("m12_ai_paid_conversion",    "t14_media_weekly"),              # 数据复盘格式
    ("m12_ai_paid_conversion",    "t16_insurance_sales_insight"),   # 转化漏斗/销售洞察
    ("m12_ai_paid_conversion",    "t06_consulting_expansion"),      # B2B商业化语言
    ("m12_ai_paid_conversion",    "t17_payment_integration"),       # 支付/订阅系统

    # m13 产线提效 → 5个高风险
    ("m13_production_efficiency", "t04_engineering_delivery"),      # 项目交付/质量管控
    ("m13_production_efficiency", "t19_payment_reconciliation"),    # 稳定性/性能基线语言
    ("m13_production_efficiency", "t06_consulting_expansion"),      # 咨询客户是制造业
    ("m13_production_efficiency", "t02_hr_recruitment"),            # 人员配置/团队建设
    ("m13_production_efficiency", "t05_auto_launch"),               # 汽车制造业重叠

    # m14 内容平台周会 → 5个高风险
    ("m14_content_weekly",        "t03_entertainment_celebrity"),   # 同行业艺人商业化
    ("m14_content_weekly",        "t12_ai_paid_conversion"),        # 增长/数据分析重叠
    ("m14_content_weekly",        "t09_retail_repurchase"),         # 用户留存/增长
    ("m14_content_weekly",        "t16_insurance_sales_insight"),   # 销售数据复盘
    ("m14_content_weekly",        "t02_hr_recruitment"),            # 团队扩张/内容补岗

    # m15 广告合规审核 → 5个高风险
    ("m15_ad_compliance",         "t07_legal_retainer"),            # 同法律行业最易串
    ("m15_ad_compliance",         "t10_insurance_qc"),              # 合规审查流程极相似
    ("m15_ad_compliance",         "t22_moments_privacy"),           # 内容审核流程重叠
    ("m15_ad_compliance",         "t03_entertainment_celebrity"),   # 品牌内容/宣发策略
    ("m15_ad_compliance",         "t12_ai_paid_conversion"),        # 广告/获客语言

    # m16 保险销售洞察 → 5个高风险
    ("m16_insurance_sales_insight", "t10_insurance_qc"),            # 同行业最易串
    ("m16_insurance_sales_insight", "t08_wealth_allocation"),       # 金融产品销售
    ("m16_insurance_sales_insight", "t09_retail_repurchase"),       # 客户留存转化
    ("m16_insurance_sales_insight", "t12_ai_paid_conversion"),      # 转化漏斗语言
    ("m16_insurance_sales_insight", "t06_consulting_expansion"),    # 销售咨询化

    # m17 支付接入联调 → 5个高风险
    ("m17_payment_integration",   "t18_payment_refund_security"),   # 同支付域最易串
    ("m17_payment_integration",   "t19_payment_reconciliation"),    # 同支付域
    ("m17_payment_integration",   "t21_moments_interaction"),       # 状态同步/回调机制
    ("m17_payment_integration",   "t04_engineering_delivery"),      # 项目验收/上线门禁
    ("m17_payment_integration",   "t12_ai_paid_conversion"),        # 支付产品/订阅

    # m18 支付退款对账准入 → 5个高风险
    ("m18_payment_risk_reconciliation", "t17_payment_integration"),   # 同支付域
    ("m18_payment_risk_reconciliation", "t22_moments_privacy"),       # 风控/权限校验重叠
    ("m18_payment_risk_reconciliation", "t08_wealth_allocation"),     # 金融风险管理
    ("m18_payment_risk_reconciliation", "t07_legal_retainer"),        # 金融合规语言
    ("m18_payment_risk_reconciliation", "t04_engineering_delivery"),  # 验收标准重叠

    # m19 朋友圈内容发布 → 5个高风险
    ("m19_moments_publish",       "t21_moments_interaction"),       # 同微信域最易串
    ("m19_moments_publish",       "t22_moments_privacy"),           # 同微信域
    ("m19_moments_publish",       "t03_entertainment_celebrity"),   # 内容分发/宣发
    ("m19_moments_publish",       "t14_media_weekly"),              # 内容策略复盘
    ("m19_moments_publish",       "t12_ai_paid_conversion"),        # 内容商业化

    # m20 朋友圈互动状态 → 5个高风险
    ("m20_moments_interaction",   "t20_moments_publish"),           # 同微信域最易串
    ("m20_moments_interaction",   "t22_moments_privacy"),           # 同微信域
    ("m20_moments_interaction",   "t17_payment_integration"),       # 状态同步/回调机制
    ("m20_moments_interaction",   "t12_ai_paid_conversion"),        # 用户参与度数据
    ("m20_moments_interaction",   "t14_media_weekly"),              # 互动数据复盘

    # m21 朋友圈隐私权限 → 5个高风险
    ("m21_moments_privacy",       "t21_moments_interaction"),       # 同微信域最易串
    ("m21_moments_privacy",       "t20_moments_publish"),           # 同微信域
    ("m21_moments_privacy",       "t15_legal_ad_compliance"),       # 内容合规审查重叠
    ("m21_moments_privacy",       "t10_insurance_qc"),              # 质检/审核流程
    ("m21_moments_privacy",       "t12_ai_paid_conversion"),        # 数据隐私/产品
]

assert len(B4_RISK_PAIRINGS) == 105, f"B4 应有 105 组，实际 {len(B4_RISK_PAIRINGS)}"


# ─────────────────────────────────────────────
# B5 精选组合（66 组 = 22 正配对 + 44 高风险精选）
# 44 个高风险精选：每个手动主题选 B4 中最高风险的 2 个
# 选择标准：跨行业距离最远 + 长文本最易漂移
# ─────────────────────────────────────────────
B5_EXTREME_COMBOS: List[Tuple[str, str]] = list(POSITIVE_PAIRS) + [
    # m01 高血压复诊
    ("m01_hypertension_followup", "t17_payment_integration"),   # 医疗×支付：最远跨界
    ("m01_hypertension_followup", "t11_realestate_destock"),    # 医疗×房地产

    # m02 运营补岗
    ("m02_ops_recruitment",       "t17_payment_integration"),   # HR×支付
    ("m02_ops_recruitment",       "t01_medical_chronic"),       # HR×医疗

    # m03 艺人代言
    ("m03_celebrity_endorsement", "t17_payment_integration"),   # 娱乐×支付
    ("m03_celebrity_endorsement", "t13_manufacturing_efficiency"),  # 娱乐×制造

    # m04 工程交付
    ("m04_project_delivery",      "t01_medical_chronic"),       # 工程×医疗
    ("m04_project_delivery",      "t09_retail_repurchase"),     # 工程×零售

    # m05 新能源投放
    ("m05_ev_launch",             "t17_payment_integration"),   # 汽车×支付
    ("m05_ev_launch",             "t01_medical_chronic"),       # 汽车×医疗

    # m06 咨询拓展
    ("m06_consulting_expand",     "t17_payment_integration"),   # 咨询×支付
    ("m06_consulting_expand",     "t01_medical_chronic"),       # 咨询×医疗

    # m07 法律顾问
    ("m07_legal_retainer",        "t17_payment_integration"),   # 法律×支付
    ("m07_legal_retainer",        "t13_manufacturing_efficiency"),  # 法律×制造

    # m08 资产配置
    ("m08_wealth_management",     "t17_payment_integration"),   # 金融×支付
    ("m08_wealth_management",     "t01_medical_chronic"),       # 金融×医疗

    # m09 会员复购
    ("m09_member_repurchase",     "t17_payment_integration"),   # 零售×支付
    ("m09_member_repurchase",     "t01_medical_chronic"),       # 零售×医疗

    # m10 保险质检
    ("m10_insurance_qc",          "t17_payment_integration"),   # 保险×支付
    ("m10_insurance_qc",          "t13_manufacturing_efficiency"),  # 保险×制造

    # m11 楼盘去化
    ("m11_realestate_destock",    "t17_payment_integration"),   # 房地产×支付
    ("m11_realestate_destock",    "t01_medical_chronic"),       # 房地产×医疗

    # m12 AI付费转化
    ("m12_ai_paid_conversion",    "t01_medical_chronic"),       # AI×医疗
    ("m12_ai_paid_conversion",    "t04_engineering_delivery"),  # AI×工程

    # m13 产线提效
    ("m13_production_efficiency", "t17_payment_integration"),   # 制造×支付
    ("m13_production_efficiency", "t01_medical_chronic"),       # 制造×医疗

    # m14 内容周会
    ("m14_content_weekly",        "t17_payment_integration"),   # 媒体×支付
    ("m14_content_weekly",        "t01_medical_chronic"),       # 媒体×医疗

    # m15 广告合规
    ("m15_ad_compliance",         "t17_payment_integration"),   # 法律×支付
    ("m15_ad_compliance",         "t13_manufacturing_efficiency"),  # 法律×制造

    # m16 保险销售洞察
    ("m16_insurance_sales_insight", "t17_payment_integration"),  # 保险×支付
    ("m16_insurance_sales_insight", "t04_engineering_delivery"), # 保险×工程

    # m17 支付接入
    ("m17_payment_integration",   "t01_medical_chronic"),       # 支付×医疗
    ("m17_payment_integration",   "t03_entertainment_celebrity"),  # 支付×娱乐

    # m18 支付退款对账
    ("m18_payment_risk_reconciliation", "t01_medical_chronic"),  # 支付×医疗
    ("m18_payment_risk_reconciliation", "t03_entertainment_celebrity"),  # 支付×娱乐

    # m19 朋友圈发布
    ("m19_moments_publish",       "t01_medical_chronic"),       # 微信×医疗
    ("m19_moments_publish",       "t08_wealth_allocation"),     # 微信×金融

    # m20 朋友圈互动
    ("m20_moments_interaction",   "t01_medical_chronic"),       # 微信×医疗
    ("m20_moments_interaction",   "t08_wealth_allocation"),     # 微信×金融

    # m21 朋友圈隐私
    ("m21_moments_privacy",       "t01_medical_chronic"),       # 微信×医疗
    ("m21_moments_privacy",       "t08_wealth_allocation"),     # 微信×金融

    # 补足至 44 个高风险精选（各选跨距最远的组合）
    ("m04_project_delivery",      "t08_wealth_allocation"),     # 工程×金融
    ("m07_legal_retainer",        "t19_payment_reconciliation"),  # 法律×支付对账
]

assert len(B5_EXTREME_COMBOS) == 66, f"B5 应有 66 组，实际 {len(B5_EXTREME_COMBOS)}"
