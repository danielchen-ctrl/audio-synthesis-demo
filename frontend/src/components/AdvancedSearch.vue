<script setup lang="ts">
import { ref, reactive, watch, onMounted, onUnmounted } from 'vue'
import { useMessage } from 'naive-ui'
import { listLanguages, type Language } from '@/api/meta'
import { errorMessage } from '@/api/client'
import type { ListFilesParams } from '@/api/files'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{
  (e: 'update:open', v: boolean): void
  (e: 'apply', filters: Partial<ListFilesParams>): void
  (e: 'reset'): void
}>()

const message = useMessage()
const languages = ref<Language[]>([])
const panelRef = ref<HTMLElement | null>(null)

const filters = reactive({
  date_from: '',
  date_to: '',
  duration_min: '',
  duration_max: '',
  language: '',
  speaker_count: '',
  scene: '',
  source: '',
  tags: '',
})

async function loadMeta() {
  try {
    languages.value = await listLanguages()
  } catch (e) { message.error(errorMessage(e)) }
}

watch(() => props.open, (v) => { if (v) loadMeta() })

function apply() {
  const out: Partial<ListFilesParams> = {}
  if (filters.date_from) out.date_from = filters.date_from
  if (filters.date_to) out.date_to = filters.date_to
  if (filters.duration_min !== '') out.duration_min = Number(filters.duration_min)
  if (filters.duration_max !== '') out.duration_max = Number(filters.duration_max)
  if (filters.language) out.language = filters.language
  if (filters.speaker_count !== '') out.speaker_count = Number(filters.speaker_count)
  if (filters.scene) out.scene = filters.scene
  if (filters.source) out.source = filters.source
  if (filters.tags.trim()) {
    out.tags = filters.tags.split(/[,，]/).map((s) => s.trim()).filter(Boolean)
  }
  emit('apply', out)
  emit('update:open', false)
}

function reset() {
  Object.assign(filters, {
    date_from: '', date_to: '',
    duration_min: '', duration_max: '',
    language: '', speaker_count: '',
    scene: '', source: '',
    tags: '',
  })
  emit('reset')
  emit('update:open', false)
}

function handleClickOutside(e: MouseEvent) {
  if (!props.open) return
  const target = e.target as HTMLElement
  // 点击触发按钮本身不关闭（由父组件处理）
  if (target.closest('.adv-trigger')) return
  if (panelRef.value && !panelRef.value.contains(target)) {
    emit('update:open', false)
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<template>
  <transition name="adv-panel">
    <div v-if="open" ref="panelRef" class="adv-panel">
      <div class="adv-panel-hd">
        <span class="adv-panel-title">高级搜索</span>
        <button class="mc" @click="$emit('update:open', false)" style="font-size:15px">✕</button>
      </div>

      <div class="adv-panel-body">
        <div class="adv-sec-label">基本信息</div>

        <div class="adv-modal-field">
          <div class="adv-modal-label">
            上传时间范围
            <button v-if="filters.date_from || filters.date_to"
                    class="field-clear" title="清除日期"
                    @click.stop="filters.date_from = ''; filters.date_to = ''">清除</button>
          </div>
          <div class="adv-date-range">
            <div class="input-with-clear">
              <input v-model="filters.date_from" class="input-field" type="date" />
              <span v-if="filters.date_from" class="inline-clear"
                    @click.stop="filters.date_from = ''" title="清除">×</span>
            </div>
            <span class="adv-date-sep">至</span>
            <div class="input-with-clear">
              <input v-model="filters.date_to" class="input-field" type="date" />
              <span v-if="filters.date_to" class="inline-clear"
                    @click.stop="filters.date_to = ''" title="清除">×</span>
            </div>
          </div>
        </div>

        <div class="adv-modal-field">
          <div class="adv-modal-label">
            时长（秒）
            <button v-if="filters.duration_min !== '' || filters.duration_max !== ''"
                    class="field-clear" title="清除时长"
                    @click.stop="filters.duration_min = ''; filters.duration_max = ''">清除</button>
          </div>
          <div class="adv-date-range">
            <div class="input-with-clear">
              <input v-model="filters.duration_min" class="input-field"
                     type="number" min="0" placeholder="最短（秒）" />
              <span v-if="filters.duration_min !== ''" class="inline-clear"
                    @click.stop="filters.duration_min = ''" title="清除">×</span>
            </div>
            <span class="adv-date-sep">至</span>
            <div class="input-with-clear">
              <input v-model="filters.duration_max" class="input-field"
                     type="number" min="0" placeholder="最长（秒）" />
              <span v-if="filters.duration_max !== ''" class="inline-clear"
                    @click.stop="filters.duration_max = ''" title="清除">×</span>
            </div>
          </div>
        </div>

        <div class="adv-modal-field">
          <div class="adv-modal-label">语言</div>
          <select v-model="filters.language" class="select-field">
            <option value="">不限</option>
            <option v-for="l in languages" :key="l.code" :value="l.code">{{ l.name }}</option>
          </select>
        </div>

        <div class="adv-sec-label">语料属性</div>

        <div class="adv-modal-field">
          <div class="adv-modal-label">场景类别</div>
          <select v-model="filters.scene" class="select-field">
            <option value="">不限</option>
            <option value="meeting">会议讨论</option>
            <option value="interview">访谈</option>
            <option value="medical">问诊</option>
            <option value="custom">自定义</option>
            <option value="other">其他</option>
          </select>
        </div>

        <div class="adv-modal-field">
          <div class="adv-modal-label">来源</div>
          <select v-model="filters.source" class="select-field">
            <option value="">不限</option>
            <option value="generated">在线生成</option>
            <option value="uploaded">用户上传</option>
          </select>
        </div>

        <div class="adv-modal-field">
          <div class="adv-modal-label">说话人数</div>
          <select v-model="filters.speaker_count" class="select-field">
            <option value="">不限</option>
            <option value="1">1 人</option>
            <option value="2">2 人</option>
            <option value="3">3 人</option>
            <option value="4">4 人</option>
            <option value="5">5 人以上</option>
          </select>
        </div>

        <div class="adv-modal-field">
          <div class="adv-modal-label">标签</div>
          <input v-model="filters.tags" class="input-field"
                 placeholder="输入标签关键词…" />
          <div class="form-hint">逗号分隔多个标签（AND 关系）</div>
        </div>
      </div>

      <div class="adv-panel-ft">
        <button class="btn btn-secondary btn-sm" @click="reset">清除全部筛选</button>
        <button class="btn btn-primary btn-sm" @click="apply">应用筛选</button>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.adv-panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 460px;
  max-height: 80vh;
  background: var(--clarity-white);
  border-radius: var(--r-lg);
  box-shadow: 0 8px 32px rgba(65, 61, 59, .12), 0 2px 8px rgba(65, 61, 59, .08);
  border: 1px solid var(--gray-200);
  z-index: 150;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.adv-panel-hd {
  padding: 14px 18px 12px;
  border-bottom: 1px solid var(--gray-200);
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
}
.adv-panel-title { font-size: 15px; font-weight: 600; color: var(--gray-900); }
.adv-panel-body { padding: 20px 20px 8px; overflow-y: auto; flex: 1; }
.adv-panel-ft {
  padding: 12px 18px;
  border-top: 1px solid var(--gray-200);
  display: flex; justify-content: flex-end; gap: 8px;
  flex-shrink: 0;
}
.adv-sec-label {
  font-size: 12px; color: var(--gray-400); font-weight: 500;
  margin: 18px 0 12px; letter-spacing: .2px;
}
.adv-sec-label:first-child { margin-top: 0; }
.adv-modal-field { margin-bottom: 14px; }
.adv-modal-field:last-child { margin-bottom: 4px; }
.adv-modal-label {
  font-size: 13px; font-weight: 500; color: var(--gray-900); margin-bottom: 6px;
  display: flex; align-items: center; justify-content: space-between;
}
.field-clear {
  background: none; border: none; padding: 0;
  color: var(--gray-400); font-size: 11px; cursor: pointer;
  font-weight: 400;
}
.field-clear:hover { color: var(--danger); }

.adv-date-range { display: flex; align-items: center; gap: 10px; }
.adv-date-range .input-with-clear { flex: 1; }
.input-with-clear {
  position: relative;
}
.input-with-clear .input-field { width: 100%; padding-right: 28px; }
.inline-clear {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  width: 18px; height: 18px;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 50%;
  background: var(--gray-200);
  color: var(--gray-500);
  font-size: 13px; line-height: 1;
  cursor: pointer;
  transition: all .12s;
  user-select: none;
}
.inline-clear:hover {
  background: var(--danger);
  color: white;
}
.adv-date-sep { font-size: 13px; color: var(--gray-400); flex-shrink: 0; }

/* 展开/收起动画 */
.adv-panel-enter-active, .adv-panel-leave-active {
  transition: opacity .15s, transform .15s;
}
.adv-panel-enter-from, .adv-panel-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
