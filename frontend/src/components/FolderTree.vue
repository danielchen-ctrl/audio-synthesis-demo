<script setup lang="ts">
import { computed } from 'vue'
import type { FolderNode } from '@/api/folders'

const props = defineProps<{
  folders: FolderNode[]
  selectedId: string | null   // null = 根目录
}>()
const emit = defineEmits<{
  (e: 'select', id: string | null): void
  (e: 'rename', node: FolderNode): void
  (e: 'delete', node: FolderNode): void
  (e: 'newChild', parentId: string | null): void
}>()

function flat(nodes: FolderNode[], depth = 0): Array<FolderNode & { _depth: number }> {
  const out: Array<FolderNode & { _depth: number }> = []
  for (const n of nodes) {
    out.push({ ...n, _depth: depth })
    if (n.children?.length) out.push(...flat(n.children, depth + 1))
  }
  return out
}

const flatList = computed(() => flat(props.folders))
</script>

<template>
  <div class="folder-tree">
    <!-- 根目录 -->
    <div class="sb-item" :class="{ active: selectedId === null }"
         @click="emit('select', null)">
      <span>📁</span>
      <span class="sb-folder-name">我的文件（根目录）</span>
      <button class="sb-rename-btn" title="新建文件夹"
              @click.stop="emit('newChild', null)">+</button>
    </div>

    <!-- 树节点（扁平化展示，靠 padding 视觉缩进）-->
    <div v-for="node in flatList" :key="node.folder_id"
         class="sb-item"
         :class="{ active: selectedId === node.folder_id }"
         :style="{ paddingLeft: (10 + node._depth * 14) + 'px' }"
         @click="emit('select', node.folder_id)">
      <span>📁</span>
      <span class="sb-folder-name">{{ node.name }}</span>
      <span v-if="node.file_count > 0" class="folder-count">{{ node.file_count }}</span>
      <button v-if="node.depth < 2" class="sb-rename-btn"
              title="新建子文件夹"
              @click.stop="emit('newChild', node.folder_id)">+</button>
      <button class="sb-rename-btn" title="重命名"
              @click.stop="emit('rename', node)">✏</button>
      <button class="sb-del-btn" title="删除"
              @click.stop="emit('delete', node)">🗑</button>
    </div>
  </div>
</template>

<style scoped>
.folder-tree {
  display: flex;
  flex-direction: column;
}
.sb-rename-btn, .sb-del-btn {
  opacity: 0; flex-shrink: 0;
  width: 18px; height: 18px; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 3px; background: none; color: var(--gray-400);
  font-size: 11px; cursor: pointer; border: none; line-height: 1;
  transition: opacity .12s;
}
.sb-item:hover .sb-rename-btn,
.sb-item:hover .sb-del-btn { opacity: 1; }
.sb-rename-btn:hover { background: var(--gray-200); color: var(--dark-warm-grey); }
.sb-del-btn:hover { background: #FEE2E2; color: #DC2626; }
.sb-folder-name {
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.folder-count {
  font-size: 10px; color: var(--gray-400);
  background: var(--gray-100); padding: 0 6px; border-radius: var(--r-pill);
  font-weight: 500;
}
</style>
