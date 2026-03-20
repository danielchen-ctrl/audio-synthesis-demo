const STORAGE_KEY = "demo_app_web_state_v3";

const profileOptions = {
  job_function: ["后端开发", "产品经理", "运营管理", "零售行业", "金融服务", "法律服务", "医疗健康", "人工智能/科技", "其他"],
  work_content: ["系统建设", "需求管理", "项目推进", "客户沟通", "数据分析", "风险合规", "市场运营", "其他"],
  seniority: ["初级", "中级", "资深", "经理/主管", "总监/负责人", "其他"],
  use_case: ["会议评审", "客户访谈", "内部会议", "方案决策", "问题排查", "其他"]
};

const state = {
  dialogueId: "",
  originalDialogueText: "",
  audioSourceText: "",
  textPath: "",
  audioPath: "",
  textSavedAt: "",
  audioSavedAt: "",
  serverInfo: null,
  progressTimer: null
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
    if (i === 3) option.selected = true;
    el.peopleCount.appendChild(option);
  }
}

function normalizeText(value) {
  return String(value || "").replace(/\r\n/g, "\n").trim();
}

function currentDialogueText() {
  return normalizeText(el.dialogueEditor.value);
}

function hasUnsavedDialogueEdits() {
  return Boolean(state.dialogueId) && currentDialogueText() !== normalizeText(state.originalDialogueText);
}

function isAudioOutdated() {
  if (!state.dialogueId) return false;
  if (!state.audioPath) return false;
  return currentDialogueText() !== normalizeText(state.audioSourceText);
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

function buildDownloadUrl(kind) {
  if (!state.dialogueId) return "";
  return `/api/download?dialogue_id=${encodeURIComponent(state.dialogueId)}&kind=${kind}&t=${Date.now()}`;
}

function startProgress(message) {
  clearInterval(state.progressTimer);
  let progress = 0;
  el.progressFill.style.width = "0%";
  el.progressText.textContent = message;
  state.progressTimer = window.setInterval(() => {
    progress = Math.min(progress + Math.random() * 14, 92);
    el.progressFill.style.width = `${progress}%`;
  }, 280);
}

function finishProgress(message) {
  clearInterval(state.progressTimer);
  el.progressFill.style.width = "100%";
  el.progressText.textContent = message;
  window.setTimeout(() => {
    el.progressFill.style.width = "0%";
  }, 1200);
}

function setMeta(message, isError = false) {
  el.outputMeta.classList.toggle("is-error", Boolean(isError));
  el.outputMeta.textContent = message;
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
    dialogueId: state.dialogueId,
    originalDialogueText: state.originalDialogueText,
    currentDialogueText: el.dialogueEditor.value,
    audioSourceText: state.audioSourceText,
    textPath: state.textPath,
    audioPath: state.audioPath,
    textSavedAt: state.textSavedAt,
    audioSavedAt: state.audioSavedAt
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function syncActionButtons() {
  const hasDialogue = Boolean(state.dialogueId && currentDialogueText());
  el.generateAudioBtn.disabled = !hasDialogue;
  el.downloadTextBtn.disabled = !hasDialogue;
  el.downloadAudioBtn.disabled = !hasDialogue;
}

function syncStatusPanels() {
  if (!state.dialogueId) {
    el.editStatus.textContent = "未生成文本";
    el.editHint.textContent = "先生成一段对话，再在下方编辑。";
    el.audioStatus.textContent = "未生成音频";
    el.audioHint.textContent = "文本生成后即可合成或下载音频。";
  } else if (hasUnsavedDialogueEdits()) {
    el.editStatus.textContent = "文本已修改，尚未保存";
    el.editHint.textContent = "点击“下载文本”会先保存；点击“生成 mp3 音频”会先保存并基于当前内容合成。";
    el.audioStatus.textContent = state.audioPath ? "音频不是最新版本" : "还没有音频文件";
    el.audioHint.textContent = "当前文本与已保存/已合成版本不一致，继续下载音频会自动重新生成。";
  } else {
    el.editStatus.textContent = state.textPath ? "文本已保存，可直接分享或下载" : "文本已生成";
    el.editHint.textContent = state.textPath
      ? `当前文本文件：${basenameFromPath(state.textPath)}`
      : "可继续修改文本，再重新合成音频。";
    if (!state.audioPath) {
      el.audioStatus.textContent = "还没有音频文件";
      el.audioHint.textContent = "点击“生成 mp3 音频”或“下载音频”即可生成。";
    } else if (isAudioOutdated()) {
      el.audioStatus.textContent = "音频不是最新版本";
      el.audioHint.textContent = "文本最近已更新，下载音频时会自动重新生成。";
    } else {
      el.audioStatus.textContent = "音频已同步，可直接下载";
      el.audioHint.textContent = `当前音频文件：${basenameFromPath(state.audioPath)}`;
    }
  }

  el.textArtifactName.textContent = state.textPath ? basenameFromPath(state.textPath) : "未生成";
  el.textArtifactMeta.textContent = state.textPath
    ? `最近保存：${formatTimestamp(state.textSavedAt)}`
    : "生成文本后会显示文件名与保存时间。";

  el.audioArtifactName.textContent = state.audioPath ? basenameFromPath(state.audioPath) : "未生成";
  el.audioArtifactMeta.textContent = state.audioPath
    ? `最近更新：${formatTimestamp(state.audioSavedAt)}`
    : "生成音频后会显示文件名与更新时间。";
}

function refreshUi() {
  syncActionButtons();
  syncStatusPanels();
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
    el.peopleCount.value = cached.peopleCount || "3";
    el.wordCount.value = cached.wordCount || "1000";
    state.dialogueId = cached.dialogueId || "";
    state.originalDialogueText = cached.originalDialogueText || "";
    state.audioSourceText = cached.audioSourceText || "";
    state.textPath = cached.textPath || "";
    state.audioPath = cached.audioPath || "";
    state.textSavedAt = cached.textSavedAt || "";
    state.audioSavedAt = cached.audioSavedAt || "";
    el.dialogueEditor.value = cached.currentDialogueText || "";
    refreshUi();
  } catch (error) {
    console.warn("恢复缓存失败", error);
  }
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
    people_count: Number(el.peopleCount.value || 3),
    word_count: Number(el.wordCount.value || 1000)
  };
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : { ok: false, error: await response.text() };
  if (!response.ok || payload.ok === false) {
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
    setMeta(`已复制分享链接：${link}`);
  } catch (error) {
    setMeta(`复制失败，请手动复制：${link}`, true);
  }
}

function applyTextPayload(payload, source = "generate") {
  state.dialogueId = payload.dialogue_id || state.dialogueId;
  state.originalDialogueText = payload.dialogue_text || payload.text || "";
  state.textPath = payload.text_path || state.textPath;
  state.textSavedAt = payload.saved_at || new Date().toISOString();
  if (source === "generate") {
    state.audioPath = "";
    state.audioSavedAt = "";
    state.audioSourceText = "";
  }
  el.dialogueEditor.value = state.originalDialogueText;
  persistState();
  refreshUi();
}

async function saveEditedDialogue() {
  if (!state.dialogueId) return null;
  const dialogueText = currentDialogueText();
  if (!dialogueText) {
    throw new Error("当前对话文本为空，无法保存");
  }
  const payload = await fetchJson("/api/update_dialogue", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dialogue_id: state.dialogueId,
      dialogue_text: dialogueText
    })
  });
  applyTextPayload(payload, "save");
  return payload;
}

function applyAudioPayload(payload) {
  state.audioPath = payload.audio_file_path || payload.mp3_path || payload.wav_path || "";
  state.audioSavedAt = payload.generated_at || new Date().toISOString();
  state.audioSourceText = currentDialogueText();
  persistState();
  refreshUi();
}

async function generateText() {
  startProgress("文本生成中...");
  el.generateTextBtn.disabled = true;
  try {
    const payload = await fetchJson("/api/generate_text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildGenerateTextPayload())
    });
    applyTextPayload(payload, "generate");
    setMeta(`文本已生成：${basenameFromPath(state.textPath) || state.textPath}`);
    finishProgress("文本生成完成");
  } catch (error) {
    setMeta(`文本生成失败：${error.message}`, true);
    finishProgress("文本生成失败");
  } finally {
    el.generateTextBtn.disabled = false;
  }
}

async function generateAudio() {
  if (!state.dialogueId) return;
  startProgress("音频生成中...");
  el.generateAudioBtn.disabled = true;
  try {
    await saveEditedDialogue();
    const payload = await fetchJson("/api/generate_audio_custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dialogue_id: state.dialogueId,
        dialogue_text: currentDialogueText()
      })
    });
    applyAudioPayload(payload);
    setMeta(`音频已生成：${basenameFromPath(state.audioPath) || state.audioPath}`);
    finishProgress("音频生成完成");
  } catch (error) {
    setMeta(`音频生成失败：${error.message}`, true);
    finishProgress("音频生成失败");
  } finally {
    el.generateAudioBtn.disabled = false;
  }
}

async function downloadText() {
  if (!state.dialogueId) return;
  try {
    startProgress("保存文本后准备下载...");
    await saveEditedDialogue();
    window.location.href = buildDownloadUrl("text");
    setMeta(`正在下载文本：${basenameFromPath(state.textPath) || "最新文本"}`);
    finishProgress("文本下载开始");
  } catch (error) {
    setMeta(`文本下载失败：${error.message}`, true);
    finishProgress("文本下载失败");
  }
}

async function downloadAudio() {
  if (!state.dialogueId) return;
  try {
    if (!state.audioPath || isAudioOutdated()) {
      await generateAudio();
    }
    if (!state.audioPath) {
      throw new Error("当前还没有可下载的音频文件");
    }
    window.location.href = buildDownloadUrl("audio");
    setMeta(`正在下载音频：${basenameFromPath(state.audioPath) || "最新音频"}`);
  } catch (error) {
    setMeta(`音频下载失败：${error.message}`, true);
  }
}

function resetAll() {
  localStorage.removeItem(STORAGE_KEY);
  state.dialogueId = "";
  state.originalDialogueText = "";
  state.audioSourceText = "";
  state.textPath = "";
  state.audioPath = "";
  state.textSavedAt = "";
  state.audioSavedAt = "";
  el.jobFunction.selectedIndex = 0;
  el.workContent.selectedIndex = 0;
  el.seniority.selectedIndex = 0;
  el.useCase.selectedIndex = 0;
  el.scenario.value = "";
  el.coreContent.value = "";
  el.wordCount.value = "1000";
  el.peopleCount.value = "3";
  el.dialogueEditor.value = "";
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
    el.wordCount,
    el.dialogueEditor
  ].forEach((node) => {
    node.addEventListener("input", () => {
      persistState();
      refreshUi();
    });
    node.addEventListener("change", () => {
      persistState();
      refreshUi();
    });
  });

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
  refreshUi();
}

init();
