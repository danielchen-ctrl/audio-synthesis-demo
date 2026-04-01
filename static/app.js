const STORAGE_KEY = "online_audio_generation_demo_v2";
const AUDIO_TEXT_MAX_CHARS = 12000;
const DEFAULT_WORD_COUNT = "1000";
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

const BASE_TEMPLATE_OPTIONS = [
  { value: "meeting", label: "会议讨论" },
  { value: "interview", label: "访谈" },
  { value: "medical", label: "问诊" },
  { value: "review", label: "评审会" },
  { value: "customer", label: "客户访谈" },
  { value: "internal", label: "内部会议" },
  { value: "decision", label: "方案决策" },
  { value: "troubleshooting", label: "问题排查" },
  { value: "strategy", label: "战略周会" },
  { value: "other", label: "其他" },
  { value: "custom", label: "自定义" }
];

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
    template: BASE_TEMPLATE_OPTIONS[0].value,
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

function dynamicTemplateValue(label) {
  const code = Array.from(String(label || "其他"))
    .map((char) => char.codePointAt(0).toString(16))
    .join("")
    .slice(0, 24);
  return `dynamic_${code || "template"}`;
}

function ensureTemplateOption(label) {
  const normalized = String(label || "").trim();
  if (!normalized) {
    return state.templateOptions[0]?.value || BASE_TEMPLATE_OPTIONS[0].value;
  }
  const existing = templateOptionByLabel(normalized);
  if (existing) return existing.value;
  const next = { value: dynamicTemplateValue(normalized), label: normalized };
  state.templateOptions = [...state.templateOptions, next];
  return next.value;
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
    state.tasks = Array.isArray(cached.tasks) ? cached.tasks : [];
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
            task.dialogueId ? "" : "disabled"
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

function buildProfileFromTemplate(templateLabel, topic) {
  const normalizedTemplate = String(templateLabel || "通用对话").trim() || "通用对话";
  const normalizedTopic = String(topic || "在线生成音频").trim() || "在线生成音频";
  return {
    job_function: normalizedTemplate,
    work_content: normalizedTopic,
    seniority: "标准",
    use_case: normalizedTemplate
  };
}

function buildManualTopicScenario(templateLabel, topic) {
  const normalizedTemplate = String(templateLabel || "通用对话").trim() || "通用对话";
  const normalizedTopic = String(topic || "").trim();
  if (!normalizedTopic) {
    return `${normalizedTemplate}场景对话`;
  }
  return `${normalizedTemplate}：围绕“${normalizedTopic}”展开真实自然的多轮场景对话`;
}

function buildManualTopicCoreContent(templateLabel, topic) {
  const keywordTerms = [...state.form.keywords];
  const contentParts = [
    `文本主题：${topic}`,
    `主题模板：${templateLabel}`,
    `请生成自然、真实、口语化的多轮对话文本`
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

  if (currentTopicInputMode() === "preset" && preset) {
    const coreParts = [];
    if (preset.core_content) {
      coreParts.push(preset.core_content);
    }
    if (keywordTerms.length) {
      coreParts.push(`核心对话内容：请在最终文本中明确体现这些关键词——${keywordTerms.join("，")}`);
    }
    if (normalizeText(el.customPrompt.value)) {
      coreParts.push(`补充要求：${normalizeText(el.customPrompt.value)}`);
    }

    return {
      title: preset.topic_text || topic,
      profile: preset.profile || buildProfileFromTemplate(template.label, preset.topic_text || topic),
      scenario: preset.scenario || buildManualTopicScenario(template.label, preset.topic_text || topic),
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
      preset_source_title: preset.source_title || ""
    };
  }

  return {
    title: topic,
    profile: buildProfileFromTemplate(template.label, topic),
    scenario: buildManualTopicScenario(template.label, topic),
    core_content: buildManualTopicCoreContent(template.label, topic),
    people_count: speakerCountValue(),
    word_count: wordCount,
    language: el.llmLanguage.value,
    audio_language: el.llmLanguage.value,
    template_label: template.label,
    tags: state.form.tags,
    folder: el.folderSelect.value,
    source_mode: "llm",
    keyword_terms: keywordTerms,
    topic_input_mode: "manual"
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
  const payload = contentType.includes("application/json")
    ? await response.json()
    : { success: false, error: await response.text() };

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

function detailPayloadToForm(payload) {
  const manifest = payload?.manifest || {};
  const sourceMode = manifest.source_mode === "manual" ? "manual" : "llm";
  const templateValue = manifest.template_label ? ensureTemplateOption(manifest.template_label) : BASE_TEMPLATE_OPTIONS[0].value;
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

async function openTaskInModal(task) {
  let nextForm = taskSnapshotToForm(task.snapshot);
  if (!nextForm && task.dialogueId) {
    const detail = await fetchTaskDetail(task.dialogueId);
    nextForm = detailPayloadToForm(detail);
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
    dialogueId: ""
  };
  state.tasks = [task, ...state.tasks];
  renderTasks();
  persistState();
  return task.id;
}

function updateTask(taskId, patch) {
  state.tasks = state.tasks.map((task) => (task.id === taskId ? { ...task, ...patch } : task));
  renderTasks();
  persistState();
}

async function loadServerInfo() {
  try {
    const payload = await fetchJson("/api/server_info");
    state.serverInfo = payload;
    renderShareBox(payload);
  } catch (error) {
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
    state.templateOptions = [...BASE_TEMPLATE_OPTIONS];
    state.presetTopics.forEach((preset) => {
      if (preset.template_label) {
        ensureTemplateOption(preset.template_label);
      }
    });

    if (state.form.selectedPresetId && !presetTopicById(state.form.selectedPresetId)) {
      state.form.selectedPresetId = "";
    }

    if (state.form.selectedPresetId) {
      applyPresetSelection(currentPresetTopic(), { render: false });
    }
  } catch (error) {
    state.presetTopics = [];
    state.templateOptions = [...BASE_TEMPLATE_OPTIONS];
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
  if (preset.template_label) {
    state.form.template = ensureTemplateOption(preset.template_label);
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
  state.form.isSubmittingAudio = true;
  setModalMessage("任务已提交，正在生成音频...", "info");
  renderSubmitState();
  persistState();

  try {
    let dialogueId = state.form.dialogueId;
    let workingText = currentWorkingText();
    let textDownloadUrl = "";
    let textFileName = state.form.generatedTextFileName || "";

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
      errorMessage: requestError.message
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
    if (button.dataset.action === "view-task" && task.dialogueId) {
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
    }
  } catch (error) {
    const actionLabel = button.dataset.action === "view-task" ? "任务回看" : "下载";
    showToast("error", `${actionLabel}失败：${error.message}`);
  }
}

function bindEvents() {
  initModalResize();
  window.addEventListener("resize", applyModalSize);
  el.copyShareBtn.addEventListener("click", copyShareLink);
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
