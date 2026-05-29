<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { getDownloadUrl } from '@/api/files'
import { errorMessage } from '@/api/client'
import { useMessage } from 'naive-ui'

const props = defineProps<{
  fileId: string
  fileName: string
}>()
const emit = defineEmits<{ (e: 'close'): void }>()

const message = useMessage()
const audioRef = ref<HTMLAudioElement | null>(null)
const downloadUrl = ref('')
const playing = ref(false)
const currentTime = ref(0)
const totalTime = ref(0)
const loading = ref(true)

watch(() => props.fileId, async () => {
  loading.value = true
  try {
    const dl = await getDownloadUrl(props.fileId)
    downloadUrl.value = dl.download_url
    // 自动播放
    setTimeout(() => audioRef.value?.play(), 100)
  } catch (e) {
    message.error(errorMessage(e))
  } finally {
    loading.value = false
  }
}, { immediate: true })

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

onUnmounted(() => { if (audioRef.value) audioRef.value.pause() })
</script>

<template>
  <div class="mini-player">
    <button class="mini-play" @click="togglePlay" :title="playing ? '暂停' : '播放'">
      {{ playing ? '⏸' : '▶' }}
    </button>
    <div class="mini-info">{{ fileName }}</div>
    <div class="mini-prog" @click="seek">
      <div class="mini-prog-fill"
           :style="{ width: totalTime ? (currentTime / totalTime * 100) + '%' : '0%' }"></div>
    </div>
    <div class="mini-time">
      {{ fmtMS(currentTime) }} / {{ fmtMS(totalTime) }}
    </div>
    <button class="mini-close" @click="emit('close')">× 关闭</button>
    <audio ref="audioRef" :src="downloadUrl"
           @play="playing = true" @pause="playing = false"
           @timeupdate="onTimeUpdate" @loadedmetadata="onTimeUpdate"></audio>
  </div>
</template>

<style scoped>
.mini-player {
  background: var(--deep-black);
  color: #fff;
  border-radius: var(--r-md);
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  margin: 4px 0;
}
.mini-play {
  width: 28px; height: 28px;
  background: var(--amplify-green);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; flex-shrink: 0; border: none;
  font-size: 11px; color: var(--deep-black);
  transition: opacity .12s;
}
.mini-play:hover { opacity: .85; }
.mini-info {
  font-weight: 500;
  max-width: 280px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  flex-shrink: 0;
}
.mini-prog {
  flex: 1;
  height: 4px;
  background: rgba(255, 255, 255, .15);
  border-radius: 2px;
  cursor: pointer;
  position: relative;
}
.mini-prog-fill {
  height: 100%;
  background: var(--amplify-green);
  border-radius: 2px;
  transition: width .1s linear;
}
.mini-time {
  font-size: 11px;
  color: rgba(255, 255, 255, .7);
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.mini-close {
  background: none;
  color: rgba(255, 255, 255, .7);
  font-size: 12px;
  cursor: pointer;
  border: none;
  padding: 2px 6px;
  border-radius: 3px;
  flex-shrink: 0;
  transition: all .12s;
}
.mini-close:hover {
  background: rgba(255, 255, 255, .1);
  color: #fff;
}
</style>
