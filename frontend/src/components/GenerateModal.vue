<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useMessage } from 'naive-ui'
import { listLanguages, listTemplates, listVoices, type Voice } from '@/api/meta'
import { listFolders, type FolderNode } from '@/api/folders'
import {
  createTask, previewDialogue,
  type TaskCreatePayload, type VoiceAssignment,
} from '@/api/tasks'
import { errorMessage } from '@/api/client'
import VoiceManageModal from '@/components/VoiceManageModal.vue'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
  (e: 'generated'): void
}>()

const message = useMessage()
const submitting = ref(false)
const previewing = ref(false)
const showVoiceMgmt = ref(false)

// 配置
const generationMode = ref<'llm' | 'manual'>('llm')
const topic = ref('')
const template = ref('1')  // 默认选第一个预设；自定义 code = "custom"
const customPrompt = ref('')
const language = ref('zh')
const speakerCount = ref(2)
const targetDuration = ref(60)
const keywords = ref<string[]>([])
const kwInput = ref('')
const audioFormat = ref<'mp3' | 'wav' | 'm4a'>('mp3')
const folderId = ref<string>('')
const tagInput = ref('')
const generateScripts = ref(false)

const folders = ref<FolderNode[]>([])
function flattenFolders(nodes: FolderNode[], prefix = ''): Array<{ id: string; label: string }> {
  const out: Array<{ id: string; label: string }> = []
  for (const n of nodes) {
    const label = prefix ? `${prefix} / ${n.name}` : n.name
    out.push({ id: n.folder_id, label })
    if (n.children?.length) out.push(...flattenFolders(n.children, label))
  }
  return out
}
const folderOptions = computed(() => [
  { id: '', label: '默认目录（根）' },
  ...flattenFolders(folders.value),
])

// 当前选中的模板对象（含描述/角色/默认值等元数据）
const selectedTemplate = computed(() =>
  templates.value.find((t) => t.code === template.value),
)
const isCustomTemplate = computed(() => template.value === 'custom')

// 选模板时，把模板默认值自动填入字段（用户可继续修改）
watch(template, (newCode) => {
  const t = templates.value.find((x) => x.code === newCode)
  if (!t || newCode === 'custom') return
  if (t.example_topic && !topic.value) topic.value = t.example_topic
  if (t.default_speaker_count) speakerCount.value = t.default_speaker_count
  // 不强行覆盖用户已填的关键词
})

// 文本预览 / 编辑
const previewText = ref('')        // LLM 预览结果（可编辑）
const manualText = ref('')          // 手动模式输入

// 当前真正会发给 TTS 的文本（LLM 模式时来自 previewText，否则 manualText）
const finalDialogueText = computed(() =>
  generationMode.value === 'llm' ? previewText.value : manualText.value
)

const voiceAssignments = ref<Record<string, VoiceAssignment>>({})
const languages = ref<Array<{ code: string; name: string }>>([])
const templates = ref<Array<{ code: string; name: string; description: string }>>([])
const voices = ref<Voice[]>([])

async function loadMeta() {
  try {
    languages.value = await listLanguages()
    templates.value = await listTemplates()
    folders.value = await listFolders()
    await refreshVoices()
  } catch (e) { message.error(errorMessage(e)) }
}

async function refreshVoices() {
  voices.value = await listVoices(language.value)
  const newAssignments: Record<string, VoiceAssignment> = {}
  for (let i = 1; i <= speakerCount.value; i++) {
    const voice = voices.value[(i - 1) % voices.value.length]
    if (voice) newAssignments[String(i)] = { voice_id: voice.voice_id, voice_name: voice.name }
  }
  voiceAssignments.value = newAssignments
}

watch(() => language.value, refreshVoices)
watch(() => speakerCount.value, refreshVoices)
watch(() => props.show, (v) => { if (v) loadMeta() })

const voiceOptions = computed(() =>
  voices.value.map((v) => ({ label: `${v.name}${v.gender ? ` (${v.gender})` : ''}`, value: v.voice_id })),
)

function setVoice(speakerId: string, voiceId: string) {
  const v = voices.value.find((x) => x.voice_id === voiceId)
  if (v) voiceAssignments.value[speakerId] = { voice_id: v.voice_id, voice_name: v.name }
}

function addKeyword() {
  const k = kwInput.value.trim()
  if (k && !keywords.value.includes(k)) keywords.value.push(k)
  kwInput.value = ''
}
function removeKeyword(i: number) { keywords.value.splice(i, 1) }

const speakerColors = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16']

/** PRD §8：根据当前配置生成对话文本并填入预览区 */
async function doPreview() {
  if (!topic.value.trim()) { message.warning('请填写文本主题'); return }
  if (template.value === 'custom' && !customPrompt.value.trim()) {
    message.warning('自定义模板需填写 Prompt'); return
  }
  previewing.value = true
  try {
    const resp = await previewDialogue({
      topic: topic.value.trim(),
      template: template.value,
      custom_prompt: template.value === 'custom' ? customPrompt.value.trim() : undefined,
      language: language.value,
      speaker_count: speakerCount.value,
      target_duration_sec: targetDuration.value,
      keywords: keywords.value,
    })
    previewText.value = resp.dialogue_text
    message.success(`已生成 ${resp.line_count} 行对话（${resp.model}）`)
  } catch (e) {
    message.error(errorMessage(e))
  } finally {
    previewing.value = false
  }
}

async function submit() {
  if (!topic.value.trim()) { message.warning('请填写文本主题'); return }

  const dialogueText = finalDialogueText.value.trim()
  if (!dialogueText) {
    message.warning(generationMode.value === 'llm'
      ? '请先点【根据以上配置生成文本】生成对话，或切到手动模式'
      : '请填写对话文本')
    return
  }
  if (Object.keys(voiceAssignments.value).length !== speakerCount.value) {
    message.warning('请为每个 speaker 选择音色'); return
  }

  // 不论何种 mode，到提交合成这一步统一走 manual（文本已经定型）
  const tagList = tagInput.value.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
  const payload: TaskCreatePayload = {
    generation_mode: 'manual',
    topic: topic.value.trim(),
    language: language.value,
    speaker_count: speakerCount.value,
    voice_assignments: voiceAssignments.value,
    audio_format: audioFormat.value,
    dialogue_text: dialogueText,
    folder_id: folderId.value || null,
    tag_names: tagList,
    generate_scripts: generateScripts.value,
  }

  submitting.value = true
  try {
    await createTask(payload)
    emit('generated')
    resetForm()
  } catch (e) { message.error(errorMessage(e)) }
  finally { submitting.value = false }
}

function resetForm() {
  topic.value = ''
  customPrompt.value = ''
  keywords.value = []
  previewText.value = ''
  manualText.value = ''
  tagInput.value = ''
  folderId.value = ''
  generateScripts.value = false
}
function close() { emit('update:show', false) }

// 切换模式时清空预览/输入
watch(generationMode, () => {
  previewText.value = ''
  manualText.value = ''
})
</script>

<template>
  <div class="mo" :class="{ open: show }" @click.self="close">
    <div class="modal">
      <div class="mh">
        <div class="mt">在线生成音频</div>
        <button class="mc" @click="close">✕</button>
      </div>

      <div class="mb">
        <!-- 生成方式 -->
        <div class="ms-sec">
          <div class="ms-sec-title">生成方式</div>
          <div class="radio-group">
            <label class="ro" :class="{ sel: generationMode === 'llm' }">
              <input type="radio" value="llm" v-model="generationMode" />
              <div>
                <div class="ro-label">LLM 生成文本并合成音频</div>
                <div class="ro-desc">AI 自动生成对话文本</div>
              </div>
            </label>
            <label class="ro" :class="{ sel: generationMode === 'manual' }">
              <input type="radio" value="manual" v-model="generationMode" />
              <div>
                <div class="ro-label">直接输入文本生成音频</div>
                <div class="ro-desc">自己编写对话文本</div>
              </div>
            </label>
          </div>
        </div>

        <!-- ============ LLM 模式 ============ -->
        <template v-if="generationMode === 'llm'">
          <div class="ms-sec">
            <div class="ms-sec-title">内容配置</div>

            <div class="form-group">
              <label class="form-label">文本主题<span class="req">*</span></label>
              <input v-model="topic" class="input-field" placeholder="如：季度复盘会议讨论" />
            </div>

            <div class="g2">
              <div class="form-group">
                <label class="form-label">主题模板<span class="req">*</span></label>
                <select v-model="template" class="select-field">
                  <option v-for="t in templates" :key="t.code" :value="t.code">{{ t.name }}</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">文本语言<span class="req">*</span></label>
                <select v-model="language" class="select-field">
                  <option v-for="l in languages" :key="l.code" :value="l.code">{{ l.name }}</option>
                </select>
              </div>
            </div>

            <!-- 选中预设模板时展示场景说明 -->
            <div v-if="selectedTemplate && !isCustomTemplate" class="template-hint">
              <div class="template-hint-title">📋 场景背景</div>
              <div class="template-hint-desc">{{ selectedTemplate.description }}</div>
              <div v-if="selectedTemplate.roles && selectedTemplate.roles.length"
                   class="template-hint-meta">
                <strong>候选角色：</strong>
                <span v-for="(r, i) in selectedTemplate.roles" :key="i" class="tag" style="margin-right:4px">{{ r }}</span>
              </div>
              <div v-if="selectedTemplate.core_keywords && selectedTemplate.core_keywords.length"
                   class="template-hint-meta">
                <strong>核心关键词（自动注入）：</strong>
                <span v-for="(k, i) in selectedTemplate.core_keywords" :key="i" class="tag" style="margin-right:4px">{{ k }}</span>
              </div>
            </div>

            <!-- 自定义 Prompt 输入 -->
            <div v-if="isCustomTemplate" class="form-group">
              <label class="form-label">自定义 Prompt<span class="req">*</span></label>
              <textarea v-model="customPrompt" class="textarea-field" style="min-height:100px"
                        placeholder="描述您想生成什么样的对话，例如：&#10;生成一个两人技术讨论，讨论软件发布流程，语气自然，包含敏捷开发、CI/CD 等术语..."></textarea>
              <div class="form-hint">
                内置模板不能覆盖您的场景？这里完全自由描述，LLM 会按您的 Prompt 生成
              </div>
            </div>

            <div class="g2">
              <div class="form-group">
                <label class="form-label">目标对话时长<span class="req">*</span></label>
                <input v-model.number="targetDuration" class="input-field" type="number"
                       :min="10" :max="43200" />
                <div class="form-hint">单位秒，范围 10–43200（12 小时）</div>
              </div>
              <div class="form-group">
                <label class="form-label">关键词</label>
                <div class="tag-input-wrap">
                  <span v-for="(k, i) in keywords" :key="i" class="ti-tag">
                    {{ k }} <span class="rm" @click="removeKeyword(i)">×</span>
                  </span>
                  <input v-model="kwInput" placeholder="输入关键词，回车添加" @keyup.enter="addKeyword" />
                </div>
                <div class="form-hint">多个关键词用回车分隔</div>
              </div>
            </div>
          </div>

          <!-- 说话人数 -->
          <div class="ms-sec">
            <div class="ms-sec-title">说话人数</div>
            <div class="form-group">
              <label class="form-label">说话人数<span class="req">*</span></label>
              <input v-model.number="speakerCount" class="input-field" type="number"
                     :min="1" :max="10" style="width:120px" />
              <div class="form-hint">范围 1–10，须与文本中 Speaker 数量一致</div>
            </div>

            <!-- 渐变品牌按钮：生成文本 -->
            <button class="btn-gen" :disabled="previewing" @click="doPreview">
              <span v-if="previewing">⏳ 生成中…</span>
              <span v-else-if="previewText">✨ 重新生成文本</span>
              <span v-else>✨ 根据以上配置生成文本</span>
            </button>
          </div>

          <!-- 文本预览与编辑：仅在有预览结果时显示 -->
          <div v-if="previewText" class="ms-sec">
            <div class="ms-sec-title flex">
              <span style="flex:1">文本预览与编辑</span>
              <button class="btn btn-secondary btn-sm" :disabled="previewing" @click="doPreview">
                🔄 重新生成
              </button>
            </div>
            <textarea v-model="previewText" class="textarea-field font-mono"
                      style="min-height:180px"></textarea>
            <div class="form-hint">
              生成的对话已填入上方文本框，可直接编辑。提交时使用编辑后的文本。
            </div>
          </div>
        </template>

        <!-- ============ Manual 模式 ============ -->
        <template v-else>
          <div class="ms-sec">
            <div class="ms-sec-title">基本信息</div>
            <div class="form-group">
              <label class="form-label">文本主题<span class="req">*</span></label>
              <input v-model="topic" class="input-field" placeholder="用于文件命名和检索" />
            </div>
            <div class="form-group">
              <label class="form-label">文本语言<span class="req">*</span></label>
              <select v-model="language" class="select-field">
                <option v-for="l in languages" :key="l.code" :value="l.code">{{ l.name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">说话人数<span class="req">*</span></label>
              <input v-model.number="speakerCount" class="input-field" type="number"
                     :min="1" :max="10" style="width:120px" />
            </div>
            <div class="form-group">
              <label class="form-label">对话文本<span class="req">*</span></label>
              <textarea v-model="manualText" class="textarea-field font-mono" style="min-height:180px"
                        placeholder="Speaker 1: 大家好&#10;Speaker 2: 你好，今天讨论什么主题？"></textarea>
              <div class="form-hint">每行格式：<code>Speaker N: 内容</code>，N 从 1 开始连续</div>
            </div>
          </div>
        </template>

        <!-- ============ 语音配置 ============ -->
        <div class="ms-sec">
          <div class="ms-sec-title" style="display:flex;align-items:center;justify-content:space-between">
            <span>语音配置</span>
            <button class="btn btn-secondary btn-sm" style="font-size:12px"
                    @click="showVoiceMgmt = true">⚙️ 管理真人音色</button>
          </div>

          <!-- 音色管理弹窗 -->
          <VoiceManageModal v-model:show="showVoiceMgmt" @updated="refreshVoices" />

          <div class="form-group">
            <label class="form-label">音色配置<span class="req">*</span></label>
            <div class="form-hint mb8">
              当前语言：{{ languages.find((l) => l.code === language)?.name }}
              — 音色列表已按语言筛选
            </div>
            <div v-for="i in speakerCount" :key="i" class="sp-row">
              <div class="sp-badge"
                   :style="{ background: speakerColors[(i - 1) % speakerColors.length] }">
                {{ i }}
              </div>
              <select :value="voiceAssignments[String(i)]?.voice_id || ''"
                      class="select-field" style="flex:1"
                      @change="setVoice(String(i), ($event.target as HTMLSelectElement).value)">
                <option value="">— 请选择音色 —</option>
                <option v-for="o in voiceOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
              </select>
            </div>
            <div v-if="voiceOptions.length === 0" class="form-hint" style="color:var(--warning)">
              ⚠ 当前语言无可用音色（CosyVoice 服务未连接？）
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">音频输出格式<span class="req">*</span></label>
            <select v-model="audioFormat" class="select-field" style="width:200px">
              <option value="mp3">MP3</option>
              <option value="wav">WAV</option>
              <option value="m4a">M4A</option>
            </select>
          </div>

          <div class="g2">
            <div class="form-group">
              <label class="form-label">保存到文件夹</label>
              <select v-model="folderId" class="select-field">
                <option v-for="o in folderOptions" :key="o.id" :value="o.id">{{ o.label }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">标签 Tag（可选）</label>
              <input v-model="tagInput" class="input-field" placeholder="多个用逗号分隔" />
              <div class="form-hint">如：复盘, Q2, 项目A</div>
            </div>
          </div>

          <label class="cb-row">
            <input v-model="generateScripts" type="checkbox" />
            <span>同时生成 JSON 和 SRT 脚本文件</span>
          </label>
          <div v-if="generateScripts" class="form-hint" style="margin-top:4px;padding-left:22px">
            生成完成后可在文件详情页下载，包含每段对话的精确时间码
          </div>
        </div>
      </div>

      <div class="mf">
        <button class="btn btn-secondary" @click="close">取消</button>
        <button class="btn btn-primary" :disabled="submitting" @click="submit">
          {{ submitting ? '提交中…' : '生成音频' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tag-input-wrap {
  display: flex; flex-wrap: wrap; gap: 5px; align-items: center;
  padding: 6px 10px; border: 1px solid var(--gray-300); border-radius: var(--r-sm);
  background: var(--clarity-white); min-height: 38px;
}
.tag-input-wrap:focus-within { border-color: var(--dark-warm-grey); box-shadow: 0 0 0 3px rgba(65,61,59,.10); }
.tag-input-wrap input { border: none; outline: none; font-size: 13px; flex: 1; min-width: 80px; background: none; padding: 1px 0; }
.ti-tag {
  display: inline-flex; align-items: center; gap: 3px; padding: 2px 8px;
  background: var(--gray-100); border: 1px solid var(--gray-300);
  color: var(--dark-warm-grey); border-radius: var(--r-pill);
  font-size: 12px; font-weight: 500;
}
.ti-tag .rm { cursor: pointer; color: var(--gray-400); font-size: 13px; line-height: 1; }
.ti-tag .rm:hover { color: var(--danger); }
code {
  background: var(--gray-100); padding: 1px 6px; border-radius: 3px;
  font-family: 'Courier New', monospace; font-size: 12px;
}
.g2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.cb-row {
  display: flex; align-items: center; gap: 7px;
  font-size: 13px; cursor: pointer; color: var(--gray-700);
  margin-top: 6px;
}
.cb-row input { accent-color: var(--primary); }

.template-hint {
  background: #F8FAFC;
  border: 1px solid var(--gray-200);
  border-radius: var(--r-md);
  padding: 11px 14px;
  margin-bottom: 14px;
  font-size: 12px;
  color: var(--gray-700);
  line-height: 1.7;
}
.template-hint-title { font-weight: 600; color: var(--gray-900); margin-bottom: 4px; }
.template-hint-desc { color: var(--gray-500); margin-bottom: 6px; }
.template-hint-meta { margin-top: 4px; }
.template-hint-meta strong { color: var(--gray-700); font-weight: 500; margin-right: 4px; }
</style>
