<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useMessage } from 'naive-ui'
import client, { errorMessage } from '@/api/client'
import { listLanguages, type Language } from '@/api/meta'
import { listFolders, type FolderNode } from '@/api/folders'

const props = defineProps<{ show: boolean }>()
const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
  (e: 'uploaded'): void
}>()

const message = useMessage()
const file = ref<File | null>(null)
const dragOver = ref(false)
const uploading = ref(false)
const progress = ref(0)

const language = ref('zh')
const scene = ref('meeting')
const speakerCount = ref(2)
const folderId = ref<string>('')
const tagInput = ref('')

const languages = ref<Language[]>([])
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
  { id: '', label: '默认目录' },
  ...flattenFolders(folders.value),
])

async function loadMeta() {
  try {
    languages.value = await listLanguages()
    folders.value = await listFolders()
  } catch (e) { message.error(errorMessage(e)) }
}

watch(() => props.show, (v) => {
  if (v) {
    file.value = null
    progress.value = 0
    tagInput.value = ''
    loadMeta()
  }
})

function onFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files && target.files[0]) file.value = target.files[0]
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  dragOver.value = false
  if (e.dataTransfer?.files && e.dataTransfer.files[0]) {
    file.value = e.dataTransfer.files[0]
  }
}

const MAX_MB = 500
const ALLOWED = ['mp3', 'wav', 'm4a', 'mp4']

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

async function submit() {
  if (!file.value) { message.warning('请选择文件'); return }
  const ext = file.value.name.split('.').pop()?.toLowerCase() || ''
  if (!ALLOWED.includes(ext)) {
    message.error(`不支持的文件格式，请上传 ${ALLOWED.join('/').toUpperCase()}`); return
  }
  if (file.value.size > MAX_MB * 1024 * 1024) {
    message.error(`文件大小超出限制（最大 ${MAX_MB}MB），请压缩后重新上传`); return
  }

  const form = new FormData()
  form.append('file', file.value)
  form.append('language', language.value)
  form.append('scene', scene.value)
  form.append('speaker_count', String(speakerCount.value))
  if (folderId.value) form.append('folder_id', folderId.value)
  if (tagInput.value.trim()) form.append('tag_names', tagInput.value.trim())

  uploading.value = true
  try {
    await client.post('/files/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
      onUploadProgress: (e) => {
        if (e.total) progress.value = Math.round((e.loaded / e.total) * 100)
      },
    })
    message.success('上传成功')
    emit('uploaded')
    emit('update:show', false)
  } catch (e) { message.error(errorMessage(e)) }
  finally { uploading.value = false; progress.value = 0 }
}

function close() { emit('update:show', false) }
</script>

<template>
  <div class="mo" :class="{ open: show }" @click.self="close">
    <div class="modal modal-sm">
      <div class="mh"><div class="mt">上传音频文件</div>
        <button class="mc" @click="close">✕</button></div>

      <div class="mb">
        <div class="upload-zone" :class="{ drag: dragOver }"
             @click="($refs.fInput as HTMLInputElement).click()"
             @dragover.prevent="dragOver = true"
             @dragleave="dragOver = false"
             @drop="onDrop">
          <div class="upload-zone-icon">📂</div>
          <div class="upload-zone-text">点击选择文件，或拖拽到此处</div>
          <div class="upload-zone-hint">支持 WAV / MP3 / M4A / MP4，单文件 ≤ 500MB</div>
          <input ref="fInput" type="file" accept=".wav,.mp3,.m4a,.mp4"
                 style="display:none" @change="onFileChange" />
        </div>

        <div v-if="file" class="upload-info">
          <span style="font-size:20px">🎵</span>
          <div style="flex:1">
            <div style="font-weight:500;font-size:13px">{{ file.name }}</div>
            <div class="text-sm">{{ fmtSize(file.size) }}</div>
          </div>
          <button class="ic-btn d" @click="file = null">×</button>
        </div>

        <div v-if="uploading" class="upload-progress">
          上传中… {{ progress }}%
          <div class="upload-bar"><div :style="{ width: progress + '%' }"></div></div>
        </div>

        <div style="margin-top:14px">
          <div class="g2">
            <div class="form-group">
              <label class="form-label">语言<span class="req">*</span></label>
              <select v-model="language" class="select-field">
                <option v-for="l in languages" :key="l.code" :value="l.code">{{ l.name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">场景<span class="req">*</span></label>
              <select v-model="scene" class="select-field">
                <option value="meeting">会议讨论</option>
                <option value="interview">访谈</option>
                <option value="medical">问诊</option>
                <option value="other">其他</option>
              </select>
            </div>
          </div>
          <div class="g2">
            <div class="form-group">
              <label class="form-label">说话人数<span class="req">*</span></label>
              <input v-model.number="speakerCount" class="input-field" type="number" :min="1" :max="10" />
            </div>
            <div class="form-group">
              <label class="form-label">保存到文件夹</label>
              <select v-model="folderId" class="select-field">
                <option v-for="o in folderOptions" :key="o.id" :value="o.id">{{ o.label }}</option>
              </select>
            </div>
          </div>
          <div class="form-group">
            <label class="form-label">标签 Tag（可选）</label>
            <input v-model="tagInput" class="input-field" placeholder="如：会议, Q1, 项目A（逗号分隔）" />
            <div class="form-hint">多个标签用逗号分隔</div>
          </div>
        </div>
      </div>

      <div class="mf">
        <button class="btn btn-secondary" @click="close">取消</button>
        <button class="btn btn-primary" :disabled="uploading || !file" @click="submit">
          {{ uploading ? '上传中…' : '确认上传' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.upload-zone {
  border: 2px dashed var(--gray-300);
  border-radius: var(--r-md);
  padding: 28px 20px; text-align: center; cursor: pointer;
  transition: all .15s;
}
.upload-zone:hover, .upload-zone.drag {
  border-color: var(--primary); background: var(--primary-light);
}
.upload-zone-icon { font-size: 30px; margin-bottom: 8px; }
.upload-zone-text { font-size: 14px; font-weight: 500; color: var(--gray-700); }
.upload-zone-hint { font-size: 12px; color: var(--gray-400); margin-top: 3px; }
.upload-info {
  background: var(--gray-50); border: 1px solid var(--gray-200); border-radius: var(--r-sm);
  padding: 9px 13px; display: flex; align-items: center; gap: 10px; margin-top: 10px;
}
.upload-progress {
  margin-top: 10px; font-size: 12px; color: var(--gray-700);
}
.upload-bar {
  margin-top: 4px; height: 4px; background: var(--gray-200); border-radius: 2px; overflow: hidden;
}
.upload-bar div {
  height: 100%; background: var(--primary); transition: width .2s;
}
.g2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
</style>
