const profileOptions = {
  job_function: [
    "医疗健康",
    "人力资源与招聘",
    "娱乐/媒体",
    "建筑与工程行业",
    "汽车行业",
    "咨询/专业服务",
    "法律服务",
    "金融/投资",
    "零售行业",
    "保险行业",
    "房地产",
    "人工智能/科技",
    "制造业",
    "其他"
  ],
  work_content: [
    "医疗服务供应商",
    "战略/运营/数据",
    "法务/合规",
    "人力资源与招聘",
    "IT/系统管理",
    "教师/教授/学术研究",
    "销售/合作伙伴关系",
    "学生/学徒",
    "工程",
    "市场与创意",
    "高管（C层）/创始人",
    "咨询与顾问服务",
    "技工/技术工种",
    "房地产",
    "财务与会记",
    "其他"
  ],
  seniority: [
    "高级职员",
    "高管/C级/合伙人",
    "经理/主管",
    "初级职员",
    "副总裁/总监/部门负责人",
    "其他"
  ],
  use_case: [
    "会议/峰会",
    "客户洽谈",
    "口述想法/灵感记录",
    "内部会议",
    "个人使用",
    "其他"
  ]
};

const state = {
  dialogueId: null,
  progressTimer: null
};

const STORAGE_KEY = "dialogue_demo_cache";

const elements = {
  jobFunction: document.getElementById("jobFunction"),
  workContent: document.getElementById("workContent"),
  seniority: document.getElementById("seniority"),
  useCase: document.getElementById("useCase"),
  jobFunctionOther: document.getElementById("jobFunctionOther"),
  workContentOther: document.getElementById("workContentOther"),
  seniorityOther: document.getElementById("seniorityOther"),
  useCaseOther: document.getElementById("useCaseOther"),
  scenario: document.getElementById("scenario"),
  coreContent: document.getElementById("coreContent"),
  peopleCount: document.getElementById("peopleCount"),
  wordCount: document.getElementById("wordCount"),
  generateTextBtn: document.getElementById("generateTextBtn"),
  generateAudioBtn: document.getElementById("generateAudioBtn"),
  outputText: document.getElementById("outputText"),
  outputMeta: document.getElementById("outputMeta"),
  progressFill: document.getElementById("progressFill"),
  progressText: document.getElementById("progressText")
};

function fillSelect(selectEl, options) {
  selectEl.innerHTML = "";
  options.forEach((option) => {
    const opt = document.createElement("option");
    opt.value = option;
    opt.textContent = option;
    selectEl.appendChild(opt);
  });
}

function toggleOtherInput(selectEl, inputEl) {
  if (selectEl.value === "其他") {
    inputEl.style.display = "block";
  } else {
    inputEl.style.display = "none";
    inputEl.value = "";
  }
}

function initOptions() {
  fillSelect(elements.jobFunction, profileOptions.job_function);
  fillSelect(elements.workContent, profileOptions.work_content);
  fillSelect(elements.seniority, profileOptions.seniority);
  fillSelect(elements.useCase, profileOptions.use_case);

  for (let i = 2; i <= 10; i += 1) {
    const opt = document.createElement("option");
    opt.value = i;
    opt.textContent = String(i);
    elements.peopleCount.appendChild(opt);
  }

  elements.jobFunction.addEventListener("change", () => {
    toggleOtherInput(elements.jobFunction, elements.jobFunctionOther);
    saveToCache();
  });
  elements.workContent.addEventListener("change", () => {
    toggleOtherInput(elements.workContent, elements.workContentOther);
    saveToCache();
  });
  elements.seniority.addEventListener("change", () => {
    toggleOtherInput(elements.seniority, elements.seniorityOther);
    saveToCache();
  });
  elements.useCase.addEventListener("change", () => {
    toggleOtherInput(elements.useCase, elements.useCaseOther);
    saveToCache();
  });
  
  // 为所有输入框添加自动保存
  elements.jobFunctionOther.addEventListener("input", saveToCache);
  elements.workContentOther.addEventListener("input", saveToCache);
  elements.seniorityOther.addEventListener("input", saveToCache);
  elements.useCaseOther.addEventListener("input", saveToCache);
  elements.scenario.addEventListener("input", saveToCache);
  elements.coreContent.addEventListener("input", saveToCache);
  elements.peopleCount.addEventListener("change", saveToCache);
  elements.wordCount.addEventListener("input", saveToCache);

  toggleOtherInput(elements.jobFunction, elements.jobFunctionOther);
  toggleOtherInput(elements.workContent, elements.workContentOther);
  toggleOtherInput(elements.seniority, elements.seniorityOther);
  toggleOtherInput(elements.useCase, elements.useCaseOther);
}

function startProgress(message) {
  clearInterval(state.progressTimer);
  let progress = 0;
  elements.progressFill.style.width = "0%";
  elements.progressText.textContent = message;

  state.progressTimer = setInterval(() => {
    progress = Math.min(progress + Math.random() * 12, 95);
    elements.progressFill.style.width = `${progress}%`;
  }, 300);
}

function finishProgress(message) {
  clearInterval(state.progressTimer);
  elements.progressFill.style.width = "100%";
  elements.progressText.textContent = message;
  setTimeout(() => {
    elements.progressFill.style.width = "0%";
  }, 1500);
}

function getProfileValue(selectEl, otherInput) {
  if (selectEl.value === "其他" && otherInput.value.trim()) {
    return otherInput.value.trim();
  }
  return selectEl.value;
}

function saveToCache() {
  const cacheData = {
    profile: {
      job_function: getProfileValue(elements.jobFunction, elements.jobFunctionOther),
      work_content: getProfileValue(elements.workContent, elements.workContentOther),
      seniority: getProfileValue(elements.seniority, elements.seniorityOther),
      use_case: getProfileValue(elements.useCase, elements.useCaseOther),
      job_function_other: elements.jobFunctionOther.value,
      work_content_other: elements.workContentOther.value,
      seniority_other: elements.seniorityOther.value,
      use_case_other: elements.useCaseOther.value
    },
    scenario: elements.scenario.value,
    coreContent: elements.coreContent.value,
    peopleCount: elements.peopleCount.value,
    wordCount: elements.wordCount.value,
    dialogueId: state.dialogueId,
    lastGeneratedLines: state.lastGeneratedLines || null
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(cacheData));
  } catch (e) {
    console.warn("保存缓存失败:", e);
  }
}

function loadFromCache() {
  try {
    const cached = localStorage.getItem(STORAGE_KEY);
    if (!cached) return false;
    
    const data = JSON.parse(cached);
    
    // 恢复人物画像
    if (data.profile) {
      if (data.profile.job_function) {
        elements.jobFunction.value = data.profile.job_function;
        if (data.profile.job_function === "其他" && data.profile.job_function_other) {
          elements.jobFunctionOther.value = data.profile.job_function_other;
          elements.jobFunctionOther.style.display = "block";
        }
      }
      if (data.profile.work_content) {
        elements.workContent.value = data.profile.work_content;
        if (data.profile.work_content === "其他" && data.profile.work_content_other) {
          elements.workContentOther.value = data.profile.work_content_other;
          elements.workContentOther.style.display = "block";
        }
      }
      if (data.profile.seniority) {
        elements.seniority.value = data.profile.seniority;
        if (data.profile.seniority === "其他" && data.profile.seniority_other) {
          elements.seniorityOther.value = data.profile.seniority_other;
          elements.seniorityOther.style.display = "block";
        }
      }
      if (data.profile.use_case) {
        elements.useCase.value = data.profile.use_case;
        if (data.profile.use_case === "其他" && data.profile.use_case_other) {
          elements.useCaseOther.value = data.profile.use_case_other;
          elements.useCaseOther.style.display = "block";
        }
      }
    }
    
    // 恢复场景设置
    if (data.scenario) {
      elements.scenario.value = data.scenario;
    }
    if (data.coreContent) {
      elements.coreContent.value = data.coreContent;
    }
    if (data.peopleCount) {
      elements.peopleCount.value = data.peopleCount;
    }
    if (data.wordCount) {
      elements.wordCount.value = data.wordCount;
    }
    
    // 恢复对话结果
    if (data.dialogueId) {
      state.dialogueId = data.dialogueId;
    }
    if (data.lastGeneratedLines && data.lastGeneratedLines.length > 0) {
      state.lastGeneratedLines = data.lastGeneratedLines;
      renderDialogue(data.lastGeneratedLines);
      elements.generateAudioBtn.disabled = false;
      elements.outputMeta.textContent = "已恢复上次生成的对话内容";
    }
    
    return true;
  } catch (e) {
    console.warn("加载缓存失败:", e);
    return false;
  }
}

function renderDialogue(lines) {
  if (!lines || lines.length === 0) {
    elements.outputText.textContent = "暂无对话内容";
    return;
  }
  const html = lines
    .map((line) => {
      let text = line.text;
      text = text.replace(/<<核心:(.*?)>>/g, '<span class="core-text">$1</span>');
      if (line.is_owner) {
        return `<strong>${line.speaker}：</strong> <strong>${text}</strong>`;
      }
      return `${line.speaker}：${text}`;
    })
    .join("<br/>");
  elements.outputText.innerHTML = html;
}

async function generateText() {
  const profile = {
    job_function: getProfileValue(elements.jobFunction, elements.jobFunctionOther),
    work_content: getProfileValue(elements.workContent, elements.workContentOther),
    seniority: getProfileValue(elements.seniority, elements.seniorityOther),
    use_case: getProfileValue(elements.useCase, elements.useCaseOther)
  };

  const payload = {
    title: `${profile.job_function}_${profile.seniority}`,
    profile,
    scenario: elements.scenario.value.trim(),
    core_content: elements.coreContent.value.trim(),
    people_count: Number(elements.peopleCount.value || 2),
    word_count: Number(elements.wordCount.value || 500)
  };

  startProgress("文本生成中...");
  elements.generateTextBtn.disabled = true;
  elements.generateAudioBtn.disabled = true;

  try {
    const response = await fetch("/api/generate_text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    
    // 检查响应类型
    const contentType = response.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
      const text = await response.text();
      throw new Error(`服务器返回了非 JSON 格式: ${text.substring(0, 200)}`);
    }
    
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "生成失败");
    }
    state.dialogueId = data.dialogue_id;
    state.lastGeneratedLines = data.lines;
    renderDialogue(data.lines);
    elements.outputMeta.textContent = `文本已保存：${data.text_path}`;
    elements.generateAudioBtn.disabled = false;
    finishProgress("文本生成完成");
    saveToCache(); // 保存到缓存
  } catch (err) {
    elements.outputMeta.textContent = `生成失败：${err.message}`;
    finishProgress("文本生成失败");
  } finally {
    elements.generateTextBtn.disabled = false;
  }
}

async function generateAudio() {
  if (!state.dialogueId) return;
  startProgress("音频生成中...");
  elements.generateAudioBtn.disabled = true;
  try {
    const response = await fetch("/api/generate_audio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dialogue_id: state.dialogueId })
    });
    
    // 检查响应类型
    const contentType = response.headers.get("content-type");
    if (!contentType || !contentType.includes("application/json")) {
      const text = await response.text();
      throw new Error(`服务器返回了非 JSON 格式: ${text.substring(0, 200)}`);
    }
    
    const data = await response.json();
    if (!response.ok) {
      // 即使失败，也可能生成了 WAV 文件
      let errorMsg = data.error || "音频生成失败";
      if (data.wav_path) {
        const format = data.format || "wav";
        const note = data.note || "";
        errorMsg += `\n已生成${format.toUpperCase()}文件：${data.wav_path}`;
        if (note) {
          errorMsg += `（${note}）`;
        }
      } else if (data.note) {
        errorMsg += `\n${data.note}`;
      }
      throw new Error(errorMsg);
    }
    
    // 成功生成，显示 format 和 note 信息
    const format = data.format || (data.mp3_path ? "mp3" : data.wav_path ? "wav" : "unknown");
    const audioPath = data.mp3_path || data.wav_path;
    const note = data.note || "";
    
    if (audioPath) {
      // 格式化显示：✅ "生成完成：xxx.wav（note信息）"
      let message = `✅ 生成完成：${audioPath}`;
      if (note) {
        message += `（${note}）`;
      }
      elements.outputMeta.textContent = message;
      finishProgress("音频生成完成");
    } else {
      elements.outputMeta.textContent = "音频生成完成";
      finishProgress("音频生成完成");
    }
  } catch (err) {
    elements.outputMeta.textContent = `音频生成失败：${err.message}`;
    finishProgress("音频生成失败");
  } finally {
    elements.generateAudioBtn.disabled = false;
  }
}

elements.generateTextBtn.addEventListener("click", generateText);
elements.generateAudioBtn.addEventListener("click", generateAudio);

// 初始化
initOptions();

// 加载缓存数据
if (loadFromCache()) {
  console.log("已恢复上次使用的数据");
}
