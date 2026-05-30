import client from './client'

export interface Tag {
  tag_id: string
  name: string
}

export interface AudioFile {
  file_id: string
  user_id: string
  file_name: string
  file_size: number
  duration_sec: number | null
  format: string | null
  language: string
  speaker_count: number
  scene: string
  topic: string | null
  source: string
  created_at: string
  folder_id: string | null
  tags: Tag[]
  has_transcript: boolean
}

export interface AudioFileUpdate {
  file_name?: string
  language?: string
  speaker_count?: number
  scene?: string
  tag_names?: string[]
}

export async function updateFile(fileId: string, payload: AudioFileUpdate): Promise<AudioFile> {
  const resp = await client.patch(`/files/${fileId}`, payload)
  return resp.data
}

export interface AudioFileDownload {
  file_id: string
  download_url: string
  expires_in_sec: number
}

export interface ListFilesParams {
  mine_only?: boolean
  folder_id?: string
  root_only?: boolean
  q?: string
  language?: string
  scene?: string
  source?: string
  speaker_count?: number
  duration_min?: number
  duration_max?: number
  date_from?: string
  date_to?: string
  tags?: string[]
  page?: number
  page_size?: number
}

export async function listFiles(params: ListFilesParams = {}): Promise<AudioFile[]> {
  const resp = await client.get('/files', { params })
  return resp.data
}

export async function getFile(fileId: string): Promise<AudioFile> {
  const resp = await client.get(`/files/${fileId}`)
  return resp.data
}

export async function getDownloadUrl(
  fileId: string,
  forceDownload = false,
): Promise<AudioFileDownload> {
  const resp = await client.get(`/files/${fileId}/download`, {
    params: forceDownload ? { force_download: true } : {},
  })
  return resp.data
}

export async function deleteFile(fileId: string): Promise<void> {
  await client.delete(`/files/${fileId}`)
}

export async function restoreFile(fileId: string): Promise<void> {
  await client.post(`/files/${fileId}/restore`)
}

export async function purgeFile(fileId: string): Promise<void> {
  await client.delete(`/files/${fileId}/purge`)
}

// ===== 批量 =====
export async function batchMove(file_ids: string[], folder_id: string | null): Promise<void> {
  await client.post('/files/batch/move', { file_ids, folder_id })
}
export async function batchDelete(file_ids: string[]): Promise<void> {
  await client.post('/files/batch/delete', { file_ids })
}
export async function batchRestore(file_ids: string[]): Promise<void> {
  await client.post('/files/batch/restore', { file_ids })
}
export async function batchPurge(file_ids: string[]): Promise<void> {
  await client.post('/files/batch/purge', { file_ids })
}

/** PRD §13.3: 批量下载（ZIP）。返回的是 Blob，前端用 <a download> 触发。 */
export async function batchDownload(file_ids: string[]): Promise<void> {
  const resp = await client.post('/files/batch/download', { file_ids }, {
    responseType: 'blob',
    timeout: 600000,  // 5 min
  })
  const url = window.URL.createObjectURL(resp.data as Blob)
  const a = document.createElement('a')
  a.href = url
  const ts = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '')
  a.download = `audio_export_${ts}.zip`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => window.URL.revokeObjectURL(url), 1000)
}

export interface TranscriptLine {
  speaker_id: string
  text: string
  start_time?: number | null
  end_time?: number | null
}

export interface TranscriptResponse {
  file_id: string
  has_transcript: boolean
  lines: TranscriptLine[]
  has_json: boolean
  has_srt: boolean
  json_download_url?: string | null
  srt_download_url?: string | null
  voice_names?: Record<string, string>  // speaker_id -> voice_name
}

export async function getTranscript(fileId: string): Promise<TranscriptResponse> {
  const resp = await client.get(`/files/${fileId}/transcript`)
  return resp.data
}
