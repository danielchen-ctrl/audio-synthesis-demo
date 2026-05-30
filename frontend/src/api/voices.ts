import client from './client'

export interface Voice {
  voice_id: string
  name: string
  language: string
  gender: string | null
}

export interface VoiceCreateResponse {
  voice_id: string
  name: string
  verified: boolean
  message: string
}

/** 获取音色列表（全局共享，可按语言过滤） */
export async function listVoicesFromDB(language?: string): Promise<Voice[]> {
  const params = language ? `?language=${encodeURIComponent(language)}` : ''
  const resp = await client.get(`/voices${params}`)
  return resp.data
}

/** 注册新音色（multipart：audio file + 元数据） */
export async function registerVoice(
  audioFile: File,
  meta: { name: string; language: string; gender?: string; reference_text?: string },
): Promise<VoiceCreateResponse> {
  const form = new FormData()
  form.append('audio', audioFile)
  const params = new URLSearchParams({ name: meta.name, language: meta.language })
  if (meta.gender) params.append('gender', meta.gender)
  if (meta.reference_text) params.append('reference_text', meta.reference_text)
  const resp = await client.post(`/voices?${params}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,  // 音色注册：上传 + CosyVoice 处理最长 120 秒
  })
  return resp.data
}

/** 删除音色（仅创建者可操作） */
export async function deleteVoice(voiceId: string, deleteRemote = false): Promise<void> {
  await client.delete(`/voices/${voiceId}?delete_remote=${deleteRemote}`)
}
