<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMessage, useDialog } from 'naive-ui'
import { useAuthStore } from '@/stores/auth'
import { useFolderStore, type FolderSelection } from '@/stores/folders'
import { errorMessage } from '@/api/client'
import type { FolderNode } from '@/api/folders'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const folderStore = useFolderStore()
const message = useMessage()
const dialog = useDialog()

const dropdownOpen = ref(false)
const myFolderCollapsed = ref(false)  // 我的文件夹树是否折叠
const userInitial = computed(() => auth.user?.username.charAt(0).toUpperCase() || 'U')
const userName = computed(() => auth.user?.display_name || auth.user?.username || '')

// 路由是否在「我的文件」（决定要不要在侧栏渲染文件夹树）
const inMyAudio = computed(() => route.path.startsWith('/myaudio'))

function handleMyAudioClick() {
  // 已在 /myaudio 时再次点击 → 切换折叠；否则导航过去并展开
  if (inMyAudio.value) {
    myFolderCollapsed.value = !myFolderCollapsed.value
  } else {
    myFolderCollapsed.value = false
    selectFolder('__all__')
    go('/myaudio')
  }
}

// 当路由切到 /myaudio 时第一次加载文件夹
onMounted(() => {
  if (inMyAudio.value && !folderStore.loaded) folderStore.load()
  document.addEventListener('click', closeDropdownOnClickOutside)
})
onUnmounted(() => document.removeEventListener('click', closeDropdownOnClickOutside))

function toggleDropdown() { dropdownOpen.value = !dropdownOpen.value }
function closeDropdownOnClickOutside(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('.nb-user')) dropdownOpen.value = false
}
function logout() { auth.logout(); router.push('/login') }
function go(path: string) {
  router.push(path)
  if (path.startsWith('/myaudio') && !folderStore.loaded) folderStore.load()
  dropdownOpen.value = false
}
const isActive = (path: string) => computed(() => route.path === path)

// ===== 文件夹操作 =====
function selectFolder(sel: FolderSelection) {
  folderStore.select(sel)
  // 如果不在 /myaudio 页，切过去
  if (!inMyAudio.value) router.push('/myaudio')
}

// 新建文件夹 modal
const showNew = ref(false)
const newName = ref('')
const newParent = ref<string | null>(null)
function openNew(parentId: string | null = null) {
  newName.value = ''
  newParent.value = parentId
  showNew.value = true
}

// 扁平化为 select option（用于新建 modal 选父）
const folderOptions = computed(() => {
  const out = [{ id: '', label: '我的文件（根目录）', depth: 0 }]
  for (const n of flatFolders.value) {
    // 第 3 层（depth=2）不能再有子，建文件夹时不显示为父
    if (n.depth >= 2) continue
    out.push({ id: n.folder_id, label: '— '.repeat(n._depth + 1) + n.name, depth: n._depth })
  }
  return out
})
async function submitNew() {
  if (!newName.value.trim()) { message.warning('请输入文件夹名'); return }
  try {
    await folderStore.create(newName.value.trim(), newParent.value)
    showNew.value = false
    message.success('已创建')
  } catch (e) { message.error(errorMessage(e)) }
}

// 重命名 modal
const showRename = ref(false)
const renameName = ref('')
const renameTarget = ref<FolderNode | null>(null)
function openRename(node: FolderNode) {
  renameName.value = node.name
  renameTarget.value = node
  showRename.value = true
}
async function submitRename() {
  if (!renameTarget.value || !renameName.value.trim()) return
  try {
    await folderStore.rename(renameTarget.value.folder_id, renameName.value.trim())
    showRename.value = false
    message.success('已重命名')
  } catch (e) { message.error(errorMessage(e)) }
}

// 删除文件夹
function confirmDelete(node: FolderNode) {
  dialog.warning({
    title: `删除文件夹「${node.name}」?`,
    content: '文件夹内的文件也会被移入回收站，可在 30 天内还原。',
    positiveText: '确认删除', negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await folderStore.remove(node.folder_id)
        message.success('已删除')
      } catch (e) { message.error(errorMessage(e)) }
    },
  })
}

// 扁平化树（深度数字用于缩进）
function flatTree(nodes: FolderNode[], depth = 0): Array<FolderNode & { _depth: number }> {
  const out: Array<FolderNode & { _depth: number }> = []
  for (const n of nodes) {
    out.push({ ...n, _depth: depth })
    if (n.children?.length) out.push(...flatTree(n.children, depth + 1))
  }
  return out
}
const flatFolders = computed(() => flatTree(folderStore.folders))

// ===== 复制分享链接 =====
const shareTooltip = ref('')
async function copyShareLink() {
  let url = window.location.origin
  // 如果当前是 localhost，尝试从后端拿局域网 IP
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    try {
      const resp = await fetch('/api/v1/admin/server-info', {
        headers: { Authorization: `Bearer ${auth.token}` },
      })
      if (resp.ok) {
        const data = await resp.json()
        if (data.lan_ips?.length) {
          url = `http://${data.lan_ips[0]}:${window.location.port || data.frontend_port}`
        }
      }
    } catch { /* 失败则用当前 origin */ }
  }
  try {
    await navigator.clipboard.writeText(url)
    shareTooltip.value = '已复制 ✓'
    message.success(`分享链接已复制：${url}`)
  } catch {
    // 兜底：prompt
    window.prompt('复制此分享链接：', url)
  }
  setTimeout(() => { shareTooltip.value = '' }, 2000)
}
</script>

<template>
  <div class="app-shell">
    <nav class="navbar">
      <div class="logo">
        <div class="logo-icon">
          <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M4 36 L14 10 Q20 5 26 10 L36 36"
                  stroke="black" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
            <circle cx="20" cy="26" r="3.2" fill="black"/>
          </svg>
        </div>
        <span class="logo-text">PLAUD</span>
        <span class="logo-sub">音频语料平台</span>
      </div>
      <div class="nb-space"></div>
      <div class="nb-user" @click.stop="toggleDropdown">
        <div class="avatar">{{ userInitial }}</div>
        <span>{{ userName }}</span> ▾
        <div class="ud" :class="{ open: dropdownOpen }">
          <div class="ud-item" @click="logout">退出登录</div>
        </div>
      </div>
    </nav>

    <div class="layout">
      <aside class="sidebar">
        <div class="sb-label">浏览</div>
        <div class="sb-item" :class="{ active: isActive('/home').value }" @click="go('/home')">
          <span>🌐</span> 全部文件
        </div>
        <div class="sb-item my-folder-row"
             :class="{ active: inMyAudio && folderStore.selected === '__all__' }"
             @click="handleMyAudioClick">
          <span>📁</span>
          <span class="sb-folder-name">我的文件</span>
          <span v-if="inMyAudio" class="sb-chevron"
                :class="{ collapsed: myFolderCollapsed }">▾</span>
        </div>

        <!-- 文件夹子树：仅在 /myaudio 路由下且未折叠时展开 -->
        <template v-if="inMyAudio && !myFolderCollapsed">
          <div class="sb-item folder-item"
               :class="{ active: folderStore.selected === null }"
               style="padding-left:24px"
               @click="selectFolder(null)">
            <span>📂</span>
            <span class="sb-folder-name">默认目录</span>
          </div>

          <div v-for="node in flatFolders" :key="node.folder_id"
               class="sb-item folder-item"
               :class="{ active: folderStore.selected === node.folder_id }"
               :style="{ paddingLeft: (24 + node._depth * 14) + 'px' }"
               @click="selectFolder(node.folder_id)">
            <span>📂</span>
            <span class="sb-folder-name">{{ node.name }}</span>
            <span v-if="node.file_count > 0" class="folder-count">{{ node.file_count }}</span>
            <button class="sb-rename-btn" title="重命名"
                    @click.stop="openRename(node)">✏</button>
            <button class="sb-del-btn" title="删除"
                    @click.stop="confirmDelete(node)">🗑</button>
          </div>

          <div class="sb-add" @click="openNew()">＋ 新建文件夹</div>
        </template>

        <div class="sb-sep"></div>
        <div class="sb-label">快捷</div>
        <div class="sb-item" :class="{ active: isActive('/tasks').value }" @click="go('/tasks')">
          <span>📋</span> 生成任务列表
        </div>
        <div class="sb-item" :class="{ active: isActive('/trash').value }" @click="go('/trash')">
          <span>🗑</span> 回收站
        </div>

        <!-- 分享链接 -->
        <div class="sb-share" @click="copyShareLink" :title="shareTooltip || '复制局域网访问链接，分享给同事'">
          <span>🔗</span>
          <span>{{ shareTooltip || '复制分享链接' }}</span>
        </div>
      </aside>

      <main class="content-area">
        <router-view />
      </main>
    </div>
  </div>

  <!-- 新建文件夹 Modal -->
  <div class="mo" :class="{ open: showNew }" @click.self="showNew = false">
    <div class="modal modal-sm">
      <div class="mh"><div class="mt">新建文件夹</div>
        <button class="mc" @click="showNew = false">✕</button></div>
      <div class="mb">
        <div class="form-group">
          <label class="form-label">所属位置</label>
          <select v-model="newParent" class="select-field">
            <option v-for="o in folderOptions" :key="o.id || 'root'"
                    :value="o.id || null">{{ o.label }}</option>
          </select>
          <div class="form-hint">最多支持 3 层嵌套</div>
        </div>
        <div class="form-group">
          <label class="form-label">文件夹名称<span class="req">*</span></label>
          <input v-model="newName" class="input-field" maxlength="255"
                 @keyup.enter="submitNew" />
          <div class="form-hint">最长 255 字符，同级目录不允许重名</div>
        </div>
      </div>
      <div class="mf">
        <button class="btn btn-secondary" @click="showNew = false">取消</button>
        <button class="btn btn-primary" @click="submitNew">创建</button>
      </div>
    </div>
  </div>

  <!-- 重命名 Modal -->
  <div class="mo" :class="{ open: showRename }" @click.self="showRename = false">
    <div class="modal modal-sm">
      <div class="mh"><div class="mt">重命名文件夹</div>
        <button class="mc" @click="showRename = false">✕</button></div>
      <div class="mb">
        <div class="form-group">
          <label class="form-label">文件夹名称<span class="req">*</span></label>
          <input v-model="renameName" class="input-field" maxlength="255"
                 @keyup.enter="submitRename" />
        </div>
      </div>
      <div class="mf">
        <button class="btn btn-secondary" @click="showRename = false">取消</button>
        <button class="btn btn-primary" @click="submitRename">确认重命名</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
}
.sb-folder-name {
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-size: 12px;
}
.folder-count {
  font-size: 10px; color: var(--gray-400);
  background: var(--gray-100); padding: 0 6px; border-radius: var(--r-pill);
  font-weight: 500;
}
.sb-rename-btn, .sb-del-btn {
  opacity: 0; flex-shrink: 0;
  width: 18px; height: 18px; padding: 0;
  display: inline-flex; align-items: center; justify-content: center;
  border-radius: 3px; background: none; color: var(--gray-400);
  font-size: 10px; cursor: pointer; border: none; line-height: 1;
  transition: opacity .12s;
}
.sb-item:hover .sb-rename-btn,
.sb-item:hover .sb-del-btn { opacity: 1; }
.sb-rename-btn:hover { background: var(--gray-200); color: var(--dark-warm-grey); }
.sb-del-btn:hover { background: #FEE2E2; color: #DC2626; }
.sb-add {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 10px; padding-left: 24px;
  color: var(--gray-500); font-size: 12px; cursor: pointer;
  border-radius: var(--r-sm);
}
.sb-add:hover { background: var(--gray-100); color: var(--dark-warm-grey); }

.my-folder-row { user-select: none; }
.sb-chevron {
  margin-left: auto;
  font-size: 11px;
  color: var(--gray-400);
  transition: transform .15s;
}
.sb-chevron.collapsed { transform: rotate(-90deg); }

.sb-share {
  display: flex; align-items: center; gap: 8px;
  margin: 8px 10px 12px;
  padding: 8px 10px;
  border-radius: var(--r-sm);
  border: 1px dashed var(--gray-300);
  color: var(--gray-500);
  font-size: 12px;
  cursor: pointer;
  transition: background .15s, color .15s, border-color .15s;
  user-select: none;
}
.sb-share:hover {
  background: var(--gray-100);
  color: var(--primary, #3B82F6);
  border-color: var(--primary, #3B82F6);
}
</style>
