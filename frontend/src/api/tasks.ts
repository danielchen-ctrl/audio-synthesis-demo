import client from './client'

export interface VoiceAssignment {
  voice_id: string
  voice_name?: string
}

export interface TaskCreatePayload {
  generation_mode: 'llm' | 'manual'
  topic: string
  language: string
  speaker_count: number
  voice_assignments: Record<string, VoiceAssignment>
  audio_format?: 'wav' | 'mp3' | 'm4a'
  template?: string
  custom_prompt?: string
  keywords?: string[]
  target_duration_sec?: number
  dialogue_text?: string
  folder_id?: string | null
  tag_names?: string[]
  generate_scripts?: boolean
}

export interface Task {
  task_id: string
  status: string
  generation_mode: string
  progress: number
  params: Record<string, any>
  dialogue_text: string | null
  file_id: string | null
  error_code: string | null
  error_message: string | null
  queued_at: string
  started_at: string | null
  finished_at: string | null
}

export interface TaskListItem {
  task_id: string
  status: string
  generation_mode: string
  progress: number
  queued_at: string
  finished_at: string | null
  error_message: string | null
  file_id: string | null
  topic: string | null
  language: string | null
  speaker_count: number | null
}

export interface DialoguePreviewPayload {
  topic: string
  template: string
  custom_prompt?: string
  language: string
  speaker_count: number
  target_duration_sec: number
  keywords?: string[]
}

export interface DialoguePreviewResult {
  dialogue_text: string
  line_count: number
  model: string
}

export async function previewDialogue(
  payload: DialoguePreviewPayload,
): Promise<DialoguePreviewResult> {
  const resp = await client.post('/tasks/preview-dialogue', payload, { timeout: 90000 })
  return resp.data
}

export async function createTask(payload: TaskCreatePayload): Promise<Task> {
  const resp = await client.post('/tasks', payload)
  return resp.data
}

export async function listTasks(page = 1, pageSize = 20): Promise<TaskListItem[]> {
  const resp = await client.get('/tasks', { params: { page, page_size: pageSize } })
  return resp.data
}

export async function getTask(taskId: string): Promise<Task> {
  const resp = await client.get(`/tasks/${taskId}`)
  return resp.data
}

export async function cancelTask(taskId: string): Promise<Task> {
  const resp = await client.post(`/tasks/${taskId}/cancel`)
  return resp.data
}

export async function retryTask(taskId: string): Promise<Task> {
  const resp = await client.post(`/tasks/${taskId}/retry`)
  return resp.data
}

export async function deleteTask(taskId: string): Promise<void> {
  await client.delete(`/tasks/${taskId}`)
}
