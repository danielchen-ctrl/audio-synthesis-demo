<script setup lang="ts">
import { ref, onMounted, h, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage, useDialog } from 'naive-ui'
import {
  listFiles, getDownloadUrl, deleteFile, batchDownload,
  type AudioFile, type ListFilesParams,
} from '@/api/files'
import { errorMessage } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import GenerateModal from '@/components/GenerateModal.vue'
import AdvancedSearch from '@/components/AdvancedSearch.vue'
import UploadModal from '@/components/UploadModal.vue'
import InlinePlayer from '@/components/InlinePlayer.vue'
import MoveFileModal from '@/components/MoveFileModal.vue'
import FilterChips from '@/components/FilterChips.vue'

const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const auth = useAuthStore()

const files = ref<AudioFile[]>([])
const loading = ref(false)
const showModal = ref(false)
const showAdvSearch = ref(false)
const showUpload = ref(false)

// 多选 / 批量下载
const selectedIds = ref<Set<string>>(new Set())
const selectedArray = computed(() => Array.from(selectedIds.value))
const allSelected = computed(() =>
  files.value.length > 0 && files.value.every((f) => selectedIds.value.has(f.file_id))
)
function toggleAll() {
  if (allSelected.value) selectedIds.value.clear()
  else files.value.forEach((f) => selectedIds.value.add(f.file_id))
  selectedIds.value = new Set(selectedIds.value)
}
function toggleOne(id: string) {
  if (selectedIds.value.has(id)) selectedIds.value.delete(id)
  else selectedIds.value.add(id)
  selectedIds.value = new Set(selectedIds.value)
}
function clearSelection() {
  selectedIds.value.clear()
  selectedIds.value = new Set(selectedIds.value)
}
const downloading = ref(false)
async function onBatchDownload() {
  if (selectedArray.value.length === 0) return
  if (selectedArray.value.length > 50) {
    message.warning(`已选 ${selectedArray.value.length} 个，单次最多下载 50 个`)
    return
  }
  downloading.value = true
  try {
    await batchDownload(selectedArray.value)
    message.success('下载已开始')
  } catch (e) { message.error(errorMessage(e)) }
  finally { downloading.value = false }
}
const q = ref('')
const activeFilters = reactive<Partial<ListFilesParams>>({})
const filterChipCount = ref(0)

async function fetchFiles() {
  loading.value = true
  try {
    files.value = await listFiles({
      ...activeFilters,
      q: q.value || undefined,
    })
  } catch (e) { message.error(errorMessage(e)) } finally { loading.value = false }
}

function applyAdvFilters(filters: Partial<ListFilesParams>) {
  // 清空旧的
  Object.keys(activeFilters).forEach((k) => { delete (activeFilters as any)[k] })
  Object.assign(activeFilters, filters)
  filterChipCount.value = Object.keys(filters).length
  fetchFiles()
}

function resetAdvFilters() {
  Object.keys(activeFilters).forEach((k) => { delete (activeFilters as any)[k] })
  filterChipCount.value = 0
  fetchFiles()
}

function removeFilterKeys(keys: string[]) {
  keys.forEach((k) => { delete (activeFilters as any)[k] })
  filterChipCount.value = Object.keys(activeFilters).length
  fetchFiles()
}

// 行内播放器：当前展开的 file_id
const playingId = ref<string | null>(null)
function onPlay(row: AudioFile) {
  playingId.value = playingId.value === row.file_id ? null : row.file_id
}

async function onDownload(row: AudioFile) {
  try {
    const { download_url } = await getDownloadUrl(row.file_id, true)
    window.location.href = download_url
  } catch (e) { message.error(errorMessage(e)) }
}

// 移动 modal
const showMove = ref(false)
const movingFile = ref<AudioFile | null>(null)
function openMoveModal(row: AudioFile) {
  if (!canEdit(row)) return
  movingFile.value = row
  showMove.value = true
}

function onDelete(row: AudioFile) {
  if (row.user_id !== auth.user?.user_id) {
    message.warning('只能删除自己的文件'); return
  }
  dialog.warning({
    title: '确认删除？', content: '文件将移入回收站，30 天内可恢复。',
    positiveText: '确认', negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteFile(row.file_id)
        message.success('已移入回收站')
        fetchFiles()
      } catch (e) { message.error(errorMessage(e)) }
    },
  })
}

function gotoDetail(fileId: string) { router.push(`/detail/${fileId}`) }
function fmtTime(s: string) {
  const utc = s.endsWith('Z') || s.includes('+') ? s : s + 'Z'
  return new Date(utc).toLocaleString('zh-CN', { hour12: false })
}
function fmtDuration(sec: number | null) {
  if (!sec) return '-'
  const m = Math.floor(sec / 60), s = Math.round(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
const langName: Record<string, string> = {
  zh: '中文', en: '英语', ja: '日语', ko: '韩语', es: '西语', fr: '法语',
  de: '德语', pt: '葡语', it: '意语', ru: '俄语', ar: '阿语', id: '印尼语',
}

const canEdit = (row: AudioFile) => row.user_id === auth.user?.user_id

onMounted(fetchFiles)

function onGenerated() {
  showModal.value = false
  message.success('任务已提交，请在【生成任务列表】查看进度')
}
</script>

<template>
  <div class="pg-hdr">
    <div>
      <div class="pg-title">全部文件</div>
      <div class="pg-sub">展示平台所有用户的音频语料</div>
    </div>
    <div class="flex gap-8">
      <button class="btn btn-secondary" @click="showUpload = true">⬆ 上传文件</button>
      <button class="btn btn-primary" @click="showModal = true">＋ 在线生成音频</button>
    </div>
  </div>

  <div class="search-row">
    <div class="sw flex-1">
      <span class="si">🔍</span>
      <input v-model="q" class="input-field" type="text"
             placeholder="搜索文件名 / 主题…" @keyup.enter="fetchFiles" />
    </div>
    <button class="btn btn-primary btn-sm" @click="fetchFiles">搜索</button>
    <div class="adv-wrap">
      <button class="btn btn-secondary btn-sm adv-trigger"
              :class="{ 'adv-active': showAdvSearch || filterChipCount > 0 }"
              @click="showAdvSearch = !showAdvSearch">
        高级搜索 <span v-if="filterChipCount > 0" class="adv-count">{{ filterChipCount }}</span> ▾
      </button>
      <AdvancedSearch v-model:open="showAdvSearch"
                      @apply="applyAdvFilters"
                      @reset="resetAdvFilters" />
    </div>
  </div>

  <!-- 已选 filter 条件展示 -->
  <FilterChips :filters="activeFilters"
               @remove="removeFilterKeys"
               @clear="resetAdvFilters" />

  <!-- 批量操作栏：全部文件只支持「批量下载」（其他用户的文件不能删/移动）-->
  <div v-if="selectedArray.length > 0" class="bulk-bar">
    <span class="bulk-count">已选中 {{ selectedArray.length }} 个文件</span>
    <div class="bulk-sep"></div>
    <button class="btn btn-secondary btn-sm" :disabled="downloading"
            @click="onBatchDownload">
      {{ downloading ? '打包中…' : '⬇ 批量下载' }}
    </button>
    <button class="btn btn-text btn-sm" @click="clearSelection">取消选择</button>
  </div>

  <div class="table-wrap">
    <table class="table">
      <thead>
        <tr>
          <th style="width:40px">
            <input type="checkbox" :checked="allSelected" @change="toggleAll" />
          </th>
          <th>文件名</th>
          <th style="width:80px">语言</th>
          <th style="width:70px">人数</th>
          <th style="width:90px">场景</th>
          <th style="width:80px">时长</th>
          <th style="width:80px">来源</th>
          <th style="width:160px">创建时间</th>
          <th style="width:120px">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading"><td colspan="9" class="empty"><div class="empty-desc">加载中…</div></td></tr>
        <tr v-else-if="files.length === 0">
          <td colspan="9">
            <div class="empty">
              <div class="empty-icon">📁</div>
              <div class="empty-title">{{ q || filterChipCount > 0 ? '暂无匹配的语料' : '暂无文件' }}</div>
              <div class="empty-desc">
                {{ q || filterChipCount > 0 ? '请尝试调整关键词或筛选条件' : '点击右上角【在线生成音频】生成一段试试' }}
              </div>
            </div>
          </td>
        </tr>
        <template v-else v-for="row in files" :key="row.file_id">
          <tr :class="{ selected: selectedIds.has(row.file_id) }">
            <td>
              <input type="checkbox"
                     :checked="selectedIds.has(row.file_id)"
                     @change="toggleOne(row.file_id)" />
            </td>
            <td>
              <span class="file-link" @click="gotoDetail(row.file_id)">{{ row.file_name }}</span>
              <span v-if="row.has_transcript" class="script-badge" title="包含对话脚本">SRT</span>
            </td>
            <td><span class="tag">{{ langName[row.language] || row.language }}</span></td>
            <td>{{ row.speaker_count }}</td>
            <td>{{ row.scene || '-' }}</td>
            <td>{{ fmtDuration(row.duration_sec) }}</td>
            <td>{{ row.source === 'generated' ? '生成' : '上传' }}</td>
            <td class="text-sm">{{ fmtTime(row.created_at) }}</td>
            <td>
              <div class="row-acts">
                <button class="ic-btn" :class="{ active: playingId === row.file_id }"
                        title="播放" @click="onPlay(row)">▶</button>
                <button class="ic-btn" title="下载" @click="onDownload(row)">⬇</button>
                <button class="ic-btn" :title="canEdit(row) ? '移动' : '只能移动自己的文件'"
                        :disabled="!canEdit(row)" @click="openMoveModal(row)">→</button>
                <button class="ic-btn d" :title="canEdit(row) ? '删除' : '只能删除自己的文件'"
                        :disabled="!canEdit(row)" @click="onDelete(row)">🗑</button>
              </div>
            </td>
          </tr>
          <tr v-if="playingId === row.file_id" class="mini-player-row">
            <td colspan="9">
              <InlinePlayer :file-id="row.file_id" :file-name="row.file_name"
                            @close="playingId = null" />
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </div>

  <generate-modal v-model:show="showModal" @generated="onGenerated" />
  <UploadModal v-model:show="showUpload" @uploaded="fetchFiles" />
  <MoveFileModal
    v-if="movingFile"
    v-model:show="showMove"
    :file-id="movingFile.file_id"
    :file-name="movingFile.file_name"
    :current-folder-id="movingFile.folder_id"
    @moved="fetchFiles"
  />
</template>

<style scoped>
.adv-wrap { position: relative; }
.bulk-bar {
  display: flex; align-items: center; gap: 10px;
  padding: 9px 14px;
  background: var(--gray-100);
  border: 1px solid var(--gray-300);
  border-radius: var(--r-md);
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.bulk-count { font-size: 13px; font-weight: 500; color: var(--deep-black); flex: 1; }
.bulk-sep { width: 1px; height: 16px; background: var(--gray-300); }
tr.selected td { background: var(--gray-50); }
input[type="checkbox"] { accent-color: var(--primary); cursor: pointer; }
.adv-active { background: var(--gray-100); border-color: var(--dark-warm-grey); color: var(--deep-black); }
.adv-count {
  display: inline-block; margin-left: 4px;
  min-width: 18px; padding: 0 5px;
  background: var(--primary); color: white;
  border-radius: var(--r-pill);
  font-size: 11px; line-height: 18px; text-align: center;
}
.mini-player-row td {
  padding: 6px 13px !important;
  background: var(--gray-50) !important;
}
.mini-player-row td:hover { background: var(--gray-50) !important; }
.ic-btn.active { background: var(--gray-100); color: var(--deep-black); }
.script-badge {
  display: inline-flex; align-items: center; gap: 2px;
  padding: 1px 6px; margin-left: 5px;
  background: rgba(33, 239, 106, .12);
  border: 1px solid rgba(33, 239, 106, .35);
  color: #0a5c23;
  border-radius: var(--r-pill);
  font-size: 10px; font-weight: 600;
  vertical-align: middle;
}
</style>
