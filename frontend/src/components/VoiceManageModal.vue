<script setup lang="ts">
import { ref, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { listVoicesFromDB, registerVoice, renameVoice, deleteVoice, type Voice } from '@/api/voices'
import { errorMessage } from '@/api/client'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
  (e: 'updated'): void  // 音色列表变化，通知父组件刷新
}>()

const message = useMessage()

// ── 已注册音色列表 ─────────────────────────────────────────────────────────
const voices = ref<Voice[]>([])
const loadingList = ref(false)

async function refreshList() {
  loadingList.value = true
  try {
    voices.value = await listVoicesFromDB()
  } catch (e) {
    message.error(errorMessage(e))
  } finally {
    loadingList.value = false
  }
}

watch(() => props.show, (v) => { if (v) refreshList() })

// ── 新音色注册表单 ──────────────────────────────────────────────────────────
const audioFile = ref<File | null>(null)
const audioFileName = ref('')
const formName = ref('')
const formLanguage = ref('zh')
const formGender = ref<'male' | 'female' | ''>('')
const formRefText = ref('')
const submitting = ref(false)
const lastResult = ref<{ verified: boolean; message: string } | null>(null)

const LANGUAGES = [
  { code: 'zh', name: '中文' }, { code: 'en', name: '英语' },
  { code: 'ja', name: '日语' }, { code: 'ko', name: '韩语' },
  { code: 'es', name: '西班牙语' }, { code: 'fr', name: '法语' },
  { code: 'de', name: '德语' }, { code: 'pt', name: '葡萄牙语' },
  { code: 'it', name: '意大利语' }, { code: 'ru', name: '俄语' },
  { code: 'ar', name: '阿拉伯语' }, { code: 'id', name: '印尼语' },
]

function handleFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (f) { audioFile.value = f; audioFileName.value = f.name }
  input.value = ''
}

function handleDrop(e: DragEvent) {
  e.preventDefault()
  const f = e.dataTransfer?.files[0]
  if (f) { audioFile.value = f; audioFileName.value = f.name }
}

async function submitRegister() {
  if (!audioFile.value) { message.warning('请选择参考音频文件'); return }
  if (!formName.value.trim()) { message.warning('请填写音色名称'); return }
  submitting.value = true
  lastResult.value = null
  try {
    const resp = await registerVoice(audioFile.value, {
      name: formName.value.trim(),
      language: formLanguage.value,
      gender: formGender.value || undefined,
      reference_text: formRefText.value.trim() || undefined,
    })
    lastResult.value = { verified: resp.verified, message: resp.message }
    if (resp.verified) {
      message.success(`「${resp.name}」注册成功`)
      resetForm()
      await refreshList()
      emit('updated')
    }
  } catch (e) {
    message.error(errorMessage(e))
  } finally {
    submitting.value = false
  }
}

// ── 内联重命名 ─────────────────────────────────────────────────────────────
const editingId = ref<string | null>(null)
const editingName = ref('')

function startEdit(v: Voice) {
  editingId.value = v.voice_id
  editingName.value = v.name
}

function cancelEdit() {
  editingId.value = null
  editingName.value = ''
}

async function confirmEdit(v: Voice) {
  const newName = editingName.value.trim()
  if (!newName) { message.warning('名称不能为空'); return }
  if (newName === v.name) { cancelEdit(); return }
  try {
    await renameVoice(v.voice_id, newName)
    message.success(`已重命名为「${newName}」`)
    cancelEdit()
    await refreshList()
    emit('updated')
  } catch (e) {
    message.error(errorMessage(e))
  }
}

async function handleDelete(v: Voice) {
  try {
    await deleteVoice(v.voice_id)
    message.success(`已删除「${v.name}」`)
    await refreshList()
    emit('updated')
  } catch (e) {
    message.error(errorMessage(e))
  }
}

function resetForm() {
  audioFile.value = null
  audioFileName.value = ''
  formName.value = ''
  formLanguage.value = 'zh'
  formGender.value = ''
  formRefText.value = ''
}

function close() { emit('update:show', false) }
</script>

<template>
  <div v-if="show" class="vm-overlay" @click.self="close">
    <div class="vm-modal">
      <!-- 标题栏 -->
      <div class="vm-header">
        <span class="vm-title">⚙️ 管理真人音色</span>
        <button class="vm-close" @click="close">✕</button>
      </div>

      <div class="vm-body">
        <!-- 已注册音色列表 -->
        <div class="vm-section">
          <div class="vm-section-title">已注册音色</div>
          <div v-if="loadingList" class="vm-hint">加载中…</div>
          <div v-else-if="voices.length === 0" class="vm-hint">暂无注册音色</div>
          <div v-else class="vm-list">
            <div v-for="v in voices" :key="v.voice_id" class="vm-item">
              <!-- 编辑状态 -->
              <template v-if="editingId === v.voice_id">
                <input
                  v-model="editingName"
                  class="vm-edit-input"
                  @keyup.enter="confirmEdit(v)"
                  @keyup.escape="cancelEdit"
                  autofocus
                />
                <div class="vm-edit-btns">
                  <button class="vm-confirm-btn" title="确认" @click="confirmEdit(v)">✓</button>
                  <button class="vm-cancel-btn" title="取消" @click="cancelEdit">✕</button>
                </div>
              </template>
              <!-- 普通状态 -->
              <template v-else>
                <div class="vm-item-info">
                  <span class="vm-item-name">{{ v.name }}</span>
                  <span class="vm-item-meta">{{ v.language }}{{ v.gender ? ` · ${v.gender}` : '' }}</span>
                </div>
                <div class="vm-item-actions">
                  <button class="vm-edit-btn" title="重命名" @click="startEdit(v)">✏️</button>
                  <button class="vm-del-btn" title="删除" @click="handleDelete(v)">🗑</button>
                </div>
              </template>
            </div>
          </div>
        </div>

        <hr class="vm-divider" />

        <!-- 注册新音色 -->
        <div class="vm-section">
          <div class="vm-section-title">➕ 注册新音色</div>

          <!-- 上传区 -->
          <div
            class="vm-upload-area"
            :class="{ 'has-file': !!audioFile }"
            @dragover.prevent
            @drop="handleDrop"
            @click="($refs.fileInput as HTMLInputElement).click()"
          >
            <input ref="fileInput" type="file" accept="audio/*,.mp3,.wav,.m4a,.ogg" hidden @change="handleFileChange" />
            <div v-if="audioFile" class="vm-file-name">📎 {{ audioFileName }}</div>
            <div v-else class="vm-upload-hint">
              <div>点击或拖拽上传参考音频</div>
              <div class="vm-upload-sub">单人朗读，清晰无噪音，10-30 秒</div>
            </div>
          </div>

          <div class="vm-form">
            <div class="vm-form-row">
              <label>音色名称 <span class="req">*</span></label>
              <input v-model="formName" class="vm-input" placeholder="如：耿同学" />
            </div>
            <div class="vm-form-row vm-form-2col">
              <div>
                <label>语言 <span class="req">*</span></label>
                <select v-model="formLanguage" class="vm-select">
                  <option v-for="l in LANGUAGES" :key="l.code" :value="l.code">{{ l.name }}</option>
                </select>
              </div>
              <div>
                <label>性别</label>
                <select v-model="formGender" class="vm-select">
                  <option value="">不设置</option>
                  <option value="male">男</option>
                  <option value="female">女</option>
                </select>
              </div>
            </div>
            <div class="vm-form-row">
              <label>参考文本（可选）</label>
              <input v-model="formRefText" class="vm-input" placeholder="参考音频对应的文字内容" />
            </div>
          </div>

          <!-- 上次结果提示 -->
          <div v-if="lastResult" :class="['vm-result', lastResult.verified ? 'success' : 'fail']">
            {{ lastResult.verified ? '✅' : '⚠️' }} {{ lastResult.message }}
          </div>

          <button class="vm-submit-btn" :disabled="submitting" @click="submitRegister">
            {{ submitting ? '验证中…' : '注册音色' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.vm-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,.45);
  z-index: 9999;
  display: flex; align-items: center; justify-content: center;
}
.vm-modal {
  background: #fff; border-radius: 12px;
  width: 480px; max-width: 95vw;
  max-height: 90vh; display: flex; flex-direction: column;
  box-shadow: 0 8px 40px rgba(0,0,0,.18);
}
.vm-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px 12px; border-bottom: 1px solid #eee;
}
.vm-title { font-size: 15px; font-weight: 600; }
.vm-close {
  background: none; border: none; cursor: pointer;
  font-size: 16px; color: #999; padding: 2px 6px;
}
.vm-close:hover { color: #333; }
.vm-body { overflow-y: auto; padding: 0 20px 20px; flex: 1; }
.vm-section { padding-top: 16px; }
.vm-section-title { font-size: 13px; font-weight: 600; color: #555; margin-bottom: 10px; }
.vm-hint { font-size: 13px; color: #aaa; }
.vm-list {
  display: flex; flex-direction: column; gap: 8px;
  max-height: 240px; overflow-y: auto; padding-right: 4px;
}
.vm-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; background: #f8f9fa; border-radius: 8px;
}
.vm-item-info { display: flex; flex-direction: column; gap: 2px; }
.vm-item-name { font-size: 13px; font-weight: 500; }
.vm-item-meta { font-size: 11px; color: #999; }
.vm-item-actions { display: flex; gap: 4px; align-items: center; }
.vm-edit-btn, .vm-del-btn {
  background: none; border: none; cursor: pointer;
  font-size: 14px; opacity: .45; padding: 2px 4px;
}
.vm-edit-btn:hover, .vm-del-btn:hover { opacity: 1; }
.vm-edit-input {
  flex: 1; padding: 4px 8px; border: 1px solid #3B82F6;
  border-radius: 6px; font-size: 13px; outline: none;
}
.vm-edit-btns { display: flex; gap: 4px; margin-left: 6px; }
.vm-confirm-btn {
  background: #3B82F6; color: #fff; border: none; border-radius: 5px;
  padding: 3px 8px; cursor: pointer; font-size: 13px;
}
.vm-confirm-btn:hover { background: #2563eb; }
.vm-cancel-btn {
  background: #e5e7eb; color: #555; border: none; border-radius: 5px;
  padding: 3px 8px; cursor: pointer; font-size: 13px;
}
.vm-cancel-btn:hover { background: #d1d5db; }
.vm-divider { border: none; border-top: 1px solid #eee; margin: 12px 0 0; }
.vm-upload-area {
  border: 2px dashed #d0d0d0; border-radius: 8px;
  padding: 20px; text-align: center; cursor: pointer;
  transition: border-color .2s;
  margin-bottom: 14px;
}
.vm-upload-area:hover, .vm-upload-area.has-file { border-color: #3B82F6; }
.vm-upload-hint { font-size: 13px; color: #888; }
.vm-upload-sub { font-size: 11px; color: #aaa; margin-top: 4px; }
.vm-file-name { font-size: 13px; color: #3B82F6; font-weight: 500; }
.vm-form { display: flex; flex-direction: column; gap: 10px; }
.vm-form-row { display: flex; flex-direction: column; gap: 4px; }
.vm-form-row label { font-size: 12px; color: #666; }
.vm-form-2col { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.req { color: #ef4444; }
.vm-input, .vm-select {
  padding: 7px 10px; border: 1px solid #d0d0d0; border-radius: 6px;
  font-size: 13px; width: 100%; box-sizing: border-box; outline: none;
}
.vm-input:focus, .vm-select:focus { border-color: #3B82F6; }
.vm-result {
  margin-top: 10px; padding: 8px 12px; border-radius: 6px;
  font-size: 12px; line-height: 1.5;
}
.vm-result.success { background: #f0fdf4; color: #15803d; }
.vm-result.fail { background: #fff7ed; color: #c2410c; }
.vm-submit-btn {
  margin-top: 14px; width: 100%;
  background: #3B82F6; color: #fff;
  border: none; border-radius: 8px;
  padding: 10px; font-size: 14px; font-weight: 500;
  cursor: pointer; transition: opacity .2s;
}
.vm-submit-btn:hover { opacity: .9; }
.vm-submit-btn:disabled { opacity: .5; cursor: not-allowed; }
</style>
