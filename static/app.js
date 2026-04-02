const STORAGE_KEY = "online_audio_generation_demo_v2";
const AUDIO_TEXT_MAX_CHARS = 12000;
const DEFAULT_WORD_COUNT = "1000";
const STALE_TASK_MS = 24 * 60 * 60 * 1000;
const SPEAKER_COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4", "#84CC16", "#F97316", "#EC4899", "#6B7280"];

const LANGUAGE_OPTIONS = [
  { label: "中文（普通话）", backend: "Chinese", code: "zh" },
  { label: "英语", backend: "English", code: "en" },
  { label: "日语", backend: "Japanese", code: "ja" },
  { label: "韩语", backend: "Korean", code: "ko" },
  { label: "西班牙语", backend: "Spanish", code: "es" },
  { label: "法语", backend: "French", code: "fr" },
  { label: "德语", backend: "German", code: "de" },
  { label: "葡萄牙语", backend: "Portuguese", code: "pt" },
  { label: "意大利语", backend: "Italian", code: "it" },
  { label: "俄语", backend: "Russian", code: "ru" },
  { label: "阿拉伯语", backend: "Arabic", code: "ar" },
  { label: "印度尼西亚语", backend: "Indonesian", code: "id" }
];

const PRESET_TEMPLATE_LABELS = [
  "医疗健康｜慢病随访",
  "人力资源与招聘｜招聘补岗",
  "娱乐/媒体｜艺人商业化",
  "建筑与工程行业｜项目交付",
  "汽车行业｜车型投放",
  "咨询/专业服务｜客户拓展",
  "法律服务｜法顾专项",
  "金融/投资｜资产配置",
  "零售行业｜会员复购",
  "保险行业｜保险质检",
  "房地产｜项目去化",
  "人工智能/科技｜付费转化",
  "制造业｜产线提效",
  "娱乐/媒体｜战略周会",
  "法律服务｜广告合规",
  "保险行业｜销售洞察",
  "测试开发｜支付项目",
  "测试开发｜朋友圈项目"
];

const TEMPLATE_CONTEXT_MAP = {
  "医疗健康｜慢病随访": {
    primaryRole: "随访医生",
    supportingRoles: ["患者本人", "家属", "随访护士"],
    discussionAxes: ["症状变化", "用药执行", "复查节点", "风险提示", "患者配合"],
    deliverable: "形成清晰的随访安排、复查节点和注意事项",
    goalStem: "围绕慢病随访过程中的当前情况、风险判断和后续安排展开真实交流"
  },
  "人力资源与招聘｜招聘补岗": {
    primaryRole: "招聘负责人",
    supportingRoles: ["业务部门经理", "HRBP", "用人主管"],
    discussionAxes: ["岗位缺口", "优先级", "候选人画像", "渠道策略", "到岗时间"],
    deliverable: "明确补岗优先级、招聘策略和推进节奏",
    goalStem: "围绕招聘补岗过程中的岗位画像、时间压力和渠道策略展开讨论"
  },
  "娱乐/媒体｜艺人商业化": {
    primaryRole: "商务负责人",
    supportingRoles: ["经纪人", "品牌负责人", "内容运营"],
    discussionAxes: ["商业定位", "品牌匹配", "报价策略", "执行风险", "转化目标"],
    deliverable: "形成艺人商业化推进策略和合作判断",
    goalStem: "围绕艺人商业化中的品牌合作、资源投入和转化效果展开讨论"
  },
  "建筑与工程行业｜项目交付": {
    primaryRole: "项目经理",
    supportingRoles: ["工程负责人", "甲方代表", "采购或成本负责人"],
    discussionAxes: ["交付进度", "现场问题", "成本控制", "风险处理", "验收节点"],
    deliverable: "形成项目交付问题清单和推进方案",
    goalStem: "围绕项目交付中的进度、成本、现场风险和验收安排展开讨论"
  },
  "汽车行业｜车型投放": {
    primaryRole: "车型项目负责人",
    supportingRoles: ["市场负责人", "销售负责人", "区域运营代表"],
    discussionAxes: ["投放节奏", "渠道准备", "卖点表达", "库存规划", "区域反馈"],
    deliverable: "形成车型投放节奏和重点动作安排",
    goalStem: "围绕车型投放中的市场准备、渠道协同和节奏控制展开讨论"
  },
  "咨询/专业服务｜客户拓展": {
    primaryRole: "客户拓展负责人",
    supportingRoles: ["顾问经理", "行业顾问", "交付负责人"],
    discussionAxes: ["客户诉求", "方案切入", "关系推进", "报价策略", "交付匹配"],
    deliverable: "形成客户拓展策略和下一步推进动作",
    goalStem: "围绕客户拓展中的切入点、关系推进和方案竞争力展开讨论"
  },
  "法律服务｜法顾专项": {
    primaryRole: "法务顾问",
    supportingRoles: ["客户负责人", "专项律师", "合规经理"],
    discussionAxes: ["风险识别", "证据材料", "处理方案", "边界判断", "执行安排"],
    deliverable: "形成法顾专项的处理路径和分工建议",
    goalStem: "围绕法顾专项中的法律风险、证据准备和执行方案展开讨论"
  },
  "金融/投资｜资产配置": {
    primaryRole: "投顾负责人",
    supportingRoles: ["客户经理", "研究员", "风险控制负责人"],
    discussionAxes: ["配置目标", "风险偏好", "资金安排", "收益预期", "调整策略"],
    deliverable: "形成清晰的资产配置建议和风险提示",
    goalStem: "围绕资产配置中的收益目标、风险偏好和组合调整展开讨论"
  },
  "零售行业｜会员复购": {
    primaryRole: "会员运营负责人",
    supportingRoles: ["门店负责人", "活动运营", "数据分析师"],
    discussionAxes: ["会员分层", "活动策略", "复购触达", "门店配合", "效果验证"],
    deliverable: "形成会员复购提升方案和执行节奏",
    goalStem: "围绕会员复购中的触达策略、门店配合和活动效果展开讨论"
  },
  "保险行业｜保险质检": {
    primaryRole: "质检负责人",
    supportingRoles: ["销售主管", "培训负责人", "合规专员"],
    discussionAxes: ["录音质检", "销售话术", "风险点", "培训改进", "复盘闭环"],
    deliverable: "形成保险质检问题结论和改进动作",
    goalStem: "围绕保险质检中的话术风险、培训改进和问题闭环展开讨论"
  },
  "房地产｜项目去化": {
    primaryRole: "项目营销负责人",
    supportingRoles: ["渠道经理", "案场负责人", "投放运营"],
    discussionAxes: ["去化压力", "客源结构", "渠道效率", "价格策略", "案场转化"],
    deliverable: "形成项目去化提效方案和短期动作安排",
    goalStem: "围绕项目去化中的渠道效率、案场转化和价格策略展开讨论"
  },
  "人工智能/科技｜付费转化": {
    primaryRole: "增长负责人",
    supportingRoles: ["产品经理", "数据分析师", "运营负责人"],
    discussionAxes: ["转化漏斗", "付费门槛", "试用策略", "价值感知", "数据回收"],
    deliverable: "形成付费转化优化方案和实验计划",
    goalStem: "围绕付费转化中的产品策略、转化漏斗和数据验证展开讨论"
  },
  "制造业｜产线提效": {
    primaryRole: "产线负责人",
    supportingRoles: ["工艺工程师", "设备负责人", "质量经理"],
    discussionAxes: ["瓶颈工序", "设备效率", "良率波动", "排产协同", "异常处理"],
    deliverable: "形成产线提效方案和关键改善动作",
    goalStem: "围绕产线提效中的瓶颈工序、设备效率和质量稳定性展开讨论"
  },
  "娱乐/媒体｜战略周会": {
    primaryRole: "业务负责人",
    supportingRoles: ["内容负责人", "增长负责人", "商务负责人"],
    discussionAxes: ["业务目标", "资源投入", "进展复盘", "重点风险", "下周动作"],
    deliverable: "形成战略周会的重点决策和分工安排",
    goalStem: "围绕战略周会中的业务目标、资源分配和重点风险展开讨论"
  },
  "法律服务｜广告合规": {
    primaryRole: "法务负责人",
    supportingRoles: ["市场负责人", "品牌经理", "合规专员"],
    discussionAxes: ["广告表述", "风险边界", "素材审核", "整改建议", "上线条件"],
    deliverable: "形成广告合规判断和修改建议",
    goalStem: "围绕广告合规中的风险边界、素材表述和整改方案展开讨论"
  },
  "保险行业｜销售洞察": {
    primaryRole: "销售管理负责人",
    supportingRoles: ["区域经理", "培训负责人", "数据分析师"],
    discussionAxes: ["销售表现", "客户反馈", "转化瓶颈", "团队差异", "改善动作"],
    deliverable: "形成销售洞察结论和管理改进动作",
    goalStem: "围绕销售洞察中的客户反馈、团队差异和改善动作展开讨论"
  },
  "测试开发｜支付项目": {
    primaryRole: "测试负责人",
    supportingRoles: ["服务端开发", "客户端开发", "产品经理", "质量负责人"],
    discussionAxes: ["支付接入", "下单回调", "退款安全", "对账差错", "稳定性准入"],
    deliverable: "形成支付项目的测试范围、风险清单和上线准入结论",
    goalStem: "围绕支付项目中的链路完整性、异常兜底和上线风险展开讨论"
  },
  "测试开发｜朋友圈项目": {
    primaryRole: "测试负责人",
    supportingRoles: ["客户端开发", "服务端开发", "产品经理", "运营负责人"],
    discussionAxes: ["内容发布", "多端分发", "互动一致性", "隐私可见性", "内容审核", "容量与准入"],
    deliverable: "形成朋友圈项目的重点测试范围、风险判断和准入结论",
    goalStem: "围绕朋友圈项目中的内容链路、可见性规则和容量风险展开讨论"
  }
};

const TEST_DEV_TEMPLATE_GROUPS = {
  "测试开发｜支付接入": "测试开发｜支付项目",
  "测试开发｜下单回调": "测试开发｜支付项目",
  "测试开发｜退款安全": "测试开发｜支付项目",
  "测试开发｜对账差错": "测试开发｜支付项目",
  "测试开发｜稳定性准入": "测试开发｜支付项目",
  "测试开发｜朋友圈项目": "测试开发｜朋友圈项目",
  "测试开发｜内容发布": "测试开发｜朋友圈项目",
  "测试开发｜多端分发": "测试开发｜朋友圈项目",
  "测试开发｜互动一致性": "测试开发｜朋友圈项目",
  "测试开发｜隐私可见性": "测试开发｜朋友圈项目",
  "测试开发｜内容审核": "测试开发｜朋友圈项目",
  "测试开发｜容量与准入": "测试开发｜朋友圈项目"
};

const BASE_TEMPLATE_OPTIONS = PRESET_TEMPLATE_LABELS.map((label) => ({
  value: dynamicTemplateValue(label),
  label
}));

const VOICE_LIBRARY = {
  Chinese: [
    { value: "zh-CN-XiaoxiaoNeural", label: "晓晓（女，中文）" },
    { value: "zh-CN-YunxiNeural", label: "云希（男，中文）" },
    { value: "zh-CN-XiaoyiNeural", label: "晓伊（女，中文）" },
    { value: "zh-CN-YunyangNeural", label: "云扬（男，中文）" }
  ],
  English: [
    { value: "en-US-JennyNeural", label: "Jenny（女，英语）" },
    { value: "en-US-GuyNeural", label: "Guy（男，英语）" },
    { value: "en-US-AriaNeural", label: "Aria（女，英语）" },
    { value: "en-US-DavisNeural", label: "Davis（男，英语）" }
  ],
  Japanese: [
    { value: "ja-JP-NanamiNeural", label: "Nanami（女，日语）" },
    { value: "ja-JP-KeitaNeural", label: "Keita（男，日语）" }
  ],
  Korean: [
    { value: "ko-KR-SunHiNeural", label: "SunHi（女，韩语）" },
    { value: "ko-KR-InJoonNeural", label: "InJoon（男，韩语）" }
  ],
  Spanish: [
    { value: "es-ES-ElviraNeural", label: "Elvira（女，西班牙语）" },
    { value: "es-ES-AlvaroNeural", label: "Alvaro（男，西班牙语）" }
  ],
  French: [
    { value: "fr-FR-DeniseNeural", label: "Denise（女，法语）" },
    { value: "fr-FR-HenriNeural", label: "Henri（男，法语）" }
  ],
  German: [
    { value: "de-DE-KatjaNeural", label: "Katja（女，德语）" },
    { value: "de-DE-ConradNeural", label: "Conrad（男，德语）" }
  ],
  Portuguese: [
    { value: "pt-BR-FranciscaNeural", label: "Francisca（女，葡萄牙语）" },
    { value: "pt-BR-AntonioNeural", label: "Antonio（男，葡萄牙语）" }
  ],
  Italian: [
    { value: "it-IT-ElsaNeural", label: "Elsa（女，意大利语）" },
    { value: "it-IT-DiegoNeural", label: "Diego（男，意大利语）" }
  ],
  Russian: [
    { value: "ru-RU-DariyaNeural", label: "Dariya（女，俄语）" },
    { value: "ru-RU-DmitryNeural", label: "Dmitry（男，俄语）" }
  ],
  Arabic: [
    { value: "ar-SA-ZariyahNeural", label: "Zariyah（女，阿拉伯语）" },
    { value: "ar-SA-HamedNeural", label: "Hamed（男，阿拉伯语）" }
  ],
  Indonesian: [
    { value: "id-ID-GadisNeural", label: "Gadis（女，印度尼西亚语）" },
    { value: "id-ID-ArdiNeural", label: "Ardi（男，印度尼西亚语）" }
  ]
};

function createDefaultFormState() {
  return {
    mode: "llm",
    topicInputMode: "manual",
    llmTopic: "",
    selectedPresetId: "",
    template: BASE_TEMPLATE_OPTIONS[0]?.value || "",
    customPrompt: "",
    llmLanguage: LANGUAGE_OPTIONS[0].backend,
    wordCountLimit: DEFAULT_WORD_COUNT,
    keywords: [],
    manualTopic: "",
    manualLanguage: LANGUAGE_OPTIONS[0].backend,
    manualText: "",
    speakerCount: 2,
    previewText: "",
    dialogueId: "",
    generatedTextFileName: "",
    voiceAssignments: { "1": "", "2": "" },
    outputFormat: "MP3",
    preciseDuration: "",
    folder: "默认目录",
    tags: [],
    includeScripts: false,
    isGeneratingText: false,
    isSubmittingAudio: false,
    modalMessage: "",
    modalMessageType: "info"
  };
}

const state = {
  serverInfo: null,
  modalOpen: true,
  presetTopics: [],
  templateOptions: [...BASE_TEMPLATE_OPTIONS],
  form: createDefaultFormState(),
  tasks: [],
  modalSize: null
};

const el = {
  sharePrimaryLink: document.getElementById("sharePrimaryLink"),
  copyShareBtn: document.getElementById("copyShareBtn"),
  shareHint: document.getElementById("shareHint"),
  uploadBtn: document.getElementById("uploadBtn"),
  openOnlineAudioBtn: document.getElementById("openOnlineAudioBtn"),
  cleanupOldTasksBtn: document.getElementById("cleanupOldTasksBtn"),
  taskTableBody: document.getElementById("taskTableBody"),
  taskEmpty: document.getElementById("taskEmpty"),
  toastContainer: document.getElementById("toastContainer"),
  modalOverlay: document.getElementById("modalOverlay"),
  modalPanel: document.getElementById("modalPanel"),
  modalResizeHandle: document.getElementById("modalResizeHandle"),
  closeModalBtn: document.getElementById("closeModalBtn"),
  cancelModalBtn: document.getElementById("cancelModalBtn"),
  modeCardLlm: document.getElementById("modeCardLlm"),
  modeCardManual: document.getElementById("modeCardManual"),
  modeLlm: document.getElementById("modeLlm"),
  modeManual: document.getElementById("modeManual"),
  llmSection: document.getElementById("llmSection"),
  manualSection: document.getElementById("manualSection"),
  generateTextRow: document.getElementById("generateTextRow"),
  previewSection: document.getElementById("previewSection"),
  topicModeCardManual: document.getElementById("topicModeCardManual"),
  topicModeCardPreset: document.getElementById("topicModeCardPreset"),
  topicModeManual: document.getElementById("topicModeManual"),
  topicModePreset: document.getElementById("topicModePreset"),
  topicManualGroup: document.getElementById("topicManualGroup"),
  topicPresetGroup: document.getElementById("topicPresetGroup"),
  presetTopicResolvedGroup: document.getElementById("presetTopicResolvedGroup"),
  llmTopic: document.getElementById("llmTopic"),
  presetTopicSelect: document.getElementById("presetTopicSelect"),
  presetTopicResolved: document.getElementById("presetTopicResolved"),
  templateSelect: document.getElementById("templateSelect"),
  customPromptGroup: document.getElementById("customPromptGroup"),
  customPrompt: document.getElementById("customPrompt"),
  llmLanguage: document.getElementById("llmLanguage"),
  wordCountLimit: document.getElementById("wordCountLimit"),
  keywordWrap: document.getElementById("keywordWrap"),
  keywordInput: document.getElementById("keywordInput"),
  manualTopic: document.getElementById("manualTopic"),
  manualLanguage: document.getElementById("manualLanguage"),
  manualText: document.getElementById("manualText"),
  speakerCount: document.getElementById("speakerCount"),
  generateTextBtn: document.getElementById("generateTextBtn"),
  regenTextBtn: document.getElementById("regenTextBtn"),
  previewText: document.getElementById("previewText"),
  previewKeywordGroup: document.getElementById("previewKeywordGroup"),
  previewKeywordHighlight: document.getElementById("previewKeywordHighlight"),
  voiceLanguageLabel: document.getElementById("voiceLanguageLabel"),
  speakerVoiceRows: document.getElementById("speakerVoiceRows"),
  voiceWarning: document.getElementById("voiceWarning"),
  outputFormat: document.getElementById("outputFormat"),
  preciseDuration: document.getElementById("preciseDuration"),
  folderSelect: document.getElementById("folderSelect"),
  tagWrap: document.getElementById("tagWrap"),
  tagInput: document.getElementById("tagInput"),
  includeScripts: document.getElementById("includeScripts"),
  modalMessage: document.getElementById("modalMessage"),
  submitAudioBtn: document.getElementById("submitAudioBtn")
};

function normalizeText(value) {
  return String(value || "").replace(/\r\n/g, "\n").trim();
}

function nowIsoString() {
  return new Date().toISOString();
}

function formatTimestamp(isoString) {
  if (!isoString) return "-";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function basenameFromPath(filePath) {
  if (!filePath) return "";
  const normalized = String(filePath).replace(/\\/g, "/");
  const parts = normalized.split("/");
  return parts[parts.length - 1] || "";
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escapeRegExp(text) {
  return String(text || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function languageOptionByBackend(backend) {
  return LANGUAGE_OPTIONS.find((item) => item.backend === backend) || LANGUAGE_OPTIONS[0];
}

function templateOptionByValue(value) {
  return state.templateOptions.find((item) => item.value === value) || state.templateOptions[0] || BASE_TEMPLATE_OPTIONS[0];
}

function templateOptionByLabel(label) {
  return state.templateOptions.find((item) => item.label === label) || null;
}

function normalizeTemplateDropdownLabel(label) {
  const normalized = String(label || "").trim();
  if (!normalized) return "";
  return TEST_DEV_TEMPLATE_GROUPS[normalized] || normalized;
}

function templateDisplayLabelFromPreset(preset) {
  const displayTitle = String(preset?.display_title || "").trim();
  if (displayTitle) return normalizeTemplateDropdownLabel(displayTitle);
  const templateLabel = String(preset?.template_label || "").trim();
  if (templateLabel) return normalizeTemplateDropdownLabel(templateLabel);
  return "";
}

function dynamicTemplateValue(label) {
  const code = Array.from(String(label || "其他"))
    .map((char) => char.codePointAt(0).toString(16))
    .join("")
    .slice(0, 24);
  return `dynamic_${code || "template"}`;
}

function ensureTemplateOption(label) {
  const normalized = normalizeTemplateDropdownLabel(label);
  if (!normalized) {
    return state.templateOptions[0]?.value || BASE_TEMPLATE_OPTIONS[0].value;
  }
  const existing = templateOptionByLabel(normalized);
  if (existing) return existing.value;
  const next = { value: dynamicTemplateValue(normalized), label: normalized };
  state.templateOptions = [...state.templateOptions, next];
  return next.value;
}

function uniqueStrings(items) {
  const result = [];
  (items || []).forEach((item) => {
    const normalized = String(item || "").trim();
    if (normalized && !result.includes(normalized)) {
      result.push(normalized);
    }
  });
  return result;
}

function splitTemplateLabelParts(label) {
  const parts = String(label || "")
    .split("｜")
    .map((item) => item.trim())
    .filter(Boolean);
  if (parts.length >= 2) {
    return { domain: parts[0], sceneType: parts.slice(1).join("｜") };
  }
  return { domain: "", sceneType: String(label || "").trim() || "业务场景" };
}

function templateContextForLabel(templateLabel, topic, keywordTerms = []) {
  const normalizedLabel = normalizeTemplateDropdownLabel(templateLabel);
  const base = TEMPLATE_CONTEXT_MAP[normalizedLabel] || {};
  const { domain, sceneType } = splitTemplateLabelParts(normalizedLabel);
  const topicText = String(topic || "").trim() || sceneType || "业务议题";
  const discussionAxes = uniqueStrings([
    ...(base.discussionAxes || []),
    ...keywordTerms
  ]);
  return {
    label: normalizedLabel,
    domain: base.domain || domain || "通用业务",
    sceneType: base.sceneType || sceneType || "场景讨论",
    primaryRole: base.primaryRole || `${domain || "业务"}负责人`,
    supportingRoles: uniqueStrings(base.supportingRoles || ["执行负责人", "协作方代表", "数据或质量代表"]),
    discussionAxes: discussionAxes.length ? discussionAxes : ["当前现状", "主要风险", "推进节奏", "验收标准"],
    deliverable: base.deliverable || `形成围绕${topicText}的下一步方案、责任分工和验证口径`,
    goalStem: base.goalStem || `围绕${topicText}中的现状、风险、方案选择和推进节奏展开讨论`
  };
}

function buildRoleBriefs(templateContext, speakerCount) {
  const roles = uniqueStrings([templateContext.primaryRole, ...(templateContext.supportingRoles || [])]);
  while (roles.length < speakerCount) {
    roles.push(`相关协作方${roles.length}`);
  }
  return roles.slice(0, speakerCount);
}

function buildGenerationContext(templateLabel, topic, keywordTerms = []) {
  const templateContext = templateContextForLabel(templateLabel, topic, keywordTerms);
  const roleBriefs = buildRoleBriefs(templateContext, speakerCountValue());
  return {
    domain: templateContext.domain,
    scene_type: templateContext.sceneType,
    scene_goal: `${templateContext.goalStem}，主题聚焦“${String(topic || "").trim() || templateContext.sceneType}”`,
    deliverable: templateContext.deliverable,
    discussion_axes: templateContext.discussionAxes,
    role_briefs: roleBriefs,
    quality_constraints: [
      "必须口语化、真实、避免套话",
      "每个说话人都要有明确立场和信息量",
      "避免中英混杂和空洞重复",
      "对话要围绕事实、风险、动作和结论推进"
    ]
  };
}

function buildTemplateOptionsFromPresets(presets) {
  const seen = new Set();
  const options = [];

  (Array.isArray(presets) ? presets : []).forEach((preset) => {
    const label = templateDisplayLabelFromPreset(preset);
    if (!label || seen.has(label)) return;
    seen.add(label);
    options.push({
      value: dynamicTemplateValue(label),
      label
    });
  });

  return options.length ? options : [...BASE_TEMPLATE_OPTIONS];
}

function presetTopicById(id) {
  return state.presetTopics.find((item) => item.id === id) || null;
}

function currentPresetTopic() {
  return presetTopicById(state.form.selectedPresetId || el.presetTopicSelect.value);
}

function currentMode() {
  return state.form.mode === "manual" ? "manual" : "llm";
}

function currentTopicInputMode() {
  return state.form.topicInputMode === "preset" ? "preset" : "manual";
}

function setMode(mode) {
  state.form.mode = mode === "manual" ? "manual" : "llm";
  renderAll();
}

window.setMode = setMode;

function setTopicInputMode(mode) {
  state.form.topicInputMode = mode === "preset" ? "preset" : "manual";
  renderAll();
  if (state.form.topicInputMode === "preset") {
    void refreshPresetTopicsIfNeeded(true);
  }
}

function currentLanguageBackend() {
  return currentMode() === "llm" ? el.llmLanguage.value : el.manualLanguage.value;
}

function currentLanguageLabel() {
  return languageOptionByBackend(currentLanguageBackend()).label;
}

function resolvedLlmTopic() {
  if (currentTopicInputMode() === "preset") {
    return currentPresetTopic()?.topic_text || "";
  }
  return el.llmTopic.value.trim();
}

function currentTitle() {
  return currentMode() === "llm" ? resolvedLlmTopic() : el.manualTopic.value.trim();
}

function currentWorkingText() {
  return currentMode() === "llm" ? normalizeText(el.previewText.value) : normalizeText(el.manualText.value);
}

function parseTaskTime(task) {
  const timestamp = Date.parse(String(task?.createdAt || ""));
  return Number.isFinite(timestamp) ? timestamp : 0;
}

function isTaskStale(task) {
  const timestamp = parseTaskTime(task);
  return timestamp > 0 && Date.now() - timestamp >= STALE_TASK_MS;
}

function cloneVoiceAssignments(assignments = {}) {
  return Object.fromEntries(Object.entries(assignments).map(([key, value]) => [String(key), String(value || "")]));
}

function snapshotCurrentForm() {
  readFormFromDom();
  return {
    ...state.form,
    keywords: [...state.form.keywords],
    tags: [...state.form.tags],
    voiceAssignments: cloneVoiceAssignments(state.form.voiceAssignments)
  };
}

function applyModalSize() {
  if (!el.modalPanel) return;
  if (!state.modalSize || !state.modalSize.width || !state.modalSize.height) {
    el.modalPanel.style.width = "";
    el.modalPanel.style.height = "";
    return;
  }

  const maxWidth = Math.max(760, window.innerWidth - 24);
  const maxHeight = Math.max(560, window.innerHeight - 24);
  const width = Math.min(maxWidth, Math.max(760, Number(state.modalSize.width) || 960));
  const height = Math.min(maxHeight, Math.max(560, Number(state.modalSize.height) || 760));
  el.modalPanel.style.width = `${width}px`;
  el.modalPanel.style.height = `${height}px`;
}

function speakerCountValue() {
  const parsed = Number(el.speakerCount.value || state.form.speakerCount || 2);
  return Math.min(10, Math.max(1, parsed || 2));
}

function activeVoiceOptions() {
  return VOICE_LIBRARY[currentLanguageBackend()] || VOICE_LIBRARY.Chinese;
}

function gatherVoiceAssignments() {
  const mapping = {};
  Object.entries(state.form.voiceAssignments || {}).forEach(([speakerId, voiceValue]) => {
    if (voiceValue) {
      mapping[speakerId] = voiceValue;
    }
  });
  return mapping;
}

function allVoicesSelected() {
  for (let speaker = 1; speaker <= speakerCountValue(); speaker += 1) {
    if (!state.form.voiceAssignments[String(speaker)]) {
      return false;
    }
  }
  return true;
}

function setModalMessage(message, type = "info") {
  state.form.modalMessage = message;
  state.form.modalMessageType = type;
  el.modalMessage.textContent = message;
  el.modalMessage.classList.remove("is-error", "is-success");
  if (type === "error") el.modalMessage.classList.add("is-error");
  if (type === "success") el.modalMessage.classList.add("is-success");
}

function showToast(type, message) {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  el.toastContainer.appendChild(toast);
  window.setTimeout(() => toast.remove(), 3600);
}

function openModal() {
  state.modalOpen = true;
  el.modalOverlay.classList.add("open");
  applyModalSize();
  persistState();
  if (state.form.mode === "llm") {
    void refreshPresetTopicsIfNeeded(state.presetTopics.length === 0);
  }
}

function closeModal() {
  if (state.form.isGeneratingText || state.form.isSubmittingAudio) return;
  state.modalOpen = false;
  el.modalOverlay.classList.remove("open");
  persistState();
}

function resetForm() {
  state.form = createDefaultFormState();
  syncFormToDom();
  renderAll();
}

function readFormFromDom() {
  state.form.mode = el.modeManual.checked ? "manual" : "llm";
  state.form.topicInputMode = el.topicModePreset.checked ? "preset" : "manual";
  state.form.llmTopic = el.llmTopic.value;
  state.form.selectedPresetId = el.presetTopicSelect.value;
  state.form.template = el.templateSelect.value;
  state.form.customPrompt = el.customPrompt.value;
  state.form.llmLanguage = el.llmLanguage.value;
  state.form.wordCountLimit = el.wordCountLimit.value;
  state.form.manualTopic = el.manualTopic.value;
  state.form.manualLanguage = el.manualLanguage.value;
  state.form.manualText = el.manualText.value;
  state.form.speakerCount = speakerCountValue();
  state.form.previewText = el.previewText.value;
  state.form.outputFormat = el.outputFormat.value;
  state.form.preciseDuration = el.preciseDuration.value;
  state.form.folder = el.folderSelect.value;
  state.form.includeScripts = el.includeScripts.checked;
}

function syncFormToDom() {
  el.modeLlm.checked = state.form.mode === "llm";
  el.modeManual.checked = state.form.mode === "manual";
  el.topicModeManual.checked = currentTopicInputMode() === "manual";
  el.topicModePreset.checked = currentTopicInputMode() === "preset";
  el.llmTopic.value = state.form.llmTopic || "";
  el.presetTopicSelect.value = state.form.selectedPresetId || "";
  el.presetTopicResolved.value = currentPresetTopic()?.topic_text || "";
  el.templateSelect.value = templateOptionByValue(state.form.template).value;
  el.customPrompt.value = state.form.customPrompt || "";
  el.llmLanguage.value = state.form.llmLanguage || LANGUAGE_OPTIONS[0].backend;
  el.wordCountLimit.value = state.form.wordCountLimit || DEFAULT_WORD_COUNT;
  el.manualTopic.value = state.form.manualTopic || "";
  el.manualLanguage.value = state.form.manualLanguage || LANGUAGE_OPTIONS[0].backend;
  el.manualText.value = state.form.manualText || "";
  el.speakerCount.value = String(state.form.speakerCount || 2);
  el.previewText.value = state.form.previewText || "";
  el.outputFormat.value = state.form.outputFormat || "MP3";
  el.preciseDuration.value = state.form.preciseDuration || "";
  el.folderSelect.value = state.form.folder || "默认目录";
  el.includeScripts.checked = Boolean(state.form.includeScripts);
}

function persistState() {
  readFormFromDom();
  const payload = {
    modalOpen: state.modalOpen,
    tasks: state.tasks,
    modalSize: state.modalSize,
    form: {
      ...state.form,
      keywords: [...state.form.keywords],
      tags: [...state.form.tags],
      voiceAssignments: { ...state.form.voiceAssignments }
    }
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function restoreState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const cached = JSON.parse(raw);
    state.modalOpen = cached.modalOpen !== false;
    state.tasks = Array.isArray(cached.tasks) ? cached.tasks.map(normalizeTask) : [];
    state.modalSize = cached.modalSize || null;
    state.form = {
      ...createDefaultFormState(),
      ...(cached.form || {}),
      keywords: Array.isArray(cached.form?.keywords) ? cached.form.keywords : [],
      tags: Array.isArray(cached.form?.tags) ? cached.form.tags : [],
      voiceAssignments: cached.form?.voiceAssignments || {}
    };
    state.form.isGeneratingText = false;
    state.form.isSubmittingAudio = false;
  } catch (error) {
    console.warn("restoreState failed", error);
  }
}

function renderTagEditor(wrap, input, items, removeHandler) {
  wrap.querySelectorAll(".tag-pill").forEach((node) => node.remove());
  items.forEach((item, index) => {
    const pill = document.createElement("span");
    pill.className = "tag-pill";
    pill.innerHTML = `${escapeHtml(item)}<button type="button" data-index="${index}">×</button>`;
    pill.querySelector("button").addEventListener("click", (event) => {
      event.stopPropagation();
      removeHandler(index);
    });
    wrap.insertBefore(pill, input);
  });
}

function splitInputTokens(value) {
  return String(value || "")
    .split(/[\n,，;；]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function addKeyword(value) {
  const nextItems = splitInputTokens(value);
  if (!nextItems.length) return;
  const merged = [...state.form.keywords];
  nextItems.forEach((item) => {
    if (!merged.includes(item)) {
      merged.push(item);
    }
  });
  state.form.keywords = merged;
  renderTagEditor(el.keywordWrap, el.keywordInput, state.form.keywords, removeKeyword);
  renderKeywordHighlightPreview();
  renderSubmitState();
  persistState();
}

function removeKeyword(index) {
  state.form.keywords = state.form.keywords.filter((_, itemIndex) => itemIndex !== index);
  renderTagEditor(el.keywordWrap, el.keywordInput, state.form.keywords, removeKeyword);
  renderKeywordHighlightPreview();
  renderSubmitState();
  persistState();
}

function addTag(value) {
  const nextItems = splitInputTokens(value);
  if (!nextItems.length) return;
  const merged = [...state.form.tags];
  nextItems.forEach((item) => {
    if (!merged.includes(item)) {
      merged.push(item);
    }
  });
  state.form.tags = merged;
  renderTagEditor(el.tagWrap, el.tagInput, state.form.tags, removeTag);
  persistState();
}

function removeTag(index) {
  state.form.tags = state.form.tags.filter((_, itemIndex) => itemIndex !== index);
  renderTagEditor(el.tagWrap, el.tagInput, state.form.tags, removeTag);
  persistState();
}

function handleTagInputKeydown(event, addHandler) {
  if (!["Enter", ",", "，", ";", "；"].includes(event.key)) return;
  event.preventDefault();
  addHandler(event.currentTarget.value);
  event.currentTarget.value = "";
}

function handleTagInputBlur(event, addHandler) {
  if (!event.currentTarget.value.trim()) return;
  addHandler(event.currentTarget.value);
  event.currentTarget.value = "";
}

function renderTemplates() {
  el.templateSelect.innerHTML = state.templateOptions
    .map((option) => `<option value="${option.value}">${option.label}</option>`)
    .join("");
}

function renderLanguages() {
  const options = LANGUAGE_OPTIONS.map((option) => `<option value="${option.backend}">${option.label}</option>`).join("");
  el.llmLanguage.innerHTML = options;
  el.manualLanguage.innerHTML = options;
}

function renderPresetTopics() {
  const options = [
    `<option value="">请选择预置文本主题</option>`,
    ...state.presetTopics.map(
      (preset) => `<option value="${preset.id}">${escapeHtml(preset.display_title || preset.topic_text || preset.source_title)}</option>`
    )
  ];
  el.presetTopicSelect.innerHTML = options.join("");
}

function ensureVoiceAssignmentsShape() {
  const voices = activeVoiceOptions().map((item) => item.value);
  const nextAssignments = {};
  for (let speaker = 1; speaker <= speakerCountValue(); speaker += 1) {
    const current = state.form.voiceAssignments[String(speaker)];
    nextAssignments[String(speaker)] = voices.includes(current) ? current : "";
  }
  state.form.voiceAssignments = nextAssignments;
}

function renderVoiceRows() {
  readFormFromDom();
  ensureVoiceAssignmentsShape();
  el.voiceLanguageLabel.textContent = currentLanguageLabel();
  const options = activeVoiceOptions();
  el.speakerVoiceRows.innerHTML = "";

  for (let speaker = 1; speaker <= speakerCountValue(); speaker += 1) {
    const row = document.createElement("div");
    row.className = "speaker-row";

    const badge = document.createElement("div");
    badge.className = "speaker-badge";
    badge.style.background = SPEAKER_COLORS[speaker - 1] || "#6B7280";
    badge.textContent = String(speaker);

    const select = document.createElement("select");
    select.className = "select-field";
    select.dataset.speakerId = String(speaker);
    select.innerHTML = [
      `<option value="">— 请选择音色 —</option>`,
      ...options.map((voice) => `<option value="${voice.value}">${voice.label}</option>`)
    ].join("");
    select.value = state.form.voiceAssignments[String(speaker)] || "";
    select.addEventListener("change", () => {
      state.form.voiceAssignments[String(speaker)] = select.value;
      renderSubmitState();
      persistState();
    });

    row.appendChild(badge);
    row.appendChild(select);
    el.speakerVoiceRows.appendChild(row);
  }
}

function renderModeUi() {
  readFormFromDom();
  const isLlm = currentMode() === "llm";
  const isPresetTopic = currentTopicInputMode() === "preset";
  const hasPreviewText = Boolean(normalizeText(el.previewText.value));

  el.modeCardLlm.classList.toggle("selected", isLlm);
  el.modeCardManual.classList.toggle("selected", !isLlm);
  el.llmSection.classList.toggle("hidden", !isLlm);
  el.manualSection.classList.toggle("hidden", isLlm);
  el.generateTextRow.classList.toggle("hidden", !isLlm);
  el.previewSection.classList.toggle("hidden", !(isLlm && hasPreviewText));
  el.customPromptGroup.classList.toggle("hidden", el.templateSelect.value !== "custom");

  el.topicModeCardManual.classList.toggle("selected", !isPresetTopic);
  el.topicModeCardPreset.classList.toggle("selected", isPresetTopic);
  el.topicManualGroup.classList.toggle("hidden", !isLlm || isPresetTopic);
  el.topicPresetGroup.classList.toggle("hidden", !isLlm || !isPresetTopic);
  el.presetTopicResolvedGroup.classList.toggle("hidden", !isLlm || !isPresetTopic);
  el.presetTopicSelect.disabled = state.presetTopics.length === 0;
}

function highlightKeywordsHtml(text, keywords) {
  const normalized = normalizeText(text);
  if (!normalized) return "";

  let html = escapeHtml(normalized).replace(/\n/g, "<br>");
  const uniqueKeywords = [...new Set((keywords || []).map((item) => String(item || "").trim()).filter(Boolean))].sort(
    (left, right) => right.length - left.length
  );

  uniqueKeywords.forEach((keyword) => {
    const pattern = new RegExp(escapeRegExp(escapeHtml(keyword)), "gi");
    html = html.replace(pattern, `<span class="keyword-highlight">$&</span>`);
  });

  return html;
}

function renderKeywordHighlightPreview() {
  const previewText = normalizeText(el.previewText.value);
  const shouldShow = currentMode() === "llm" && Boolean(previewText) && state.form.keywords.length > 0;
  el.previewKeywordGroup.classList.toggle("hidden", !shouldShow);
  el.previewKeywordHighlight.innerHTML = shouldShow ? highlightKeywordsHtml(previewText, state.form.keywords) : "";
}

function renderSubmitState() {
  const busy = state.form.isGeneratingText || state.form.isSubmittingAudio;
  el.generateTextBtn.disabled = busy;
  el.regenTextBtn.disabled = busy;
  el.submitAudioBtn.disabled = busy || !allVoicesSelected();
  el.cancelModalBtn.disabled = busy;
  el.closeModalBtn.disabled = busy;
  el.voiceWarning.classList.toggle("hidden", allVoicesSelected());
  el.generateTextBtn.textContent = state.form.isGeneratingText ? "正在生成文本..." : "✨ 根据以上配置生成文本";
}

function renderModalVisibility() {
  el.modalOverlay.classList.toggle("open", state.modalOpen);
  if (state.modalOpen) {
    applyModalSize();
  }
}

function statusBadgeClass(status) {
  if (status === "生成成功") return "status-ok";
  if (status === "生成失败") return "status-err";
  if (status === "语音合成中" || status === "文本生成中") return "status-run";
  return "status-wait";
}

function taskCanOpen(task) {
  return Boolean(task?.snapshot?.form || task?.dialogueId || task?.title);
}

function renderTasks() {
  const tasks = [...state.tasks].sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
  el.taskTableBody.innerHTML = tasks
    .map(
      (task) => `
    <tr>
      <td>
        <span class="task-title">${escapeHtml(task.title || "未命名任务")}</span>
        <span class="task-meta">${escapeHtml(task.fileName || task.textFileName || "")}</span>
      </td>
      <td>${escapeHtml(formatTimestamp(task.createdAt))}</td>
      <td>${escapeHtml(task.sourceLabel === "上传" ? "上传" : "生成")}</td>
      <td><span class="status-badge ${statusBadgeClass(task.status)}">${escapeHtml(task.status)}</span></td>
      <td>
        <div class="row-actions">
          <button class="btn btn-secondary btn-sm" type="button" data-action="view-task" data-id="${task.id}" ${
            taskCanOpen(task) ? "" : "disabled"
          }>查看任务</button>
          <button class="btn btn-secondary btn-sm" type="button" data-action="download-text" data-id="${task.id}" ${
            task.textDownloadUrl ? "" : "disabled"
          }>下载文本</button>
          <button class="btn btn-secondary btn-sm" type="button" data-action="download-audio" data-id="${task.id}" ${
            task.audioDownloadUrl && task.status === "生成成功" ? "" : "disabled"
          }>下载音频</button>
          <button class="btn btn-secondary btn-sm" type="button" data-action="show-error" data-id="${task.id}" ${
            task.status === "生成失败" ? "" : "disabled"
          }>查看原因</button>
          <button class="btn btn-secondary btn-sm" type="button" data-action="delete-task" data-id="${task.id}">删除</button>
        </div>
      </td>
    </tr>
  `
    )
    .join("");
  el.taskEmpty.classList.toggle("hidden", tasks.length > 0);
}

function renderShareBox(payload) {
  const primary = payload.preferred_share_url || payload.local_urls?.[0] || "";
  el.sharePrimaryLink.textContent = primary || "未获取到可访问地址";
  el.sharePrimaryLink.href = primary || "#";
  el.copyShareBtn.disabled = !primary;
  el.shareHint.textContent = payload.share_hint || "可把地址发给同一局域网内的其他电脑使用。";
}

function renderAll() {
  renderTemplates();
  renderLanguages();
  renderPresetTopics();
  syncFormToDom();
  renderTagEditor(el.keywordWrap, el.keywordInput, state.form.keywords, removeKeyword);
  renderTagEditor(el.tagWrap, el.tagInput, state.form.tags, removeTag);
  renderModeUi();
  renderVoiceRows();
  renderKeywordHighlightPreview();
  renderSubmitState();
  renderTasks();
  renderModalVisibility();
  setModalMessage(state.form.modalMessage, state.form.modalMessageType);
  persistState();
}

function readAndRender() {
  readFormFromDom();
  renderAll();
}

function extractSpeakerNumbers(text) {
  const normalized = normalizeText(text);
  if (!normalized) {
    return { error: "文本内容不能为空", speakerNumbers: [] };
  }
  if (normalized.length > AUDIO_TEXT_MAX_CHARS) {
    return { error: `文本过长，请缩短到 ${AUDIO_TEXT_MAX_CHARS} 个字符以内后再生成音频`, speakerNumbers: [] };
  }

  const lines = normalized.split("\n");
  const seen = new Set();
  let hasSpeakerLine = false;

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index].trim();
    if (!line) continue;
    const match = line.match(/^Speaker\s*(\d+)\s*[:：]\s*(.+)$/i);
    if (match) {
      const speakerNumber = Number(match[1]);
      if (!Number.isInteger(speakerNumber) || speakerNumber < 1) {
        return { error: `第 ${index + 1} 行的 Speaker 编号无效`, speakerNumbers: [] };
      }
      seen.add(speakerNumber);
      hasSpeakerLine = true;
      continue;
    }
    if (!hasSpeakerLine) {
      return { error: `第 ${index + 1} 行格式无效，请使用“Speaker N: 内容”`, speakerNumbers: [] };
    }
  }

  if (!seen.size) {
    return { error: "文本内容不能为空", speakerNumbers: [] };
  }

  const sorted = [...seen].sort((a, b) => a - b);
  for (let speaker = 1; speaker <= sorted[sorted.length - 1]; speaker += 1) {
    if (!seen.has(speaker)) {
      return { error: "Speaker 编号必须从 1 开始连续", speakerNumbers: [] };
    }
  }

  return { error: "", speakerNumbers: sorted };
}

function validateSpeakerConsistency(text) {
  const parsed = extractSpeakerNumbers(text);
  if (parsed.error) return parsed.error;
  if (parsed.speakerNumbers.length !== speakerCountValue()) {
    return "说话人数与文本中的 Speaker 数量不符，请检查后重试";
  }
  return "";
}

function missingKeywordTerms(text) {
  const normalized = normalizeText(text).toLocaleLowerCase();
  if (!normalized) {
    return [...state.form.keywords];
  }
  return state.form.keywords.filter((keyword) => !normalized.includes(String(keyword || "").trim().toLocaleLowerCase()));
}

function validateLlmBeforeGenerateText() {
  const topicMode = currentTopicInputMode();
  const topic = resolvedLlmTopic();
  const templateValue = el.templateSelect.value;
  const wordCount = Number(el.wordCountLimit.value || 0);

  if (topicMode === "preset" && !el.presetTopicSelect.value) {
    return "请选择预置文本主题";
  }
  if (!topic) {
    return "请先填写文本主题";
  }
  if (!templateValue) {
    return "请选择主题模板";
  }
  if (templateValue === "custom" && !normalizeText(el.customPrompt.value)) {
    return "选择自定义模板后，请填写自定义 Prompt";
  }
  if (!el.llmLanguage.value) {
    return "请选择文本语言";
  }
  if (speakerCountValue() < 2) {
    return "LLM 生成对话时，说话人数至少需要 2 人";
  }
  if (!Number.isInteger(wordCount) || wordCount < 100 || wordCount > 3000) {
    return "字数限制需在 100 到 3000 之间";
  }
  return "";
}

function validateBeforeSubmit() {
  if (!allVoicesSelected()) {
    return "请为所有说话人选择音色";
  }
  if (!el.outputFormat.value) {
    return "请选择音频输出格式";
  }

  if (currentMode() === "llm") {
    const llmError = validateLlmBeforeGenerateText();
    if (llmError) return llmError;

    const previewText = normalizeText(el.previewText.value);
    if (!previewText) {
      return "请先根据以上配置生成文本";
    }

    const speakerError = validateSpeakerConsistency(previewText);
    if (speakerError) return speakerError;

    const missingKeywords = missingKeywordTerms(previewText);
    if (missingKeywords.length) {
      return `以下关键词尚未体现在文本中：${missingKeywords.join("、")}`;
    }
    return "";
  }

  if (!el.manualTopic.value.trim()) return "请先填写文本主题";
  if (!el.manualLanguage.value) return "请选择文本语言";
  if (!normalizeText(el.manualText.value)) return "请先输入文本内容";
  return validateSpeakerConsistency(el.manualText.value);
}

function buildProfileFromTemplate(templateLabel, topic, generationContext = null) {
  const context = generationContext || buildGenerationContext(templateLabel, topic, []);
  const normalizedTopic = String(topic || "在线生成音频").trim() || "在线生成音频";
  return {
    job_function: context.primaryRole || context.label || "通用对话",
    work_content: normalizedTopic,
    seniority: "资深",
    use_case: `${context.domain || "通用业务"}｜${context.scene_type || context.label || "场景讨论"}`
  };
}

function buildManualTopicScenario(templateLabel, topic, generationContext = null) {
  const context = generationContext || buildGenerationContext(templateLabel, topic, []);
  const normalizedTopic = String(topic || "").trim() || context.scene_type || "业务议题";
  const roles = (context.role_briefs || []).join("、");
  const axes = (context.discussion_axes || []).slice(0, 5).join("、");
  return `场景：${context.scene_goal}。参与角色：${roles}。重点讨论：${axes}。最终目标：${context.deliverable}。主题：${normalizedTopic}。`;
}

function buildManualTopicCoreContent(templateLabel, topic, generationContext = null) {
  const context = generationContext || buildGenerationContext(templateLabel, topic, state.form.keywords);
  const keywordTerms = [...state.form.keywords];
  const contentParts = [
    `文本主题：${topic}`,
    `主题模板：${templateLabel}`,
    `行业场景：${context.domain}，场景类型：${context.scene_type}`,
    `角色分工：${(context.role_briefs || []).join("、")}`,
    `讨论重点：${(context.discussion_axes || []).join("、")}`,
    `目标输出：${context.deliverable}`,
    `写作要求：${(context.quality_constraints || []).join("；")}`
  ];

  if (keywordTerms.length) {
    contentParts.push(`核心对话内容：对话中必须明确体现这些关键词——${keywordTerms.join("，")}`);
  }
  if (normalizeText(el.customPrompt.value)) {
    contentParts.push(`补充要求：${normalizeText(el.customPrompt.value)}`);
  }

  return contentParts.join("；");
}

function buildGenerateTextPayload() {
  const template = templateOptionByValue(el.templateSelect.value);
  const topic = resolvedLlmTopic();
  const wordCount = Number(el.wordCountLimit.value || DEFAULT_WORD_COUNT);
  const keywordTerms = [...state.form.keywords];
  const preset = currentPresetTopic();
  const generationContext = buildGenerationContext(template.label, topic, keywordTerms);

  if (currentTopicInputMode() === "preset" && preset) {
    const coreParts = [];
    if (preset.core_content) {
      coreParts.push(preset.core_content);
    }
    coreParts.push(`角色分工：${generationContext.role_briefs.join("、")}`);
    coreParts.push(`讨论重点：${generationContext.discussion_axes.join("、")}`);
    coreParts.push(`目标输出：${generationContext.deliverable}`);
    coreParts.push(`写作要求：${generationContext.quality_constraints.join("；")}`);
    if (keywordTerms.length) {
      coreParts.push(`核心对话内容：请在最终文本中明确体现这些关键词——${keywordTerms.join("，")}`);
    }
    if (normalizeText(el.customPrompt.value)) {
      coreParts.push(`补充要求：${normalizeText(el.customPrompt.value)}`);
    }

    return {
      title: preset.topic_text || topic,
      profile: preset.profile || buildProfileFromTemplate(template.label, preset.topic_text || topic, generationContext),
      scenario: `${preset.scenario || buildManualTopicScenario(template.label, preset.topic_text || topic, generationContext)} 参与角色：${generationContext.role_briefs.join("、")}。`,
      core_content: coreParts.join("；"),
      people_count: speakerCountValue(),
      word_count: wordCount,
      language: el.llmLanguage.value,
      audio_language: el.llmLanguage.value,
      template_label: template.label,
      tags: state.form.tags,
      folder: el.folderSelect.value,
      source_mode: "llm",
      keyword_terms: keywordTerms,
      topic_input_mode: "preset",
      preset_id: preset.id,
      preset_source_title: preset.source_title || "",
      generation_context: generationContext
    };
  }

  return {
    title: topic,
    profile: buildProfileFromTemplate(template.label, topic, generationContext),
    scenario: buildManualTopicScenario(template.label, topic, generationContext),
    core_content: buildManualTopicCoreContent(template.label, topic, generationContext),
    people_count: speakerCountValue(),
    word_count: wordCount,
    language: el.llmLanguage.value,
    audio_language: el.llmLanguage.value,
    template_label: template.label,
    tags: state.form.tags,
    folder: el.folderSelect.value,
    source_mode: "llm",
    keyword_terms: keywordTerms,
    topic_input_mode: "manual",
    generation_context: generationContext
  };
}

function buildManualCreatePayload() {
  return {
    title: el.manualTopic.value.trim(),
    dialogue_text: normalizeText(el.manualText.value),
    language: el.manualLanguage.value,
    audio_language: el.manualLanguage.value,
    people_count: speakerCountValue(),
    scenario: el.manualTopic.value.trim(),
    template_label: "直接输入",
    keyword_terms: [...state.form.keywords],
    tags: state.form.tags,
    folder: el.folderSelect.value,
    source_mode: "manual"
  };
}

function buildAudioPayload(dialogueId, dialogueText) {
  return {
    dialogue_id: dialogueId,
    dialogue_text: normalizeText(dialogueText),
    language: currentLanguageBackend(),
    format: String(el.outputFormat.value || "MP3").toLowerCase(),
    include_scripts: el.includeScripts.checked,
    precise_duration: el.preciseDuration.value || "",
    voice_map: gatherVoiceAssignments()
  };
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const rawText = await response.text();
  let payload;

  if (contentType.includes("application/json")) {
    try {
      payload = rawText ? JSON.parse(rawText) : {};
    } catch (error) {
      const compact = rawText.replace(/\s+/g, " ").trim();
      payload = {
        success: false,
        error: compact.startsWith("<")
          ? `接口返回了非 JSON 错误页（${response.status}）`
          : compact || `请求失败: ${response.status}`
      };
    }
  } else {
    payload = { success: false, error: rawText };
  }

  if (!response.ok || payload.ok === false || payload.success === false) {
    throw new Error(payload.error || payload.reason || `请求失败: ${response.status}`);
  }
  return payload;
}

function buildTaskSnapshot(dialogueId, dialogueText, textFileName) {
  const formSnapshot = snapshotCurrentForm();
  return {
    dialogueId,
    textFileName,
    dialogueText,
    form: {
      ...formSnapshot,
      dialogueId,
      generatedTextFileName: textFileName || formSnapshot.generatedTextFileName || "",
      previewText: currentMode() === "llm" ? dialogueText : formSnapshot.previewText,
      manualText: currentMode() === "manual" ? dialogueText : formSnapshot.manualText
    }
  };
}

function taskSnapshotToForm(snapshot) {
  if (!snapshot || !snapshot.form) return null;
  const form = snapshot.form;
  return {
    ...createDefaultFormState(),
    ...form,
    keywords: Array.isArray(form.keywords) ? [...form.keywords] : [],
    tags: Array.isArray(form.tags) ? [...form.tags] : [],
    voiceAssignments: cloneVoiceAssignments(form.voiceAssignments || {}),
    isGeneratingText: false,
    isSubmittingAudio: false,
    modalMessage: "已载入历史任务，可继续查看、编辑并重新生成音频。",
    modalMessageType: "info"
  };
}

function legacyTaskToForm(task) {
  const title = String(task?.title || "").trim();
  if (!title) return null;
  return {
    ...createDefaultFormState(),
    mode: "llm",
    llmTopic: title,
    manualTopic: title,
    dialogueId: String(task?.dialogueId || ""),
    generatedTextFileName: String(task?.textFileName || ""),
    outputFormat: String(task?.outputFormat || "MP3"),
    modalMessage: task?.errorMessage
      ? `已恢复历史失败任务的基础信息。原失败原因：${task.errorMessage}`
      : "已恢复历史任务的基础信息。",
    modalMessageType: task?.errorMessage ? "error" : "info"
  };
}

function normalizeTask(task) {
  const normalized = {
    id: task?.id || `${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
    title: String(task?.title || "未命名任务"),
    createdAt: String(task?.createdAt || nowIsoString()),
    sourceLabel: task?.sourceLabel === "上传" ? "上传" : "生成",
    status: String(task?.status || "文本生成中"),
    fileName: String(task?.fileName || ""),
    textFileName: String(task?.textFileName || ""),
    textDownloadUrl: String(task?.textDownloadUrl || ""),
    audioDownloadUrl: String(task?.audioDownloadUrl || ""),
    errorMessage: String(task?.errorMessage || ""),
    dialogueId: String(task?.dialogueId || ""),
    snapshot: task?.snapshot && task.snapshot.form ? task.snapshot : null
  };
  if (!normalized.snapshot && normalized.title) {
    normalized.snapshot = {
      dialogueId: normalized.dialogueId,
      textFileName: normalized.textFileName,
      dialogueText: "",
      form: legacyTaskToForm(normalized)
    };
  }
  return normalized;
}

function detailPayloadToForm(payload) {
  const manifest = payload?.manifest || {};
  const sourceMode = manifest.source_mode === "manual" ? "manual" : "llm";
  const templateValue = manifest.template_label
    ? ensureTemplateOption(normalizeTemplateDropdownLabel(manifest.template_label))
    : BASE_TEMPLATE_OPTIONS[0].value;
  const outputFormat = String(manifest.audio_output_format || "mp3").toUpperCase();
  const normalizedKeywords = Array.isArray(manifest.keyword_terms) ? manifest.keyword_terms : [];
  const normalizedTags = Array.isArray(manifest.tags) ? manifest.tags : [];
  const topicInputMode = manifest.topic_input_mode === "preset" && manifest.preset_id ? "preset" : "manual";

  return {
    ...createDefaultFormState(),
    mode: sourceMode,
    topicInputMode,
    llmTopic: sourceMode === "llm" ? String(manifest.title || "") : "",
    selectedPresetId: topicInputMode === "preset" ? String(manifest.preset_id || "") : "",
    template: templateValue,
    llmLanguage: String(manifest.audio_language || LANGUAGE_OPTIONS[0].backend),
    wordCountLimit: String(manifest.word_count || DEFAULT_WORD_COUNT),
    keywords: [...normalizedKeywords],
    manualTopic: sourceMode === "manual" ? String(manifest.title || "") : "",
    manualLanguage: String(manifest.audio_language || LANGUAGE_OPTIONS[0].backend),
    manualText: sourceMode === "manual" ? String(payload.dialogue_text || "") : "",
    speakerCount: Math.min(10, Math.max(1, Number(manifest.people_count) || 2)),
    previewText: sourceMode === "llm" ? String(payload.dialogue_text || "") : "",
    dialogueId: String(payload.dialogue_id || ""),
    generatedTextFileName: String(payload.text_file_name || ""),
    voiceAssignments: cloneVoiceAssignments(manifest.voice_map || {}),
    outputFormat: ["MP3", "WAV", "M4A"].includes(outputFormat) ? outputFormat : "MP3",
    preciseDuration: String(manifest.precise_duration || ""),
    folder: String(manifest.folder || "默认目录"),
    tags: [...normalizedTags],
    includeScripts: Boolean(manifest.include_scripts),
    isGeneratingText: false,
    isSubmittingAudio: false,
    modalMessage: "已从任务列表恢复该任务，可继续查看或调整参数。",
    modalMessageType: "info"
  };
}

async function fetchTaskDetail(dialogueId) {
  return fetchJson(`/api/dialogue_detail?dialogue_id=${encodeURIComponent(dialogueId)}`);
}

function isNetworkFetchError(error) {
  const message = String(error?.message || "");
  return error instanceof TypeError || /Failed to fetch|NetworkError|Load failed|网络/i.test(message);
}

async function openTaskInModal(task) {
  let nextForm = taskSnapshotToForm(task.snapshot);
  if (!nextForm && task.dialogueId) {
    try {
      const detail = await fetchTaskDetail(task.dialogueId);
      nextForm = detailPayloadToForm(detail);
    } catch (error) {
      if (isNetworkFetchError(error)) {
        throw new Error("当前 demo 服务未连接，且该任务没有本地快照。请先启动服务后再查看任务。");
      }
      nextForm = legacyTaskToForm(task);
      if (!nextForm) {
        throw error;
      }
      nextForm.modalMessage = `该任务无法完整回放，已恢复基础参数。原错误：${error.message}`;
      nextForm.modalMessageType = "error";
    }
  }
  if (!nextForm) {
    nextForm = legacyTaskToForm(task);
  }
  if (!nextForm) {
    throw new Error("该任务缺少可恢复的参数信息");
  }

  state.form = nextForm;
  state.modalOpen = true;
  renderAll();
  openModal();
}

function triggerBrowserDownload(blob, fileName) {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = fileName || "download";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}

async function downloadTaskAsset(task, kind) {
  const url = kind === "audio" ? task.audioDownloadUrl : task.textDownloadUrl;
  if (!url) {
    throw new Error(kind === "audio" ? "当前任务暂无可下载音频" : "当前任务暂无可下载文本");
  }
  const response = await fetch(url);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `下载失败: ${response.status}`);
  }
  const blob = await response.blob();
  const fileName = kind === "audio" ? task.fileName : task.textFileName;
  triggerBrowserDownload(blob, fileName);
}

function initModalResize() {
  if (!el.modalPanel || !el.modalResizeHandle) return;

  el.modalResizeHandle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    const startX = event.clientX;
    const startY = event.clientY;
    const rect = el.modalPanel.getBoundingClientRect();
    const startWidth = rect.width;
    const startHeight = rect.height;

    const move = (moveEvent) => {
      const maxWidth = Math.max(760, window.innerWidth - 24);
      const maxHeight = Math.max(560, window.innerHeight - 24);
      state.modalSize = {
        width: Math.min(maxWidth, Math.max(760, startWidth + moveEvent.clientX - startX)),
        height: Math.min(maxHeight, Math.max(560, startHeight + moveEvent.clientY - startY))
      };
      applyModalSize();
    };

    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      persistState();
    };

    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
  });
}

function createTaskPlaceholder() {
  const workingText = currentWorkingText();
  const textFileName = state.form.generatedTextFileName || "";
  const task = {
    id: `${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
    title: currentTitle() || "未命名任务",
    createdAt: nowIsoString(),
    sourceLabel: "生成",
    status: "语音合成中",
    fileName: "",
    textFileName: "",
    textDownloadUrl: "",
    audioDownloadUrl: "",
    errorMessage: "",
    dialogueId: "",
    snapshot: buildTaskSnapshot("", workingText, textFileName)
  };
  state.tasks = [task, ...state.tasks];
  renderTasks();
  persistState();
  return task.id;
}

function removeTasksLocally(taskIds) {
  const idSet = new Set(taskIds);
  state.tasks = state.tasks.filter((task) => !idSet.has(task.id));
  renderTasks();
  persistState();
}

async function deleteTaskRemotely(dialogueId) {
  if (!dialogueId) {
    return { deleted: false, not_found: true };
  }
  return fetchJson("/api/delete_task", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dialogue_id: dialogueId })
  });
}

async function handleDeleteTask(task) {
  const confirmed = window.confirm(`确认删除任务“${task.title || "未命名任务"}”？`);
  if (!confirmed) return;

  let remoteError = "";
  if (task.dialogueId) {
    try {
      await deleteTaskRemotely(task.dialogueId);
    } catch (error) {
      remoteError = error.message;
    }
  }

  removeTasksLocally([task.id]);
  if (remoteError) {
    showToast("error", `任务已从列表移除，但服务端文件清理失败：${remoteError}`);
    return;
  }
  showToast("success", "任务已删除");
}

async function cleanupOldTasks() {
  const staleTasks = state.tasks.filter((task) => isTaskStale(task));
  if (!staleTasks.length) {
    showToast("info", "当前没有需要清理的过时任务");
    return;
  }

  const confirmed = window.confirm(`确认清理 ${staleTasks.length} 条过时任务？这会同时清理可找到的本地生成文件。`);
  if (!confirmed) return;

  let remoteFailures = 0;
  for (const task of staleTasks) {
    if (!task.dialogueId) continue;
    try {
      await deleteTaskRemotely(task.dialogueId);
    } catch (error) {
      remoteFailures += 1;
    }
  }

  removeTasksLocally(staleTasks.map((task) => task.id));
  if (remoteFailures) {
    showToast("error", `已清理 ${staleTasks.length} 条过时任务，其中 ${remoteFailures} 条服务端文件未成功删除`);
    return;
  }
  showToast("success", `已清理 ${staleTasks.length} 条过时任务`);
}

function updateTask(taskId, patch) {
  state.tasks = state.tasks.map((task) => (task.id === taskId ? normalizeTask({ ...task, ...patch }) : task));
  renderTasks();
  persistState();
}

async function loadServerInfo() {
  try {
    const payload = await fetchJson("/api/server_info");
    state.serverInfo = payload;
    renderShareBox(payload);
  } catch (error) {
    state.serverInfo = null;
    el.sharePrimaryLink.textContent = "获取失败";
    el.sharePrimaryLink.href = "#";
    el.copyShareBtn.disabled = true;
    el.shareHint.textContent = `获取访问地址失败：${error.message}`;
  }
}

async function loadPresetTopics() {
  try {
    const payload = await fetchJson("/api/preset_topics");
    state.presetTopics = Array.isArray(payload.presets) ? payload.presets : [];
    const currentTemplateLabel = normalizeTemplateDropdownLabel(templateOptionByValue(state.form.template)?.label || "");
    state.templateOptions = buildTemplateOptionsFromPresets(state.presetTopics);
    state.form.template = currentTemplateLabel ? ensureTemplateOption(currentTemplateLabel) : state.templateOptions[0]?.value || "";

    if (state.form.selectedPresetId && !presetTopicById(state.form.selectedPresetId)) {
      state.form.selectedPresetId = "";
    }

    if (state.form.selectedPresetId) {
      applyPresetSelection(currentPresetTopic(), { render: false });
    }
  } catch (error) {
    state.presetTopics = [];
    state.templateOptions = [...BASE_TEMPLATE_OPTIONS];
    state.form.template = state.templateOptions[0]?.value || "";
    console.warn("loadPresetTopics failed", error);
    setModalMessage(`预置文本主题加载失败：${error.message}`, "error");
  }
}

async function refreshPresetTopicsIfNeeded(force = false) {
  if (!force && state.presetTopics.length) {
    return;
  }
  await loadPresetTopics();
  renderAll();
}

function applyPresetSelection(preset, options = {}) {
  const { render = true } = options;
  if (!preset) {
    state.form.selectedPresetId = "";
    if (render) renderAll();
    return;
  }

  state.form.selectedPresetId = preset.id;
  const templateLabel = templateDisplayLabelFromPreset(preset);
  if (templateLabel) {
    state.form.template = ensureTemplateOption(templateLabel);
  }
  if (preset.language) {
    state.form.llmLanguage = preset.language;
  }
  if (preset.word_count || preset.default_word_count) {
    state.form.wordCountLimit = String(preset.word_count || preset.default_word_count);
  }
  if (preset.people_count || preset.recommended_people_count) {
    state.form.speakerCount = Math.min(
      10,
      Math.max(1, Number(preset.people_count || preset.recommended_people_count) || state.form.speakerCount || 2)
    );
  }
  if (render) {
    renderAll();
  }
}

async function copyShareLink() {
  const link = el.sharePrimaryLink.href && el.sharePrimaryLink.href !== "#" ? el.sharePrimaryLink.href : "";
  if (!link) return;
  try {
    await navigator.clipboard.writeText(link);
    showToast("success", "访问地址已复制");
  } catch (error) {
    showToast("error", `复制失败，请手动复制：${link}`);
  }
}

async function handleGenerateText() {
  readFormFromDom();
  const error = validateLlmBeforeGenerateText();
  if (error) {
    setModalMessage(error, "error");
    showToast("error", error);
    return;
  }

  if (normalizeText(el.previewText.value)) {
    const confirmed = window.confirm("确认重新生成文本？当前文本将被覆盖。");
    if (!confirmed) return;
  }

  state.form.isGeneratingText = true;
  setModalMessage("正在根据当前配置生成文本...", "info");
  renderSubmitState();
  persistState();

  try {
    const payload = await fetchJson("/api/generate_text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildGenerateTextPayload())
    });

    state.form.dialogueId = payload.dialogue_id || "";
    state.form.generatedTextFileName = payload.file_name || "";
    state.form.previewText = payload.dialogue_text || "";
    el.previewText.value = payload.dialogue_text || "";

    const enforcedKeywords = Array.isArray(payload.debug?.keywords_enforced) ? payload.debug.keywords_enforced : [];
    if (enforcedKeywords.length) {
      const message = `文本生成完成，已补入关键词：${enforcedKeywords.join("、")}`;
      setModalMessage(message, "success");
      showToast("success", message);
    } else {
      setModalMessage("文本生成完成，可继续编辑并提交音频生成。", "success");
      showToast("success", "文本生成完成，可在下方预览和编辑");
    }
  } catch (requestError) {
    setModalMessage(`文本生成失败：${requestError.message}`, "error");
    showToast("error", `文本生成失败：${requestError.message}`);
  } finally {
    state.form.isGeneratingText = false;
    renderAll();
  }
}

async function submitAudioGeneration() {
  readFormFromDom();
  const validationError = validateBeforeSubmit();
  if (validationError) {
    setModalMessage(validationError, "error");
    showToast("error", validationError);
    renderSubmitState();
    return;
  }

  const taskId = createTaskPlaceholder();
  let dialogueId = state.form.dialogueId;
  let workingText = currentWorkingText();
  let textDownloadUrl = "";
  let textFileName = state.form.generatedTextFileName || "";
  state.form.isSubmittingAudio = true;
  setModalMessage("任务已提交，正在生成音频...", "info");
  renderSubmitState();
  persistState();

  try {
    if (currentMode() === "manual") {
      const createPayload = await fetchJson("/api/create_dialogue_from_text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildManualCreatePayload())
      });
      dialogueId = createPayload.dialogue_id;
      state.form.dialogueId = dialogueId;
      textDownloadUrl = createPayload.text_download_url || "";
      textFileName = createPayload.file_name || textFileName;
      workingText = createPayload.dialogue_text || workingText;
    } else if (!dialogueId) {
      const template = templateOptionByValue(el.templateSelect.value);
      const recoveryPayload = await fetchJson("/api/create_dialogue_from_text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: currentTitle(),
          dialogue_text: workingText,
          language: currentLanguageBackend(),
          audio_language: currentLanguageBackend(),
          people_count: speakerCountValue(),
          scenario: buildManualTopicScenario(template.label, currentTitle()),
          template_label: template.label,
          tags: state.form.tags,
          folder: el.folderSelect.value,
          source_mode: "llm"
        })
      });
      dialogueId = recoveryPayload.dialogue_id;
      state.form.dialogueId = dialogueId;
      textDownloadUrl = recoveryPayload.text_download_url || "";
      textFileName = recoveryPayload.file_name || textFileName;
      workingText = recoveryPayload.dialogue_text || workingText;
    } else {
      textDownloadUrl = `/api/download?dialogue_id=${encodeURIComponent(dialogueId)}&kind=text`;
    }

    const audioPayload = await fetchJson("/api/generate_audio_custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildAudioPayload(dialogueId, workingText))
    });

    updateTask(taskId, {
      status: "生成成功",
      createdAt: audioPayload.updated_at || nowIsoString(),
      dialogueId,
      fileName: audioPayload.file_name || basenameFromPath(audioPayload.audio_file_path),
      textFileName: textFileName || basenameFromPath(state.form.generatedTextFileName),
      textDownloadUrl: textDownloadUrl || `/api/download?dialogue_id=${encodeURIComponent(dialogueId)}&kind=text`,
      audioDownloadUrl: audioPayload.audio_download_url || `/api/download?dialogue_id=${encodeURIComponent(dialogueId)}&kind=audio`,
      snapshot: buildTaskSnapshot(dialogueId, workingText, textFileName || basenameFromPath(state.form.generatedTextFileName))
    });

    state.modalOpen = false;
    showToast("success", "任务已提交，请在生成任务列表查看进度");
    resetForm();
  } catch (requestError) {
    updateTask(taskId, {
      status: "生成失败",
      errorMessage: requestError.message,
      dialogueId,
      textFileName,
      textDownloadUrl,
      snapshot: buildTaskSnapshot(dialogueId, workingText, textFileName)
    });
    setModalMessage(`音频生成失败：${requestError.message}`, "error");
    showToast("error", `音频生成失败：${requestError.message}`);
  } finally {
    state.form.isSubmittingAudio = false;
    renderAll();
  }
}

async function handleTaskTableClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const task = state.tasks.find((item) => item.id === button.dataset.id);
  if (!task) return;

  try {
    if (button.dataset.action === "view-task" && taskCanOpen(task)) {
      await openTaskInModal(task);
      return;
    }
    if (button.dataset.action === "download-text" && task.textDownloadUrl) {
      await downloadTaskAsset(task, "text");
      return;
    }
    if (button.dataset.action === "download-audio" && task.audioDownloadUrl) {
      await downloadTaskAsset(task, "audio");
      return;
    }
    if (button.dataset.action === "show-error" && task.errorMessage) {
      showToast("error", task.errorMessage);
      return;
    }
    if (button.dataset.action === "delete-task") {
      await handleDeleteTask(task);
    }
  } catch (error) {
    const actionLabelMap = {
      "view-task": "任务回看",
      "download-text": "文本下载",
      "download-audio": "音频下载",
      "delete-task": "任务删除"
    };
    const actionLabel = actionLabelMap[button.dataset.action] || "操作";
    showToast("error", `${actionLabel}失败：${error.message}`);
  }
}

function bindEvents() {
  initModalResize();
  window.addEventListener("resize", applyModalSize);
  el.copyShareBtn.addEventListener("click", copyShareLink);
  el.cleanupOldTasksBtn.addEventListener("click", () => {
    void cleanupOldTasks();
  });
  el.uploadBtn.addEventListener("click", () => {
    showToast("info", "演示版当前只开放“在线生成音频”流程。");
  });
  el.openOnlineAudioBtn.addEventListener("click", openModal);
  el.closeModalBtn.addEventListener("click", closeModal);
  el.cancelModalBtn.addEventListener("click", closeModal);

  el.modeCardLlm.addEventListener("click", (event) => {
    event.preventDefault();
    if (state.form.isGeneratingText || state.form.isSubmittingAudio) return;
    setMode("llm");
  });
  el.modeCardManual.addEventListener("click", (event) => {
    event.preventDefault();
    if (state.form.isGeneratingText || state.form.isSubmittingAudio) return;
    setMode("manual");
  });
  el.modeLlm.addEventListener("change", readAndRender);
  el.modeManual.addEventListener("change", readAndRender);

  el.topicModeCardManual.addEventListener("click", (event) => {
    event.preventDefault();
    if (state.form.isGeneratingText || state.form.isSubmittingAudio) return;
    setTopicInputMode("manual");
  });
  el.topicModeCardPreset.addEventListener("click", (event) => {
    event.preventDefault();
    if (state.form.isGeneratingText || state.form.isSubmittingAudio) return;
    setTopicInputMode("preset");
  });
  el.topicModeManual.addEventListener("change", readAndRender);
  el.topicModePreset.addEventListener("change", readAndRender);
  el.presetTopicSelect.addEventListener("pointerdown", () => {
    if (!state.presetTopics.length) {
      void refreshPresetTopicsIfNeeded(true);
    }
  });

  el.templateSelect.addEventListener("change", readAndRender);
  el.llmLanguage.addEventListener("change", readAndRender);
  el.manualLanguage.addEventListener("change", readAndRender);
  el.speakerCount.addEventListener("change", readAndRender);
  el.speakerCount.addEventListener("input", readAndRender);
  el.outputFormat.addEventListener("change", readAndRender);
  el.includeScripts.addEventListener("change", readAndRender);

  el.llmTopic.addEventListener("input", () => {
    state.form.llmTopic = el.llmTopic.value;
    persistState();
  });
  el.customPrompt.addEventListener("input", () => {
    state.form.customPrompt = el.customPrompt.value;
    persistState();
  });
  el.wordCountLimit.addEventListener("input", () => {
    state.form.wordCountLimit = el.wordCountLimit.value;
    persistState();
  });
  el.presetTopicSelect.addEventListener("change", () => {
    applyPresetSelection(presetTopicById(el.presetTopicSelect.value));
  });

  el.manualTopic.addEventListener("input", () => {
    state.form.manualTopic = el.manualTopic.value;
    persistState();
  });
  el.manualText.addEventListener("input", () => {
    state.form.manualText = el.manualText.value;
    persistState();
  });
  el.previewText.addEventListener("input", () => {
    state.form.previewText = el.previewText.value;
    renderModeUi();
    renderKeywordHighlightPreview();
    renderSubmitState();
    persistState();
  });
  el.preciseDuration.addEventListener("input", () => {
    state.form.preciseDuration = el.preciseDuration.value;
    persistState();
  });
  el.folderSelect.addEventListener("change", () => {
    state.form.folder = el.folderSelect.value;
    persistState();
  });

  el.keywordInput.addEventListener("keydown", (event) => handleTagInputKeydown(event, addKeyword));
  el.keywordInput.addEventListener("blur", (event) => handleTagInputBlur(event, addKeyword));
  el.tagInput.addEventListener("keydown", (event) => handleTagInputKeydown(event, addTag));
  el.tagInput.addEventListener("blur", (event) => handleTagInputBlur(event, addTag));

  el.generateTextBtn.addEventListener("click", handleGenerateText);
  el.regenTextBtn.addEventListener("click", handleGenerateText);
  el.submitAudioBtn.addEventListener("click", submitAudioGeneration);
  el.taskTableBody.addEventListener("click", handleTaskTableClick);
}

async function init() {
  restoreState();
  await loadPresetTopics();
  bindEvents();
  renderAll();
  await loadServerInfo();
  if (state.modalOpen) {
    openModal();
  }
}

init();
