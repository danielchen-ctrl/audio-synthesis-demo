const STORAGE_KEY = "demo_app_web_state_v4";
const AUDIO_TEXT_MAX_CHARS = 12000;

const profileOptions = {
  job_function: ["后端开发", "产品经理", "运营管理", "零售行业", "金融服务", "法律服务", "医疗健康", "人工智能/科技", "其他"],
  work_content: ["系统建设", "需求管理", "项目推进", "客户沟通", "数据分析", "风险合规", "市场运营", "其他"],
  seniority: ["初级", "中级", "资深", "经理/主管", "总监/负责人", "其他"],
  use_case: ["会议评审", "客户访谈", "内部会议", "方案决策", "问题排查", "其他"]
};

const defaults = {
  peopleCount: "3",
  wordCount: "1000"
};

const state = {
  serverInfo: null,
  progressTimer: null,
  requestIds: {
    text: 0,
    audio: 0
  },
  text: {
    dialogueId: "",
    savedContent: "",
    status: "idle",
    filePath: "",
    updatedAt: "",
    version: 0
  },
  audio: {
    status: "idle",
    filePath: "",
    updatedAt: "",
    basedOnTextVersion: null
  }
};

const el = {
  sharePrimaryLink: document.getElementById("sharePrimaryLink"),
  copyShareBtn: document.getElementById("copyShareBtn"),
  shareHint: document.getElementById("shareHint"),
  serverInfo: document.getElementById("serverInfo"),
  jobFunction: document.getElementById("jobFunction"),
  workContent: document.getElementById("workContent"),
  seniority: document.getElementById("seniority"),
  useCase: document.getElementById("useCase"),
  scenario: document.getElementById("scenario"),
  coreContent: document.getElementById("coreContent"),
  peopleCount: document.getElementById("peopleCount"),
  wordCount: document.getElementById("wordCount"),
  generateTextBtn: document.getElementById("generateTextBtn"),
  generateAudioBtn: document.getElementById("generateAudioBtn"),
  downloadTextBtn: document.getElementById("downloadTextBtn"),
  downloadAudioBtn: document.getElementById("downloadAudioBtn"),
  resetBtn: document.getElementById("resetBtn"),
  progressFill: document.getElementById("progressFill"),
  progressText: document.getElementById("progressText"),
  outputMeta: document.getElementById("outputMeta"),
  dialogueEditor: document.getElementById("dialogueEditor"),
  editStatus: document.getElementById("editStatus"),
  editHint: document.getElementById("editHint"),
  audioStatus: document.getElementById("audioStatus"),
  audioHint: document.getElementById("audioHint"),
  textArtifactName: document.getElementById("textArtifactName"),
  textArtifactMeta: document.getElementById("textArtifactMeta"),
  audioArtifactName: document.getElementById("audioArtifactName"),
  audioArtifactMeta: document.getElementById("audioArtifactMeta")
};

function fillSelect(selectEl, options) {
  selectEl.innerHTML = "";
  options.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    selectEl.appendChild(option);
  });
}

function initProfileOptions() {
  fillSelect(el.jobFunction, profileOptions.job_function);
  fillSelect(el.workContent, profileOptions.work_content);
  fillSelect(el.seniority, profileOptions.seniority);
  fillSelect(el.useCase, profileOptions.use_case);

  el.peopleCount.innerHTML = "";
  for (let i = 2; i <= 10; i += 1) {
    const option = document.createElement("option");
    option.value = String(i);
    option.textContent = String(i);
    if (i === Number(defaults.peopleCount)) {
      option.selected = true;
    }
    el.peopleCount.appendChild(option);
  }
}

function normalizeText(value) {
  return String(value || "").replace(/\r\n/g, "\n").trim();
}

function nowIsoString() {
  return new Date().toISOString();
}

function basenameFromPath(filePath) {
  if (!filePath) return "";
  const normalized = String(filePath).replace(/\\/g, "/");
  const parts = normalized.split("/");
  return parts[parts.length - 1] || "";
}

function formatTimestamp(isoString) {
  if (!isoString) return "未记录时间";
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function currentDialogueText() {
  return normalizeText(el.dialogueEditor.value);
}

function hasCurrentDialogueText() {
  return Boolean(currentDialogueText());
}

function hasPersistedDialogue() {
  return Boolean(state.text.dialogueId);
}

function hasUnsavedDialogueEdits() {
  if (!hasPersistedDialogue()) return false;
  return currentDialogueText() !== normalizeText(state.text.savedContent);
}

function isBusy() {
  return state.text.status === "generating" || state.audio.status === "generating";
}

function isAudioStale() {
  if (state.audio.status === "stale") return true;
  if (!state.audio.filePath) return false;
  if (hasUnsavedDialogueEdits()) return true;
  return state.audio.basedOnTextVersion !== state.text.version;
}

function buildDownloadUrl(kind) {
  if (!hasPersistedDialogue()) return "";
  return `/api/download?dialogue_id=${encodeURIComponent(state.text.dialogueId)}&kind=${kind}&t=${Date.now()}`;
}

function setMeta(message, isError = false) {
  el.outputMeta.classList.toggle("is-error", Boolean(isError));
  el.outputMeta.textContent = message;
}

function clearProgressTimer() {
  if (state.progressTimer) {
    window.clearInterval(state.progressTimer);
    state.progressTimer = null;
  }
}

function startProgress(message) {
  clearProgressTimer();
  let progress = 0;
  el.progressFill.style.width = "0%";
  el.progressText.textContent = message;
  state.progressTimer = window.setInterval(() => {
    progress = Math.min(progress + Math.random() * 14, 92);
    el.progressFill.style.width = `${progress}%`;
  }, 280);
}

function finishProgress(message) {
  clearProgressTimer();
  el.progressFill.style.width = "100%";
  el.progressText.textContent = message;
  window.setTimeout(() => {
    el.progressFill.style.width = "0%";
  }, 1200);
}

function resetProgress(message = "等待开始") {
  clearProgressTimer();
  el.progressFill.style.width = "0%";
  el.progressText.textContent = message;
}

function updateEditorReadonly() {
  const shouldLock = state.text.status === "generating" || state.audio.status === "generating";
  el.dialogueEditor.readOnly = shouldLock;
  el.dialogueEditor.setAttribute("aria-readonly", shouldLock ? "true" : "false");
}

function persistState() {
  const payload = {
    profile: {
      job_function: el.jobFunction.value,
      work_content: el.workContent.value,
      seniority: el.seniority.value,
      use_case: el.useCase.value
    },
    scenario: el.scenario.value,
    coreContent: el.coreContent.value,
    peopleCount: el.peopleCount.value,
    wordCount: el.wordCount.value,
    editorContent: el.dialogueEditor.value,
    text: {
      dialogueId: state.text.dialogueId,
      savedContent: state.text.savedContent,
      status: state.text.status,
      filePath: state.text.filePath,
      updatedAt: state.text.updatedAt,
      version: state.text.version
    },
    audio: {
      status: state.audio.status,
      filePath: state.audio.filePath,
      updatedAt: state.audio.updatedAt,
      basedOnTextVersion: state.audio.basedOnTextVersion
    }
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function restoreState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const cached = JSON.parse(raw);

    el.jobFunction.value = cached.profile?.job_function || el.jobFunction.value;
    el.workContent.value = cached.profile?.work_content || el.workContent.value;
    el.seniority.value = cached.profile?.seniority || el.seniority.value;
    el.useCase.value = cached.profile?.use_case || el.useCase.value;
    el.scenario.value = cached.scenario || "";
    el.coreContent.value = cached.coreContent || "";
    el.peopleCount.value = cached.peopleCount || defaults.peopleCount;
    el.wordCount.value = cached.wordCount || defaults.wordCount;
    el.dialogueEditor.value = cached.editorContent || "";

    state.text.dialogueId = cached.text?.dialogueId || "";
    state.text.savedContent = cached.text?.savedContent || "";
    state.text.filePath = cached.text?.filePath || "";
    state.text.updatedAt = cached.text?.updatedAt || "";
    state.text.version = Number(cached.text?.version || 0);
    state.audio.filePath = cached.audio?.filePath || "";
    state.audio.updatedAt = cached.audio?.updatedAt || "";
    state.audio.basedOnTextVersion = cached.audio?.basedOnTextVersion ?? null;

    if (!hasPersistedDialogue()) {
      state.text.status = "idle";
      state.audio.status = "idle";
    } else if (hasUnsavedDialogueEdits()) {
      state.text.status = "edited";
      state.audio.status = state.audio.filePath ? "stale" : "idle";
      if (state.audio.filePath && state.audio.basedOnTextVersion == null) {
        state.audio.basedOnTextVersion = Math.max(0, state.text.version - 1);
      }
    } else {
      state.text.status = "ready";
      state.audio.status = state.audio.filePath ? "ready" : "idle";
      if (state.audio.filePath && state.audio.basedOnTextVersion == null) {
        state.audio.basedOnTextVersion = state.text.version;
      }
    }
  } catch (error) {
    console.warn("恢复缓存失败", error);
  }
}

function syncTextStateFromEditor() {
  if (state.text.status === "generating" || state.audio.status === "generating") {
    return;
  }

  if (!hasPersistedDialogue()) {
    state.text.status = hasCurrentDialogueText() ? "edited" : "idle";
    state.audio.status = "idle";
    return;
  }

  if (!hasCurrentDialogueText()) {
    state.text.status = "edited";
    if (state.audio.filePath) {
      state.audio.status = "stale";
    }
    return;
  }

  if (hasUnsavedDialogueEdits()) {
    state.text.status = "edited";
    if (state.audio.filePath) {
      state.audio.status = "stale";
    }
    return;
  }

  state.text.status = "ready";
  if (!state.audio.filePath) {
    state.audio.status = "idle";
  } else if (state.audio.basedOnTextVersion === state.text.version) {
    state.audio.status = "ready";
  } else {
    state.audio.status = "stale";
  }
}

function syncActionButtons() {
  const hasPersistedText = hasPersistedDialogue() && hasCurrentDialogueText();
  const hasValidAudio = state.audio.status === "ready" && !isAudioStale() && Boolean(state.audio.filePath);
  const exceedsAudioLimit = currentDialogueText().length > AUDIO_TEXT_MAX_CHARS;

  el.generateTextBtn.disabled = state.text.status === "generating" || state.audio.status === "generating";
  el.generateAudioBtn.disabled = !hasPersistedText || exceedsAudioLimit || isBusy();
  el.downloadTextBtn.disabled = !hasPersistedText || isBusy();
  el.downloadAudioBtn.disabled = !hasValidAudio || isBusy();
  el.resetBtn.disabled = false;
}

function syncStatusPanels() {
  switch (state.text.status) {
    case "generating":
      el.editStatus.textContent = "文本生成中";
      el.editHint.textContent = "正在生成对话文本，请稍候。";
      break;
    case "ready":
      el.editStatus.textContent = "已生成文本";
      el.editHint.textContent = "已生成文本，可继续编辑、生成音频或下载文本。";
      break;
    case "edited":
      el.editStatus.textContent = "文本已修改";
      el.editHint.textContent = "当前文本已更新，下载文本和生成音频都将以当前内容为准。";
      break;
    case "failed":
      el.editStatus.textContent = "文本生成失败";
      el.editHint.textContent = "文本生成失败，请检查输入后重试。";
      break;
    default:
      el.editStatus.textContent = "未生成文本";
      el.editHint.textContent = "先生成一段对话，再在下方编辑。";
      break;
  }

  switch (state.audio.status) {
    case "generating":
      el.audioStatus.textContent = "音频生成中";
      el.audioHint.textContent = "正在生成音频，请稍候。";
      break;
    case "ready":
      el.audioStatus.textContent = "已生成音频";
      el.audioHint.textContent = "已生成最新音频，可直接下载。";
      break;
    case "stale":
      el.audioStatus.textContent = "音频已失效，请重新生成";
      el.audioHint.textContent = "当前文本已更新，旧音频不再对应最新文本。";
      break;
    case "failed":
      el.audioStatus.textContent = "音频生成失败";
      el.audioHint.textContent = "音频生成失败，请稍后重试。";
      break;
    default:
      el.audioStatus.textContent = "未生成音频";
      el.audioHint.textContent = hasPersistedDialogue()
        ? "文本已生成后可合成并下载音频。"
        : "文本生成完成后可合成并下载音频。";
      break;
  }

  el.textArtifactName.textContent = state.text.filePath ? basenameFromPath(state.text.filePath) : "未生成";
  el.textArtifactMeta.textContent = state.text.filePath
    ? `最近更新：${formatTimestamp(state.text.updatedAt)}`
    : "生成文本后会显示文件名与保存时间。";

  el.audioArtifactName.textContent = state.audio.filePath ? basenameFromPath(state.audio.filePath) : "未生成";
  el.audioArtifactMeta.textContent = state.audio.filePath
    ? `最近更新：${formatTimestamp(state.audio.updatedAt)}`
    : "生成音频后会显示文件名与更新时间。";
}

function refreshUi() {
  syncTextStateFromEditor();
  syncActionButtons();
  syncStatusPanels();
  updateEditorReadonly();
  persistState();
}

function buildGenerateTextPayload() {
  return {
    title: `${el.jobFunction.value}_${el.seniority.value}`,
    profile: {
      job_function: el.jobFunction.value,
      work_content: el.workContent.value,
      seniority: el.seniority.value,
      use_case: el.useCase.value
    },
    scenario: el.scenario.value.trim(),
    core_content: el.coreContent.value.trim(),
    people_count: Number(el.peopleCount.value || defaults.peopleCount),
    word_count: Number(el.wordCount.value || defaults.wordCount)
  };
}

function validateGenerateTextInputs() {
  const payload = buildGenerateTextPayload();
  if (!payload.profile.job_function) return "请选择职业";
  if (!payload.profile.work_content) return "请选择工作内容";
  if (!payload.profile.seniority) return "请选择职级";
  if (!payload.profile.use_case) return "请选择使用场景";
  if (!payload.scenario) return "请填写场景说明";
  if (!payload.core_content) return "请填写对话核心内容";
  if (!Number.isInteger(payload.people_count) || payload.people_count < 2) {
    return "人物数量必须大于等于 2";
  }
  if (!Number.isInteger(payload.word_count) || payload.word_count <= 0) {
    return "字数限制必须为正整数";
  }
  return "";
}

function validateDialogueFormat(dialogueText) {
  const normalized = normalizeText(dialogueText);
  if (!normalized) return "请先生成场景对话文本";
  if (normalized.length > AUDIO_TEXT_MAX_CHARS) {
    return `文本过长，请缩短到 ${AUDIO_TEXT_MAX_CHARS} 个字符以内后再生成音频`;
  }

  const lines = normalized.split("\n");
  const seenSpeakers = new Set();
  let hasSpeakerLine = false;

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line) continue;

    const match = line.match(/^Speaker\s*(\d+)\s*[:：]\s*(.+)$/i);
    if (match) {
      const speakerNumber = Number(match[1]);
      if (!Number.isInteger(speakerNumber) || speakerNumber < 1) {
        return `第 ${i + 1} 行的 Speaker 编号无效`;
      }
      seenSpeakers.add(speakerNumber);
      hasSpeakerLine = true;
      continue;
    }

    if (!hasSpeakerLine) {
      return `第 ${i + 1} 行格式无效，请使用“Speaker N: 内容”`;
    }
  }

  if (!seenSpeakers.size) {
    return "请先生成场景对话文本";
  }

  const maxSpeaker = Math.max(...seenSpeakers);
  for (let speaker = 1; speaker <= maxSpeaker; speaker += 1) {
    if (!seenSpeakers.has(speaker)) {
      return "Speaker 编号必须从 1 开始连续覆盖";
    }
  }

  const expectedPeopleCount = Number(el.peopleCount.value || 0);
  if (expectedPeopleCount && maxSpeaker !== expectedPeopleCount) {
    return "文本中的 Speaker 数量必须与人物数量一致";
  }
  return "";
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

function renderShareBox(payload) {
  const preferred = payload.preferred_share_url || payload.local_urls?.[0] || "";
  state.serverInfo = payload;
  el.sharePrimaryLink.textContent = preferred || "未获取到可分享地址";
  el.sharePrimaryLink.href = preferred || "#";
  el.copyShareBtn.disabled = !preferred;
  el.shareHint.textContent = payload.share_hint || "可把局域网地址发给同一网络中的其他电脑使用。";

  const otherLinks = (payload.local_urls || []).filter((item) => item !== preferred);
  el.serverInfo.innerHTML = otherLinks.length
    ? otherLinks.map((url) => `<a href="${url}" target="_blank" rel="noreferrer">${url}</a>`).join("")
    : `<span>本机地址：${payload.localhost_url || "未提供"}</span>`;
}

async function loadServerInfo() {
  try {
    const payload = await fetchJson("/api/server_info");
    renderShareBox(payload);
  } catch (error) {
    el.sharePrimaryLink.textContent = "获取访问地址失败";
    el.sharePrimaryLink.href = "#";
    el.shareHint.textContent = `获取访问地址失败：${error.message}`;
    el.serverInfo.textContent = "请确认服务已正常启动。";
  }
}

async function copyShareLink() {
  const link = state.serverInfo?.preferred_share_url || "";
  if (!link) return;
  try {
    await navigator.clipboard.writeText(link);
    setMeta("链接已复制");
  } catch (error) {
    setMeta(`复制失败，请手动复制：${link}`, true);
  }
}

function markAudioStale() {
  if (state.audio.filePath) {
    state.audio.status = "stale";
  } else if (state.audio.status !== "generating") {
    state.audio.status = "idle";
  }
}

function applyTextPayload(payload, source) {
  const previousSaved = normalizeText(state.text.savedContent);
  const nextSaved = normalizeText(payload.dialogue_text || payload.text || "");
  const contentChanged = nextSaved !== previousSaved;

  state.text.dialogueId = payload.dialogue_id || state.text.dialogueId;
  state.text.savedContent = nextSaved;
  state.text.filePath = payload.text_path || state.text.filePath;
  state.text.updatedAt = payload.updated_at || payload.saved_at || nowIsoString();

  if (source === "generate" || (contentChanged && source === "save")) {
    state.text.version += 1;
  }

  if (nextSaved) {
    el.dialogueEditor.value = nextSaved;
    state.text.status = "ready";
  } else {
    el.dialogueEditor.value = "";
    state.text.status = "idle";
  }

  if (source === "generate") {
    markAudioStale();
  }
}

function applyAudioPayload(payload) {
  state.audio.filePath = payload.audio_file_path || payload.mp3_path || payload.wav_path || "";
  state.audio.updatedAt = payload.generated_at || payload.updated_at || nowIsoString();
  state.audio.basedOnTextVersion = state.text.version;
  state.audio.status = state.audio.filePath ? "ready" : "failed";
}

async function saveEditedDialogue() {
  if (!hasPersistedDialogue()) return null;
  const dialogueText = currentDialogueText();
  if (!dialogueText) {
    throw new Error("当前对话文本为空，无法保存");
  }

  const payload = await fetchJson("/api/update_dialogue", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dialogue_id: state.text.dialogueId,
      dialogue_text: dialogueText
    })
  });

  applyTextPayload(payload, "save");
  refreshUi();
  return payload;
}

async function generateText() {
  const validationError = validateGenerateTextInputs();
  if (validationError) {
    setMeta(validationError, true);
    return;
  }

  if (hasCurrentDialogueText() && hasPersistedDialogue()) {
    const confirmed = window.confirm("重新生成将覆盖当前生成结果，是否继续？");
    if (!confirmed) return;
  }

  const requestId = ++state.requestIds.text;
  state.text.status = "generating";
  refreshUi();
  startProgress("文本生成中...");
  setMeta("正在生成对话文本...");

  try {
    const payload = await fetchJson("/api/generate_text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildGenerateTextPayload())
    });

    if (requestId !== state.requestIds.text) return;

    applyTextPayload(payload, "generate");
    setMeta(`文本已生成：${basenameFromPath(state.text.filePath) || "最新文本"}`);
    finishProgress("文本生成完成");
  } catch (error) {
    if (requestId !== state.requestIds.text) return;
    state.text.status = "failed";
    setMeta(`文本生成失败：${error.message}`, true);
    finishProgress("文本生成失败");
  } finally {
    if (requestId === state.requestIds.text) {
      refreshUi();
    }
  }
}

async function generateAudio() {
  if (!hasPersistedDialogue()) return;

  const validationError = validateDialogueFormat(currentDialogueText());
  if (validationError) {
    setMeta(validationError, true);
    return;
  }

  const requestId = ++state.requestIds.audio;
  state.audio.status = "generating";
  refreshUi();
  startProgress("音频生成中...");
  setMeta("正在生成 mp3 音频...");

  try {
    await saveEditedDialogue();
    const payload = await fetchJson("/api/generate_audio_custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dialogue_id: state.text.dialogueId,
        dialogue_text: currentDialogueText(),
        format: "mp3"
      })
    });

    if (requestId !== state.requestIds.audio) return;

    applyAudioPayload(payload);
    setMeta(`音频已生成：${basenameFromPath(state.audio.filePath) || "最新音频"}`);
    finishProgress("音频生成完成");
  } catch (error) {
    if (requestId !== state.requestIds.audio) return;
    state.audio.status = "failed";
    setMeta(`音频生成失败：${error.message}`, true);
    finishProgress("音频生成失败");
  } finally {
    if (requestId === state.requestIds.audio) {
      refreshUi();
    }
  }
}

async function downloadText() {
  if (!hasPersistedDialogue() || !hasCurrentDialogueText()) return;
  try {
    startProgress("保存文本后准备下载...");
    await saveEditedDialogue();
    window.location.href = buildDownloadUrl("text");
    setMeta(`正在下载文本：${basenameFromPath(state.text.filePath) || "最新文本"}`);
    finishProgress("文本下载开始");
  } catch (error) {
    setMeta(`文本下载失败：${error.message}`, true);
    finishProgress("文本下载失败");
  }
}

async function downloadAudio() {
  if (el.downloadAudioBtn.disabled) return;
  try {
    if (!state.audio.filePath || state.audio.status !== "ready" || isAudioStale()) {
      throw new Error("当前文本已更新，请重新生成音频");
    }
    window.location.href = buildDownloadUrl("audio");
    setMeta(`正在下载音频：${basenameFromPath(state.audio.filePath) || "最新音频"}`);
  } catch (error) {
    setMeta(`音频下载失败：${error.message}`, true);
  }
}

function resetAll() {
  const confirmed = window.confirm("确定重置当前内容吗？已生成的文本和音频状态将被清空。");
  if (!confirmed) return;

  localStorage.removeItem(STORAGE_KEY);
  state.requestIds.text += 1;
  state.requestIds.audio += 1;

  state.text = {
    dialogueId: "",
    savedContent: "",
    status: "idle",
    filePath: "",
    updatedAt: "",
    version: 0
  };
  state.audio = {
    status: "idle",
    filePath: "",
    updatedAt: "",
    basedOnTextVersion: null
  };

  el.jobFunction.selectedIndex = 0;
  el.workContent.selectedIndex = 0;
  el.seniority.selectedIndex = 0;
  el.useCase.selectedIndex = 0;
  el.scenario.value = "";
  el.coreContent.value = "";
  el.peopleCount.value = defaults.peopleCount;
  el.wordCount.value = defaults.wordCount;
  el.dialogueEditor.value = "";
  resetProgress("等待开始");
  setMeta("已重置");
  refreshUi();
}

function bindEvents() {
  [
    el.jobFunction,
    el.workContent,
    el.seniority,
    el.useCase,
    el.scenario,
    el.coreContent,
    el.peopleCount,
    el.wordCount
  ].forEach((node) => {
    node.addEventListener("input", refreshUi);
    node.addEventListener("change", refreshUi);
  });

  el.dialogueEditor.addEventListener("input", refreshUi);
  el.dialogueEditor.addEventListener("change", refreshUi);

  el.generateTextBtn.addEventListener("click", generateText);
  el.generateAudioBtn.addEventListener("click", generateAudio);
  el.downloadTextBtn.addEventListener("click", downloadText);
  el.downloadAudioBtn.addEventListener("click", downloadAudio);
  el.resetBtn.addEventListener("click", resetAll);
  el.copyShareBtn.addEventListener("click", copyShareLink);
}

function init() {
  initProfileOptions();
  restoreState();
  bindEvents();
  loadServerInfo();
  resetProgress("等待开始");
  refreshUi();
}

init();
