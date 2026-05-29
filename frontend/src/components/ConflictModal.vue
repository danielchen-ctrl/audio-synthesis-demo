<script setup lang="ts">
import { ref } from 'vue'
import type { ConflictStrategy } from '@/api/folders'

defineProps<{
  show: boolean
  fileName: string
  targetLabel: string  // 目标文件夹显示名
}>()
const emit = defineEmits<{
  (e: 'update:show', v: boolean): void
  (e: 'choose', strategy: ConflictStrategy): void
}>()

const chosen = ref<ConflictStrategy>('keep_both')

function confirm() {
  emit('choose', chosen.value)
  emit('update:show', false)
}
function close() { emit('update:show', false) }
</script>

<template>
  <div class="mo" :class="{ open: show }" @click.self="close">
    <div class="modal modal-sm">
      <div class="mh">
        <div class="mt">目标位置存在同名文件</div>
        <button class="mc" @click="close">✕</button>
      </div>
      <div class="mb">
        <div style="background:var(--gray-50);border:1px solid var(--gray-200);
                    border-radius:var(--r-sm);padding:9px 13px;
                    font-size:13px;color:var(--gray-700);margin-bottom:12px">
          📄 {{ fileName }}
        </div>
        <p style="font-size:13px;color:var(--gray-700);margin-bottom:14px">
          目标位置「<strong>{{ targetLabel }}</strong>」中已存在同名文件，请选择处理方式：
        </p>
        <div style="display:flex;flex-direction:column;gap:8px">
          <label class="ro" :class="{ sel: chosen === 'overwrite' }">
            <input type="radio" v-model="chosen" value="overwrite" />
            <div>
              <div class="ro-label">覆盖文件</div>
              <div class="ro-desc">原文件将被移入回收站（30 天内可恢复）</div>
            </div>
          </label>
          <label class="ro" :class="{ sel: chosen === 'keep_both' }">
            <input type="radio" v-model="chosen" value="keep_both" />
            <div>
              <div class="ro-label">保留两个文件</div>
              <div class="ro-desc">系统自动在文件名后添加 (1) 进行区分</div>
            </div>
          </label>
        </div>
      </div>
      <div class="mf">
        <button class="btn btn-secondary" @click="close">取消</button>
        <button class="btn btn-primary" @click="confirm">确定</button>
      </div>
    </div>
  </div>
</template>
