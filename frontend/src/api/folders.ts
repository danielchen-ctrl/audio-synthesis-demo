import client from './client'

export interface FolderNode {
  folder_id: string
  user_id: string
  parent_id: string | null
  name: string
  depth: number
  created_at: string
  children: FolderNode[]
  file_count: number
}

export interface Folder {
  folder_id: string
  user_id: string
  parent_id: string | null
  name: string
  depth: number
  created_at: string
}

export async function listFolders(): Promise<FolderNode[]> {
  const resp = await client.get('/folders')
  return resp.data
}

export async function createFolder(name: string, parent_id?: string | null): Promise<Folder> {
  const resp = await client.post('/folders', { name, parent_id: parent_id ?? null })
  return resp.data
}

export async function renameFolder(folder_id: string, name: string): Promise<Folder> {
  const resp = await client.patch(`/folders/${folder_id}`, { name })
  return resp.data
}

export async function deleteFolder(folder_id: string): Promise<void> {
  await client.delete(`/folders/${folder_id}`)
}

export type ConflictStrategy = 'ask' | 'overwrite' | 'keep_both'

export async function moveFile(
  file_id: string,
  folder_id: string | null,
  conflict_strategy: ConflictStrategy = 'ask',
): Promise<void> {
  await client.post(`/files/${file_id}/move`, { folder_id, conflict_strategy })
}
