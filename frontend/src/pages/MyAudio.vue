<script setup lang="ts">
import { ref, onMounted, watch, computed, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage, useDialog } from 'naive-ui'
import {
  listFiles, getDownloadUrl, deleteFile,
  batchDelete, batchDownload,
  type AudioFile, type ListFilesParams,
} from '@/api/files'
import { errorMessage } from '@/api/client'
import { useFolderStore } from '@/stores/folders'
import GenerateModal from '@/components/GenerateModal.vue'
import MoveFileModal from '@/components/MoveFileModal.vue'
import BatchMoveModal from '@/components/BatchMoveModal.vue'
import UploadModal from '@/components/UploadModal.vue'
import AdvancedSearch from '@/components/AdvancedSearch.vue'
import InlinePlayer from '@/components/InlinePlayer.vue'
import FilterChips from '@/components/FilterChips.vue'

const router = useRouter()
const message = useMessage()
const dialog = useDialog()
const folderStore = useFolderStore()

const files = ref<AudioFile[]>([])
const loading = ref(false)
const q = ref('')

// 高级搜索
const showAdvSearch = ref(false)
const activeFilters = reactive<Partial<ListFilesParams>>({})
const filterChipCount = ref(0)

function applyAdvFilters(filters: Partial<ListFilesParams>) {
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

// 多选状态（为后续批量操作铺路）
const selectedIds = ref<Set<string>>(new Set())

// Modal
const showGen = ref(false)
const showUpload = ref(false)
const showMove = ref(false)
const movingFile = ref<AudioFile | null>(null)
const showBatchMove = ref(false)

const headerTitle = computed(() => {
  if (folderStore.selected === '__all__') return '我的文件'
  if (folderStore.selected === null) return '默认目录'
  const path = folderStore.pathOf(folderStore.selected as string)
  return path[path.length - 1] || '我的文件'
})

const headerSub = computed(() => {
  if (folderStore.selected === '__all__') return '仅展示我创建或上传的文件'
  if (folderStore.selected === null) return '根目录（未归入任何文件夹）'
  return folderStore.pathOf(folderStore.selected as string).join(' / ')
})

async function fetchFiles() {
  loading.value = true
  selectedIds.value.clear()
  try {
    const base: ListFilesParams = {
      mine_only: true,
      q: q.value || undefined,
      ...activeFilters,
    }
    if (folderStore.selected === '__all__') {
      files.value = await listFiles(base)
    } else if (folderStore.selected === null) {
      files.value = await listFiles({ ...base, root_only: true })
    } else {
      files.value = await listFiles({ ...base, folder_id: folderStore.selected as string })
    }
  } catch (e) { message.error(errorMessage(e)) }
  finally { loading.value = false }
}

// 文件夹切换 → 重拉
watch(() => folderStore.selected, fetchFiles)

// 行内播放器
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
function openMoveModal(row: AudioFile) {
  movingFile.value = row
  showMove.value = true
}
function onFileDelete(row: AudioFile) {
  dialog.warning({
    title: '确认删除？', content: '文件将移入回收站，30 天内可恢复。',
    positiveText: '确认', negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await deleteFile(row.file_id)
        message.success('已移入回收站')
        await Promise.all([fetchFiles(), folderStore.load()])
      } catch (e) { message.error(errorMessage(e)) }
    },
  })
}
function gotoDetail(fileId: string) { router.push(`/detail/${fileId}`) }

// ---- 多选 / 批量 ----
const selectedArray = computed(() => Array.from(selectedIds.value))
const allSelected = computed(() =>
  files.value.length > 0 && files.value.every((f) => selectedIds.value.has(f.file_id))
)

function onBatchDelete() {
  if (selectedArray.value.length === 0) return
  dialog.warning({
    title: `删除 ${selectedArray.value.length} 个文件？`,
    content: '文件将移入回收站，30 天内可恢复。',
    positiveText: '确认', negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await batchDelete(selectedArray.value)
        message.success(`已删除 ${selectedArray.value.length} 个文件`)
        await Promise.all([fetchFiles(), folderStore.load()])
      } catch (e) { message.error(errorMessage(e)) }
    },
  })
}
function onBatchMove() {
  if (selectedArray.value.length === 0) return
  showBatchMove.value = true
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
function clearSelection() {
  selectedIds.value.clear()
  selectedIds.value = new Set(selectedIds.value)
}
function toggleAll() {
  if (allSelected.value) selectedIds.value.clear()
  else files.value.forEach((f) => selectedIds.value.add(f.file_id))
  // 触发响应式
  selectedIds.value = new Set(selectedIds.value)
}
function toggleOne(id: string) {
  if (selectedIds.value.has(id)) selectedIds.value.delete(id)
  else selectedIds.value.add(id)
  selectedIds.value = new Set(selectedIds.value)
}

// ---- 工具 ----
function fmtTime(s: string) { return new Date(s).toLocaleString('zh-CN', { hour12: false }) }
function fmtDuration(sec: number | null) {
  if (!sec) return '-'
  const m = Math.floor(sec / 60), s = Math.round(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
const langName: Record<string, string> = {
  zh: '中文', en: '英语', ja: '日语', ko: '韩语', es: '西语', fr: '法语',
  de: '德语', pt: '葡语', it: '意语', ru: '俄语', ar: '阿语', id: '印尼语',
}
function folderPath(folderId: string | null): string {
  if (!folderId) return '默认目录'
  return folderStore.pathOf(folderId).join(' / ')
}

onMounted(async () => {
  if (!folderStore.loaded) await folderStore.load()
  fetchFiles()
})

function onGenerated() {
  showGen.value = false
  message.success('任务已提交，请在【生成任务列表】查看进度')
}
</script>

<template>
  <div class="pg-hdr">
    <div>
      <div class="pg-title">{{ headerTitle }}</div>
      <div class="pg-sub">{{ headerSub }}</div>
    </div>
    <div class="flex gap-8">
      <button class="btn btn-secondary" @click="showUpload = true">⬆ 上传文件</button>
      <button class="btn btn-primary" @click="showGen = true">＋ 在线生成音频</button>
    </div>
  </div>

  <div class="search-row">
    <div class="sw flex-1">
      <span class="si">🔍</span>
      <input v-model="q" class="input-field" type="text"
             placeholder="搜索我的文件名…" @keyup.enter="fetchFiles" />
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

  <!-- 批量操作栏 -->
  <div v-if="selectedArray.length > 0" class="bulk-bar">
    <span class="bulk-count">已选中 {{ selectedArray.length }} 个文件</span>
    <div class="bulk-sep"></div>
    <button class="btn btn-secondary btn-sm" :disabled="downloading" @click="onBatchDownload">
      {{ downloading ? '打包中…' : '⬇ 批量下载' }}
    </button>
    <button class="btn btn-secondary btn-sm" @click="onBatchMove">→ 批量移动</button>
    <button class="btn btn-danger-ol btn-sm" @click="onBatchDelete">🗑 批量删除</button>
    <div class="bulk-sep"></div>
    <button class="btn btn-text btn-sm" @click="clearSelection">取消选择</button>
  </div>

  <div class="table-wrap">
    <table class="table">
      <thead>
        <tr>
          <th style="width:40px">
            <input type="checkbox" :checked="allSelected" @change="toggleAll" />
          </th>
          <th>文件名称</th>
          <th style="width:200px">所属文件夹</th>
          <th style="width:80px">语言</th>
          <th style="width:60px">人数</th>
          <th style="width:90px">场景</th>
          <th style="width:80px">时长</th>
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
              <div class="empty-title">该位置暂无文件</div>
              <div class="empty-desc">点击右上角【在线生成音频】或【上传文件】</div>
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
            <td class="folder-path">{{ folderPath(row.folder_id) }}</td>
            <td><span class="tag">{{ langName[row.language] || row.language }}</span></td>
            <td>{{ row.speaker_count }}</td>
            <td>{{ row.scene || '-' }}</td>
            <td>{{ fmtDuration(row.duration_sec) }}</td>
            <td class="text-sm">{{ fmtTime(row.created_at) }}</td>
            <td>
              <div class="row-acts">
                <button class="ic-btn" :class="{ active: playingId === row.file_id }"
                        title="播放" @click="onPlay(row)">▶</button>
                <button class="ic-btn" title="下载" @click="onDownload(row)">⬇</button>
                <button class="ic-btn" title="移动" @click="openMoveModal(row)">→</button>
                <button class="ic-btn d" title="删除" @click="onFileDelete(row)">🗑</button>
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

  <generate-modal v-model:show="showGen" @generated="onGenerated" />
  <UploadModal v-model:show="showUpload" @uploaded="fetchFiles" />
  <MoveFileModal
    v-if="movingFile"
    v-model:show="showMove"
    :file-id="movingFile.file_id"
    :file-name="movingFile.file_name"
    :current-folder-id="movingFile.folder_id"
    @moved="async () => { await Promise.all([fetchFiles(), folderStore.load()]) }"
  />
  <BatchMoveModal
    v-model:show="showBatchMove"
    :file-ids="selectedArray"
    @moved="async () => { clearSelection(); await Promise.all([fetchFiles(), folderStore.load()]) }"
  />
</template>

<style scoped>
.adv-wrap { position: relative; }
.adv-active { background: var(--gray-100); border-color: var(--dark-warm-grey); color: var(--deep-black); }
.adv-count {
  display: inline-block; margin-left: 4px;
  min-width: 18px; padding: 0 5px;
  background: var(--primary); color: white;
  border-radius: var(--r-pill);
  font-size: 11px; line-height: 18px; text-align: center;
}
.folder-path {
  font-size: 12px;
  color: var(--gray-500);
}
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
tr.selected td { background: var(--gray-50); }
input[type="checkbox"] { accent-color: var(--primary); cursor: pointer; }
.mini-player-row td {
  padding: 6px 13px !important;
  background: var(--gray-50) !important;
}
.mini-player-row td:hover { background: var(--gray-50) !important; }
.ic-btn.active { background: var(--gray-100); color: var(--deep-black); }

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
</style>
