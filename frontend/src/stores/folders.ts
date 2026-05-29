import { defineStore } from 'pinia'
import {
  listFolders, createFolder, renameFolder, deleteFolder,
  type FolderNode,
} from '@/api/folders'

// __all__  = 显示所有自己的文件（默认）
// null    = 显示根目录（folder_id IS NULL 的文件）
// <uuid>  = 具体某个文件夹
export type FolderSelection = '__all__' | null | string

export const useFolderStore = defineStore('folders', {
  state: () => ({
    folders: [] as FolderNode[],
    selected: '__all__' as FolderSelection,
    loaded: false,
  }),
  getters: {
    /** 给定 folder_id 返回 [祖先..., 自己] 名字链 */
    pathOf: (state) => (folderId: string | null): string[] => {
      if (!folderId) return []
      const idToNode = new Map<string, FolderNode>()
      const walk = (nodes: FolderNode[]) => {
        for (const n of nodes) {
          idToNode.set(n.folder_id, n)
          walk(n.children)
        }
      }
      walk(state.folders)
      const chain: string[] = []
      let cur = idToNode.get(folderId)
      while (cur) {
        chain.unshift(cur.name)
        cur = cur.parent_id ? idToNode.get(cur.parent_id) : undefined
      }
      return chain
    },
  },
  actions: {
    async load() {
      this.folders = await listFolders()
      this.loaded = true
    },
    select(sel: FolderSelection) {
      this.selected = sel
    },
    async create(name: string, parent_id: string | null) {
      await createFolder(name, parent_id)
      await this.load()
    },
    async rename(folder_id: string, name: string) {
      await renameFolder(folder_id, name)
      await this.load()
    },
    async remove(folder_id: string) {
      await deleteFolder(folder_id)
      if (this.selected === folder_id) this.selected = '__all__'
      await this.load()
    },
  },
})
