<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage, useDialog } from 'naive-ui'
import { listTasks, cancelTask, deleteTask, retryTask, type TaskListItem } from '@/api/tasks'
import { errorMessage } from '@/api/client'

const router = useRouter()
const message = useMessage()
const dialog = useDialog()

const tasks = ref<TaskListItem[]>([])
const loading = ref(false)
let timer: number | null = null

const STATUS: Record<string, { label: string; cls: string }> = {
  queued:           { label: '排队中',    cls: 'badge-wait' },
  text_generating:  { label: '文本生成中', cls: 'badge-run' },
  synthesizing:     { label: '语音合成中', cls: 'badge-run' },
  succeeded:        { label: '生成成功',  cls: 'badge-ok' },
  failed:           { label: '生成失败',  cls: 'badge-err' },
  cancelled:        { label: '已取消',    cls: 'badge-wait' },
}
const ACTIVE = new Set(['queued', 'text_generating', 'synthesizing'])

async function fetchTasks() {
  loading.value = true
  try { tasks.value = await listTasks() }
  catch (e) { message.error(errorMessage(e)) }
  finally { loading.value = false }
}

const hasActive = computed(() => tasks.value.some((t) => ACTIVE.has(t.status)))

function onCancel(row: TaskListItem) {
  dialog.warning({
    title: '确认取消任务？',
    content: '取消后任务将停止，已生成的内容不会保留。',
    positiveText: '确认', negativeText: '再想想',
    onPositiveClick: async () => {
      try { await cancelTask(row.task_id); message.success('任务已取消'); fetchTasks() }
      catch (e) { message.error(errorMessage(e)) }
    },
  })
}

async function onRetry(row: TaskListItem) {
  try {
    await retryTask(row.task_id)
    message.success('已重新提交，请等待生成')
    fetchTasks()
  } catch (e) { message.error(errorMessage(e)) }
}

function onDelete(row: TaskListItem) {
  dialog.warning({
    title: '确认删除任务记录？',
    content: '已生成的音频文件不受影响。',
    positiveText: '删除', negativeText: '取消',
    onPositiveClick: async () => {
      try { await deleteTask(row.task_id); message.success('已删除'); fetchTasks() }
      catch (e) { message.error(errorMessage(e)) }
    },
  })
}

function gotoDetail(fileId: string) { router.push(`/detail/${fileId}`) }
function fmtTime(s: string | null) { return s ? new Date(s).toLocaleString('zh-CN', { hour12: false }) : '-' }
const langName: Record<string, string> = {
  zh: '中文', en: '英语', ja: '日语', ko: '韩语', es: '西语', fr: '法语',
  de: '德语', pt: '葡语', it: '意语', ru: '俄语', ar: '阿语', id: '印尼语',
}

onMounted(() => {
  fetchTasks()
  timer = window.setInterval(() => { if (hasActive.value) fetchTasks() }, 3000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>

<template>
  <div class="pg-hdr">
    <div>
      <div class="pg-title">生成任务列表</div>
      <div class="pg-sub">查看您提交的生成任务状态与进度</div>
    </div>
    <button class="btn btn-secondary" @click="fetchTasks">🔄 刷新</button>
  </div>

  <div class="table-wrap">
    <table class="table">
      <thead>
        <tr>
          <th>主题</th>
          <th style="width:90px">模式</th>
          <th style="width:70px">语言</th>
          <th style="width:60px">人数</th>
          <th style="width:130px">状态</th>
          <th style="width:80px">进度</th>
          <th style="width:160px">提交时间</th>
          <th>错误</th>
          <th style="width:180px">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading"><td colspan="9" class="empty"><div class="empty-desc">加载中…</div></td></tr>
        <tr v-else-if="tasks.length === 0">
          <td colspan="9">
            <div class="empty">
              <div class="empty-icon">📋</div>
              <div class="empty-title">还没有任务</div>
              <div class="empty-desc">从【全部文件】页右上角【在线生成音频】提交一个任务</div>
            </div>
          </td>
        </tr>
        <tr v-else v-for="row in tasks" :key="row.task_id">
          <td>{{ row.topic || '-' }}</td>
          <td>{{ row.generation_mode === 'llm' ? 'LLM 生成' : '手动输入' }}</td>
          <td>{{ langName[row.language || ''] || row.language || '-' }}</td>
          <td>{{ row.speaker_count ?? '-' }}</td>
          <td>
            <span class="badge" :class="STATUS[row.status]?.cls || 'badge-wait'">
              {{ STATUS[row.status]?.label || row.status }}
            </span>
          </td>
          <td>{{ row.progress }}%</td>
          <td class="text-sm">{{ fmtTime(row.queued_at) }}</td>
          <td class="text-sm" style="color:var(--danger)">
            <span :title="row.error_message || ''">
              {{ row.error_message ? row.error_message.slice(0, 40) + (row.error_message.length > 40 ? '…' : '') : '-' }}
            </span>
          </td>
          <td>
            <div class="row-acts">
              <button v-if="row.status === 'succeeded' && row.file_id"
                      class="btn btn-text btn-sm" @click="gotoDetail(row.file_id!)">查看结果</button>
              <button v-if="row.status === 'failed'"
                      class="btn btn-text btn-sm" @click="onRetry(row)">重新生成</button>
              <button v-if="ACTIVE.has(row.status)" class="btn btn-text btn-sm"
                      style="color:var(--warning)" @click="onCancel(row)">取消</button>
              <button class="btn btn-text btn-sm" style="color:var(--danger)" @click="onDelete(row)">删除</button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
