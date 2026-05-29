<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import axios from 'axios'
import { listFolders, moveFile, type ConflictStrategy, type FolderNode } from '@/api/folders'
import { errorMessage } from '@/api/client'
import ConflictModal from '@/components/ConflictModal.vue'

const props = defineProps<{
  show: boolean
  fileId: string
  fileName: string
  currentFolderId: string | null
}>()
const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
  (e: 'moved'): void
}>()

const message = useMessage()
const submitting = ref(false)
const targetId = ref<string>('')   // '' = 根目录
const folders = ref<FolderNode[]>([])

function flatten(nodes: FolderNode[], prefix = ''): Array<{ id: string; label: string }> {
  const out: Array<{ id: string; label: string }> = []
  for (const n of nodes) {
    const label = prefix ? `${prefix} / ${n.name}` : n.name
    out.push({ id: n.folder_id, label })
    if (n.children?.length) out.push(...flatten(n.children, label))
  }
  return out
}

const options = computed(() => [
  { id: '', label: '我的文件（根目录）' },
  ...flatten(folders.value),
])

watch(() => props.show, async (v) => {
  if (v) {
    targetId.value = props.currentFolderId ?? ''
    try { folders.value = await listFolders() }
    catch (e) { message.error(errorMessage(e)) }
  }
})

// 同名冲突状态
const showConflict = ref(false)
const conflictTargetLabel = ref('')

async function submit(strategy: ConflictStrategy = 'ask') {
  submitting.value = true
  try {
    await moveFile(props.fileId, targetId.value || null, strategy)
    message.success('已移动')
    emit('moved')
    emit('update:show', false)
  } catch (e) {
    // 409 = 同名冲突
    if (axios.isAxiosError(e) && e.response?.status === 409) {
      const detail = e.response.data?.detail
      if (detail && typeof detail === 'object' && detail.conflict) {
        conflictTargetLabel.value =
          options.value.find((o) => o.id === targetId.value)?.label || '目标文件夹'
        showConflict.value = true
        return
      }
    }
    message.error(errorMessage(e))
  } finally { submitting.value = false }
}

function onConflictChoose(strategy: ConflictStrategy) {
  submit(strategy)
}
function close() { emit('update:show', false) }
</script>

<template>
  <div class="mo" :class="{ open: show }" @click.self="close">
    <div class="modal modal-sm">
      <div class="mh">
        <div class="mt">移动文件</div>
        <button class="mc" @click="close">✕</button>
      </div>
      <div class="mb">
        <div style="margin-bottom:14px;padding:9px 13px;background:var(--gray-50);
             border:1px solid var(--gray-200);border-radius:var(--r-sm);
             font-size:13px;color:var(--gray-700)">
          📄 {{ fileName }}
        </div>
        <div class="form-group">
          <label class="form-label">目标文件夹<span class="req">*</span></label>
          <select v-model="targetId" class="select-field">
            <option v-for="o in options" :key="o.id" :value="o.id">{{ o.label }}</option>
          </select>
        </div>
      </div>
      <div class="mf">
        <button class="btn btn-secondary" @click="close">取消</button>
        <button class="btn btn-primary" :disabled="submitting" @click="submit()">
          {{ submitting ? '移动中…' : '确认移动' }}
        </button>
      </div>
    </div>
  </div>

  <ConflictModal
    v-model:show="showConflict"
    :file-name="fileName"
    :target-label="conflictTargetLabel"
    @choose="onConflictChoose"
  />
</template>
