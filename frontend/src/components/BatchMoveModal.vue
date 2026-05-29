<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { batchMove } from '@/api/files'
import { listFolders, type FolderNode } from '@/api/folders'
import { errorMessage } from '@/api/client'

const props = defineProps<{
  show: boolean
  fileIds: string[]
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
    targetId.value = ''
    try { folders.value = await listFolders() }
    catch (e) { message.error(errorMessage(e)) }
  }
})

async function submit() {
  submitting.value = true
  try {
    await batchMove(props.fileIds, targetId.value || null)
    message.success(`已移动 ${props.fileIds.length} 个文件`)
    emit('moved')
    emit('update:show', false)
  } catch (e) { message.error(errorMessage(e)) }
  finally { submitting.value = false }
}
function close() { emit('update:show', false) }
</script>

<template>
  <div class="mo" :class="{ open: show }" @click.self="close">
    <div class="modal modal-sm">
      <div class="mh">
        <div class="mt">批量移动 {{ fileIds.length }} 个文件</div>
        <button class="mc" @click="close">✕</button>
      </div>
      <div class="mb">
        <div class="form-group">
          <label class="form-label">目标文件夹<span class="req">*</span></label>
          <select v-model="targetId" class="select-field">
            <option v-for="o in options" :key="o.id" :value="o.id">{{ o.label }}</option>
          </select>
        </div>
      </div>
      <div class="mf">
        <button class="btn btn-secondary" @click="close">取消</button>
        <button class="btn btn-primary" :disabled="submitting" @click="submit">
          {{ submitting ? '移动中…' : '确认移动' }}
        </button>
      </div>
    </div>
  </div>
</template>
