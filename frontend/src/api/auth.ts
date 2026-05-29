import client from './client'

export interface User {
  user_id: string
  username: string
  display_name: string | null
  created_at: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export async function register(data: {
  username: string
  password: string
  display_name?: string
}): Promise<LoginResponse> {
  const resp = await client.post('/auth/register', data)
  return resp.data
}

export async function login(data: { username: string; password: string }): Promise<LoginResponse> {
  const resp = await client.post('/auth/login', data)
  return resp.data
}

export async function me(): Promise<User> {
  const resp = await client.get('/auth/me')
  return resp.data
}

export interface SSOConfig {
  google_enabled: boolean
  google_client_id: string | null
  allowed_domain: string | null
}

export async function getSSOConfig(): Promise<SSOConfig> {
  const resp = await client.get('/auth/sso/config')
  return resp.data
}

export async function loginWithGoogle(id_token: string): Promise<LoginResponse> {
  const resp = await client.post('/auth/google', { id_token })
  return resp.data
}
