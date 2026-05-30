<script setup lang="ts">
import { ref, onMounted, computed, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage, useDialog } from 'naive-ui'
import {
  getFile, getDownloadUrl, deleteFile, getTranscript, updateFile,
  type AudioFile, type TranscriptLine,
} from '@/api/files'
import { errorMessage } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const auth = useAuthStore()

const file = ref<AudioFile | null>(null)
const downloadUrl = ref<string>('')
const audioRef = ref<HTMLAudioElement | null>(null)
const playing = ref(false)
const currentTime = ref(0)
const totalTime = ref(0)
const transcript = ref<TranscriptLine[]>([])
const hasTranscript = ref(false)
const voiceNames = ref<Record<string, string>>({})
const jsonDownloadUrl = ref<string | null>(null)
const srtDownloadUrl = ref<string | null>(null)

// 编辑状态
const editingBasic = ref(false)
const editingAttr = ref(false)
const editForm = reactive({
  file_name: '',
  language: '',
  speaker_count: 2,
  scene: 'meeting',
})

// 标签输入
const tagInput = ref('')

const SPEAKER_COLORS = ['#00D0FF', '#21EF6A', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16']
function speakerColor(sid: string): string {
  const n = parseInt(sid, 10)
  if (isNaN(n) || n < 1) return SPEAKER_COLORS[0]
  return SPEAKER_COLORS[(n - 1) % SPEAKER_COLORS.length]
}

const fileId = computed(() => route.params.id as string)
const isOwner = computed(() => file.value?.user_id === auth.user?.user_id)

async function fetchFile() {
  try {
    file.value = await getFile(fileId.value)
    const dl = await getDownloadUrl(fileId.value)
    downloadUrl.value = dl.download_url
    const tr = await getTranscript(fileId.value)
    hasTranscript.value = tr.has_transcript
    transcript.value = tr.lines
    voiceNames.value = tr.voice_names ?? {}
    jsonDownloadUrl.value = tr.json_download_url ?? null
    srtDownloadUrl.value = tr.srt_download_url ?? null
  } catch (e) { message.error(errorMessage(e)) }
}

function togglePlay() {
  if (!audioRef.value) return
  if (playing.value) audioRef.value.pause()
  else audioRef.value.play()
}

function onTimeUpdate() {
  if (!audioRef.value) return
  currentTime.value = audioRef.value.currentTime
  totalTime.value = audioRef.value.duration || 0
}

function seek(e: MouseEvent) {
  if (!audioRef.value || !totalTime.value) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const ratio = (e.clientX - rect.left) / rect.width
  audioRef.value.currentTime = ratio * totalTime.value
}

function fmtMS(s: number) {
  if (!s || !isFinite(s)) return '0:00'
  const m = Math.floor(s / 60), sec = Math.round(s % 60)
  return `${m}:${sec.toString().padStart(2, '0')}`
}
function fmtTime(s: string) {
  const utc = s.endsWith('Z') || s.includes('+') ? s : s + 'Z'
  return new Date(utc).toLocaleString('zh-CN', { hour12: false })
}

function onDownload() { if (downloadUrl.value) window.open(downloadUrl.value, '_blank') }

function onDelete() {
  dialog.warning({
    title: '确认删除？', content: '文件将移入回收站，30 天内可恢复',
    positiveText: '确认', negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteFile(fileId.value)
        message.success('已移入回收站')
        router.push('/myaudio')
      } catch (e) { message.error(errorMessage(e)) }
    },
  })
}

// ========== 基本信息编辑（仅文件名）==========
function startEditBasic() {
  if (!file.value) return
  editForm.file_name = file.value.file_name
  editingBasic.value = true
}
function cancelEditBasic() { editingBasic.value = false }
async function saveBasic() {
  if (!file.value || !editForm.file_name.trim()) {
    message.warning('文件名不能为空'); return
  }
  try {
    const updated = await updateFile(fileId.value, { file_name: editForm.file_name.trim() })
    file.value = updated
    editingBasic.value = false
    message.success('已保存')
  } catch (e) { message.error(errorMessage(e)) }
}

// ========== 语料属性编辑 ==========
function startEditAttr() {
  if (!file.value) return
  editForm.language = file.value.language
  editForm.speaker_count = file.value.speaker_count
  editForm.scene = file.value.scene
  editingAttr.value = true
}
function cancelEditAttr() { editingAttr.value = false }
async function saveAttr() {
  if (!file.value) return
  try {
    const updated = await updateFile(fileId.value, {
      language: editForm.language,
      speaker_count: editForm.speaker_count,
      scene: editForm.scene,
    })
    file.value = updated
    editingAttr.value = false
    message.success('已保存')
  } catch (e) { message.error(errorMessage(e)) }
}

// ========== 标签 ==========
async function addTag() {
  if (!file.value) return
  const name = tagInput.value.trim()
  if (!name) return
  if (file.value.tags.some((t) => t.name === name)) {
    message.warning('该标签已存在'); tagInput.value = ''; return
  }
  const newNames = [...file.value.tags.map((t) => t.name), name]
  try {
    const updated = await updateFile(fileId.value, { tag_names: newNames })
    file.value = updated
    tagInput.value = ''
  } catch (e) { message.error(errorMessage(e)) }
}

async function removeTag(name: string) {
  if (!file.value) return
  const newNames = file.value.tags.filter((t) => t.name !== name).map((t) => t.name)
  try {
    const updated = await updateFile(fileId.value, { tag_names: newNames })
    file.value = updated
  } catch (e) { message.error(errorMessage(e)) }
}

const langName: Record<string, string> = {
  zh: '中文（普通话）', en: '英语', ja: '日语', ko: '韩语', es: '西班牙语',
  fr: '法语', de: '德语', pt: '葡萄牙语', it: '意大利语', ru: '俄语', ar: '阿拉伯语', id: '印尼语',
}
const sceneName: Record<string, string> = {
  meeting: '会议讨论', interview: '访谈', medical: '问诊', custom: '自定义', other: '其他',
}

onMounted(fetchFile)
</script>

<template>
  <div class="dh">
    <button class="back-btn" @click="router.back()">← 返回</button>
    <div style="font-size:16px;font-weight:600;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
      {{ file?.file_name || '文件详情' }}
    </div>
    <!-- 顶部操作按钮 -->
    <div v-if="file" style="display:flex;gap:8px;flex-shrink:0">
      <button class="btn btn-secondary btn-sm" @click="onDownload">⬇ 下载</button>
      <button v-if="isOwner" class="btn btn-danger-ol btn-sm" @click="onDelete">🗑 删除</button>
    </div>
  </div>

  <div v-if="file" class="detail-grid">
    <!-- 左侧：播放器 + 对话文本 -->
    <div>
      <div class="card mb16">
        <div class="cs">
          <div class="audio-player">
            <button class="play-btn" @click="togglePlay">{{ playing ? '⏸' : '▶' }}</button>
            <div class="prog-wrap">
              <div class="prog-bar" @click="seek">
                <div class="prog-fill"
                     :style="{ width: totalTime ? (currentTime / totalTime * 100) + '%' : '0%' }"></div>
              </div>
              <div class="time-row">
                <span>{{ fmtMS(currentTime) }}</span>
                <span>{{ fmtMS(totalTime) }}</span>
              </div>
            </div>
          </div>
          <audio ref="audioRef" :src="downloadUrl"
                 @play="playing = true" @pause="playing = false"
                 @timeupdate="onTimeUpdate" @loadedmetadata="onTimeUpdate"></audio>
        </div>
      </div>

      <div class="card">
        <div class="cs">
          <div class="sec-title">对话文本</div>
          <div v-if="!hasTranscript" class="empty-desc">
            {{ file.source === 'uploaded' ? '上传的音频文件暂无脚本内容' : '未能加载脚本' }}
          </div>
          <div v-else>
            <div v-for="(line, i) in transcript" :key="i" class="tr-line">
              <div class="sp-info">
                <div class="sp-badge"
                     :style="{ background: speakerColor(line.speaker_id), color: '#000' }">
                  {{ line.speaker_id }}
                </div>
                <div v-if="voiceNames[line.speaker_id]" class="sp-voice-name">
                  {{ voiceNames[line.speaker_id] }}
                </div>
              </div>
              <div class="tr-text">
                <span v-if="line.start_time != null" class="tr-time">
                  {{ fmtMS(line.start_time) }} – {{ fmtMS(line.end_time ?? line.start_time) }}
                </span>
                {{ line.text }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧：基本信息 / 语料属性 / 标签 / 文件操作 -->
    <div>
      <!-- 基本信息 -->
      <div class="card mb16">
        <div class="cs">
          <div class="sec-title">
            基本信息
            <div v-if="isOwner" class="det-btns">
              <button v-if="!editingBasic" class="btn btn-text btn-sm" @click="startEditBasic">✏ 编辑</button>
              <template v-else>
                <button class="btn btn-primary btn-sm" @click="saveBasic">保存</button>
                <button class="btn btn-secondary btn-sm" @click="cancelEditBasic">取消</button>
              </template>
            </div>
          </div>

          <template v-if="!editingBasic">
            <div class="ig">
              <div class="il">文件名称</div><div class="iv">{{ file.file_name }}</div>
              <div class="il">创建者</div>
              <div class="iv">{{ isOwner ? auth.user?.username : '其他用户' }}</div>
              <div class="il">创建时间</div><div class="iv">{{ fmtTime(file.created_at) }}</div>
              <div class="il">音频时长</div>
              <div class="iv">{{ file.duration_sec ? fmtMS(file.duration_sec) : '-' }}</div>
              <div class="il">音频格式</div><div class="iv">{{ (file.format || '').toUpperCase() }}</div>
              <div class="il">文件大小</div>
              <div class="iv">{{ (file.file_size / 1024 / 1024).toFixed(2) }} MB</div>
            </div>
          </template>
          <template v-else>
            <div class="form-group">
              <label class="form-label">文件名称<span class="req">*</span></label>
              <input v-model="editForm.file_name" class="input-field" />
              <div class="form-hint">仅修改名称，扩展名保持不变</div>
            </div>
          </template>
        </div>
      </div>

      <!-- 语料属性 -->
      <div class="card mb16">
        <div class="cs">
          <div class="sec-title">
            语料属性
            <div v-if="isOwner" class="det-btns">
              <button v-if="!editingAttr" class="btn btn-text btn-sm" @click="startEditAttr">✏ 编辑</button>
              <template v-else>
                <button class="btn btn-primary btn-sm" @click="saveAttr">保存</button>
                <button class="btn btn-secondary btn-sm" @click="cancelEditAttr">取消</button>
              </template>
            </div>
          </div>

          <template v-if="!editingAttr">
            <div class="ig">
              <div class="il">语言</div><div class="iv">{{ langName[file.language] || file.language }}</div>
              <div class="il">人数</div><div class="iv">{{ file.speaker_count }}</div>
              <div class="il">场景</div><div class="iv">{{ sceneName[file.scene] || file.scene }}</div>
              <div class="il">来源</div>
              <div class="iv">{{ file.source === 'generated' ? '在线生成' : '用户上传' }}</div>
              <div v-if="file.topic" class="il">主题</div>
              <div v-if="file.topic" class="iv">{{ file.topic }}</div>
            </div>
          </template>
          <template v-else>
            <div class="form-group">
              <label class="form-label">语言</label>
              <select v-model="editForm.language" class="select-field">
                <option v-for="(name, code) in langName" :key="code" :value="code">{{ name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">说话人数</label>
              <input v-model.number="editForm.speaker_count" class="input-field" type="number" :min="1" :max="10" />
            </div>
            <div class="form-group">
              <label class="form-label">场景</label>
              <select v-model="editForm.scene" class="select-field">
                <option v-for="(name, code) in sceneName" :key="code" :value="code">{{ name }}</option>
              </select>
            </div>
          </template>
        </div>
      </div>

      <!-- 标签 -->
      <div class="card mb16">
        <div class="cs">
          <div class="sec-title">标签</div>
          <div class="tag-list">
            <span v-for="t in file.tags" :key="t.tag_id" class="tag">
              {{ t.name }}
              <span v-if="isOwner" class="trm" @click="removeTag(t.name)">×</span>
            </span>
            <input v-if="isOwner" v-model="tagInput" class="input-field"
                   type="text" placeholder="+ 添加标签"
                   style="width:120px;font-size:12px;padding:3px 7px"
                   @keyup.enter="addTag" />
          </div>
          <div v-if="file.tags.length === 0 && !isOwner" class="empty-desc">无标签</div>
        </div>
      </div>

      <!-- 脚本下载（JSON/SRT，仅有脚本时显示）-->
      <div v-if="jsonDownloadUrl || srtDownloadUrl" class="card">
        <div class="cs">
          <div class="sec-title">脚本下载</div>
          <div class="op-list">
            <a v-if="jsonDownloadUrl" :href="jsonDownloadUrl"
               class="btn btn-secondary btn-sm" target="_blank" download>⬇ JSON</a>
            <a v-if="srtDownloadUrl" :href="srtDownloadUrl"
               class="btn btn-secondary btn-sm" target="_blank" download>⬇ SRT</a>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div v-else class="empty">
    <div class="empty-desc">加载中…</div>
  </div>
</template>

<style scoped>
.sp-info {
  display: flex; flex-direction: column; align-items: center; gap: 3px;
  min-width: 44px;
}
.sp-voice-name {
  font-size: 10px; color: var(--gray-500);
  text-align: center; white-space: nowrap;
  max-width: 56px; overflow: hidden; text-overflow: ellipsis;
}
.tr-time {
  display: inline-block;
  font-family: 'Courier New', monospace;
  font-size: 11px;
  color: var(--gray-400);
  margin-right: 8px;
}
.tag-list {
  display: flex; flex-wrap: wrap; gap: 5px; align-items: center;
}
.tag .trm {
  cursor: pointer; color: var(--gray-400); margin-left: 2px;
}
.tag .trm:hover { color: var(--danger); }
</style>
