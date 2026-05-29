<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useMessage, useDialog } from 'naive-ui'
import client, { errorMessage } from '@/api/client'
import {
  restoreFile, purgeFile,
  batchRestore, batchPurge,
  type AudioFile,
} from '@/api/files'

const message = useMessage()
const dialog = useDialog()

const files = ref<AudioFile[]>([])
const loading = ref(false)
const selectedIds = ref<Set<string>>(new Set())

async function fetchTrash() {
  loading.value = true
  selectedIds.value.clear()
  try {
    const resp = await client.get('/files/trash')
    files.value = resp.data
  } catch (e) { message.error(errorMessage(e)) }
  finally { loading.value = false }
}

function onRestore(row: AudioFile) {
  dialog.success({
    title: '恢复文件？',
    content: `文件「${row.file_name}」将从回收站恢复`,
    positiveText: '确认恢复', negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await restoreFile(row.file_id)
        message.success('已恢复')
        fetchTrash()
      } catch (e) { message.error(errorMessage(e)) }
    },
  })
}

function onPurge(row: AudioFile) {
  dialog.warning({
    title: '永久删除？',
    content: `文件「${row.file_name}」将被永久删除，此操作不可恢复。`,
    positiveText: '永久删除', negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await purgeFile(row.file_id)
        message.success('已永久删除')
        fetchTrash()
      } catch (e) { message.error(errorMessage(e)) }
    },
  })
}

// 批量
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

function onBatchRestore() {
  if (selectedArray.value.length === 0) return
  dialog.success({
    title: `恢复 ${selectedArray.value.length} 个文件？`,
    positiveText: '确认恢复', negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await batchRestore(selectedArray.value)
        message.success(`已恢复 ${selectedArray.value.length} 个文件`)
        fetchTrash()
      } catch (e) { message.error(errorMessage(e)) }
    },
  })
}

function onBatchPurge() {
  if (selectedArray.value.length === 0) return
  dialog.warning({
    title: `永久删除 ${selectedArray.value.length} 个文件？`,
    content: '此操作不可恢复，请确认。',
    positiveText: '永久删除', negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await batchPurge(selectedArray.value)
        message.success(`已永久删除 ${selectedArray.value.length} 个文件`)
        fetchTrash()
      } catch (e) { message.error(errorMessage(e)) }
    },
  })
}

function fmtTime(s: string) { return new Date(s).toLocaleString('zh-CN', { hour12: false }) }

// 回收站保留 30 天，计算剩余天数（PRD §13.4）
function daysLeft(deletedAt: string | null | undefined): { days: number; cls: string } {
  if (!deletedAt) return { days: 30, cls: 'days-ok' }
  const deletedTime = new Date(deletedAt).getTime()
  const elapsed = Math.floor((Date.now() - deletedTime) / 86400000)
  const left = Math.max(0, 30 - elapsed)
  return { days: left, cls: left <= 7 ? 'days-warn' : 'days-ok' }
}

onMounted(fetchTrash)
</script>

<template>
  <div class="pg-hdr">
    <div>
      <div class="pg-title">回收站</div>
      <div class="pg-sub">软删除文件保留 30 天后自动永久删除</div>
    </div>
  </div>

  <!-- 批量操作栏（选中时显示）-->
  <div v-if="selectedArray.length > 0" class="bulk-bar">
    <span class="bulk-count">已选中 {{ selectedArray.length }} 个文件</span>
    <div class="bulk-sep"></div>
    <button class="btn btn-secondary btn-sm" @click="onBatchRestore">批量恢复</button>
    <button class="btn btn-danger-ol btn-sm" @click="onBatchPurge">批量永久删除</button>
    <button class="btn btn-text btn-sm" @click="selectedIds.clear(); selectedIds = new Set(selectedIds)">取消选择</button>
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
          <th style="width:90px">场景</th>
          <th style="width:160px">删除时间</th>
          <th style="width:120px">剩余天数</th>
          <th style="width:180px">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading"><td colspan="7" class="empty"><div class="empty-desc">加载中…</div></td></tr>
        <tr v-else-if="files.length === 0">
          <td colspan="7">
            <div class="empty">
              <div class="empty-icon">🗑</div>
              <div class="empty-title">回收站是空的</div>
              <div class="empty-desc">删除的文件会显示在这里，30 天内可恢复</div>
            </div>
          </td>
        </tr>
        <tr v-else v-for="row in files" :key="row.file_id"
            :class="{ selected: selectedIds.has(row.file_id) }">
          <td>
            <input type="checkbox"
                   :checked="selectedIds.has(row.file_id)"
                   @change="toggleOne(row.file_id)" />
          </td>
          <td>{{ row.file_name }}</td>
          <td><span class="tag">{{ row.language }}</span></td>
          <td>{{ row.scene || '-' }}</td>
          <td class="text-sm">{{ fmtTime((row as any).deleted_at || row.created_at) }}</td>
          <td>
            <span :class="daysLeft((row as any).deleted_at).cls">
              剩 {{ daysLeft((row as any).deleted_at).days }} 天
            </span>
          </td>
          <td>
            <button class="btn btn-text btn-sm" @click="onRestore(row)">恢复</button>
            <button class="btn btn-text btn-sm" style="color:var(--danger)"
                    @click="onPurge(row)">永久删除</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
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
</style>
