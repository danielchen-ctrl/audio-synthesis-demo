import client from './client'

export interface Language {
  code: string
  name: string
}

export interface Template {
  code: string
  name: string
  description: string
  roles?: string[]
  core_keywords?: string[]
  example_topic?: string
  default_speaker_count?: number
  default_target_words?: number
}

export interface Voice {
  voice_id: string
  name: string
  language: string
  gender: string | null
}

export async function listLanguages(): Promise<Language[]> {
  const resp = await client.get('/meta/languages')
  return resp.data
}

export async function listTemplates(): Promise<Template[]> {
  const resp = await client.get('/meta/templates')
  return resp.data
}

export async function listVoices(language?: string): Promise<Voice[]> {
  const resp = await client.get('/meta/voices', { params: language ? { language } : {} })
  return resp.data
}
