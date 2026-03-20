const STORAGE_KEY = "demo_app_web_state_v2";

const profileOptions = {
  job_function: ["后端开发", "产品经理", "运营管理", "零售行业", "金融服务", "法律服务", "医疗健康", "人工智能/科技", "其他"],
  work_content: ["系统建设", "需求管理", "项目推进", "客户沟通", "数据分析", "风险合规", "市场运营", "其他"],
  seniority: ["初级", "中级", "资深", "经理/主管", "总监/负责人", "其他"],
  use_case: ["会议评审", "客户访谈", "内部会议", "方案决策", "问题排查", "其他"]
};

const state = {
  dialogueId: "",
  originalDialogueText: "",
  textPath: "",
  audioPath: "",
  serverInfo: null,
  progressTimer: null
};

const el = {
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
  dialogueEditor: document.getElementById("dialogueEditor")
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
  el.outputMeta.style.color = isError ? "#c5221f" : "";
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
    textPath: state.textPath,
    audioPath: state.audioPath
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

function syncActionButtons() {
  const hasDialogue = Boolean(state.dialogueId && el.dialogueEditor.value.trim());
  el.generateAudioBtn.disabled = !hasDialogue;
  el.downloadTextBtn.disabled = !hasDialogue;
  el.downloadAudioBtn.disabled = !Boolean(state.dialogueId && state.audioPath);
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
    state.textPath = cached.textPath || "";
    state.audioPath = cached.audioPath || "";
    el.dialogueEditor.value = cached.currentDialogueText || "";
    syncActionButtons();
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

async function loadServerInfo() {
  try {
    const payload = await fetchJson("/api/server_info");
    state.serverInfo = payload;
    el.serverInfo.innerHTML = payload.local_urls
      .map((url) => `<a href="${url}" target="_blank" rel="noreferrer">${url}</a>`)
      .join("");
  } catch (error) {
    el.serverInfo.textContent = `获取访问地址失败: ${error.message}`;
  }
}

async function saveEditedDialogue() {
  if (!state.dialogueId) return null;
  const dialogueText = el.dialogueEditor.value.trim();
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
  state.originalDialogueText = payload.dialogue_text;
  state.textPath = payload.text_path;
  el.dialogueEditor.value = payload.dialogue_text;
  persistState();
  syncActionButtons();
  return payload;
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
    state.dialogueId = payload.dialogue_id;
    state.originalDialogueText = payload.dialogue_text || payload.text || "";
    state.textPath = payload.text_path || "";
    state.audioPath = "";
    el.dialogueEditor.value = state.originalDialogueText;
    syncActionButtons();
    persistState();
    setMeta(`文本已生成：${state.textPath}`);
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
        dialogue_text: el.dialogueEditor.value
      })
    });
    state.audioPath = payload.audio_file_path || payload.mp3_path || payload.wav_path || "";
    syncActionButtons();
    persistState();
    setMeta(`音频已生成：${state.audioPath}`);
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
    window.location.href = `/api/download?dialogue_id=${encodeURIComponent(state.dialogueId)}&kind=text&t=${Date.now()}`;
    finishProgress("文本下载开始");
  } catch (error) {
    setMeta(`文本下载失败：${error.message}`, true);
    finishProgress("文本下载失败");
  }
}

async function downloadAudio() {
  if (!state.dialogueId) return;
  try {
    if (!state.audioPath || el.dialogueEditor.value.trim() !== state.originalDialogueText.trim()) {
      await generateAudio();
    }
    if (!state.audioPath) {
      throw new Error("当前还没有可下载的音频文件");
    }
    window.location.href = `/api/download?dialogue_id=${encodeURIComponent(state.dialogueId)}&kind=audio&t=${Date.now()}`;
  } catch (error) {
    setMeta(`音频下载失败：${error.message}`, true);
  }
}

function resetAll() {
  localStorage.removeItem(STORAGE_KEY);
  state.dialogueId = "";
  state.originalDialogueText = "";
  state.textPath = "";
  state.audioPath = "";
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
  syncActionButtons();
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
    node.addEventListener("input", persistState);
    node.addEventListener("change", persistState);
  });

  el.dialogueEditor.addEventListener("input", syncActionButtons);

  el.generateTextBtn.addEventListener("click", generateText);
  el.generateAudioBtn.addEventListener("click", generateAudio);
  el.downloadTextBtn.addEventListener("click", downloadText);
  el.downloadAudioBtn.addEventListener("click", downloadAudio);
  el.resetBtn.addEventListener("click", resetAll);
}

function init() {
  initProfileOptions();
  restoreState();
  bindEvents();
  loadServerInfo();
  syncActionButtons();
}

init();
