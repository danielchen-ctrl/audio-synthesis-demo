<script setup lang="ts">
import { computed } from 'vue'
import type { ListFilesParams } from '@/api/files'

const props = defineProps<{
  filters: Partial<ListFilesParams>
}>()
const emit = defineEmits<{
  (e: 'remove', keys: string[]): void   // 一次性删一个或一组（日期/时长是一对）
  (e: 'clear'): void
}>()

const LANG_NAMES: Record<string, string> = {
  zh: '中文', en: '英语', ja: '日语', ko: '韩语', es: '西班牙语', fr: '法语',
  de: '德语', pt: '葡萄牙语', it: '意大利语', ru: '俄语', ar: '阿拉伯语', id: '印度尼西亚语',
}
const SCENE_NAMES: Record<string, string> = {
  meeting: '会议讨论', interview: '访谈', medical: '问诊',
  custom: '自定义', other: '其他',
}
const SOURCE_NAMES: Record<string, string> = {
  generated: '在线生成', uploaded: '用户上传',
}

interface Chip {
  label: string
  value: string
  keys: string[]
}

const chips = computed<Chip[]>(() => {
  const f = props.filters
  const out: Chip[] = []

  // 日期范围（两个字段合并显示）
  if (f.date_from || f.date_to) {
    const from = f.date_from || '不限'
    const to = f.date_to || '不限'
    out.push({ label: '上传时间', value: `${from} → ${to}`, keys: ['date_from', 'date_to'] })
  }
  // 时长范围
  if (f.duration_min != null || f.duration_max != null) {
    const dmin = f.duration_min != null ? `${f.duration_min}s` : '不限'
    const dmax = f.duration_max != null ? `${f.duration_max}s` : '不限'
    out.push({ label: '时长', value: `${dmin} → ${dmax}`, keys: ['duration_min', 'duration_max'] })
  }
  if (f.language) {
    out.push({ label: '语言', value: LANG_NAMES[f.language] || f.language, keys: ['language'] })
  }
  if (f.speaker_count != null) {
    out.push({ label: '人数', value: `${f.speaker_count} 人`, keys: ['speaker_count'] })
  }
  if (f.scene) {
    out.push({ label: '场景', value: SCENE_NAMES[f.scene] || f.scene, keys: ['scene'] })
  }
  if (f.source) {
    out.push({ label: '来源', value: SOURCE_NAMES[f.source] || f.source, keys: ['source'] })
  }
  if (f.tags && f.tags.length > 0) {
    out.push({ label: '标签', value: f.tags.join(' + '), keys: ['tags'] })
  }
  return out
})
</script>

<template>
  <div v-if="chips.length > 0" class="chip-bar">
    <span class="chip-bar-label">当前筛选：</span>
    <span v-for="c in chips" :key="c.keys.join(',')" class="filter-chip">
      <span class="chip-key">{{ c.label }}</span>
      <span class="chip-sep">·</span>
      <span class="chip-val">{{ c.value }}</span>
      <span class="chip-x" @click="emit('remove', c.keys)" title="移除该条件">×</span>
    </span>
    <button class="chip-clear" @click="emit('clear')">清除全部</button>
  </div>
</template>

<style scoped>
.chip-bar {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
  padding: 8px 12px;
  background: #FAFAF7;
  border: 1px solid var(--gray-200);
  border-radius: var(--r-md);
  margin-bottom: 12px;
}
.chip-bar-label {
  font-size: 12px; color: var(--gray-500); font-weight: 500;
  margin-right: 2px;
}
.filter-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 4px 3px 10px;
  background: var(--clarity-white);
  border: 1px solid var(--gray-300);
  border-radius: var(--r-pill);
  font-size: 12px;
  color: var(--gray-700);
  transition: border-color .12s;
}
.filter-chip:hover { border-color: var(--gray-400); }
.chip-key { color: var(--gray-500); font-weight: 500; }
.chip-sep { color: var(--gray-300); }
.chip-val { color: var(--gray-900); font-weight: 500; }
.chip-x {
  display: inline-flex; align-items: center; justify-content: center;
  width: 18px; height: 18px;
  border-radius: 50%;
  color: var(--gray-400);
  cursor: pointer;
  font-size: 14px; line-height: 1;
  margin-left: 2px;
  transition: all .12s;
}
.chip-x:hover {
  background: #FEE2E2;
  color: var(--danger);
}
.chip-clear {
  margin-left: 4px;
  background: none;
  color: var(--gray-500);
  font-size: 12px;
  cursor: pointer;
  border: none;
  padding: 3px 8px;
  border-radius: var(--r-sm);
  transition: all .12s;
}
.chip-clear:hover {
  color: var(--danger);
  background: var(--danger-light);
}
</style>
