import axios, { AxiosError } from 'axios'
import { useAuthStore } from '@/stores/auth'

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  // FastAPI 期望 ?tags=a&tags=b（重复 key），不是 ?tags[]=a&tags[]=b
  paramsSerializer: {
    serialize: (params) => {
      const out = new URLSearchParams()
      for (const [k, v] of Object.entries(params)) {
        if (v === undefined || v === null || v === '') continue
        if (Array.isArray(v)) {
          v.forEach((x) => out.append(k, String(x)))
        } else if (typeof v === 'boolean') {
          out.append(k, v ? 'true' : 'false')
        } else {
          out.append(k, String(v))
        }
      }
      return out.toString()
    },
  },
})

client.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

client.interceptors.response.use(
  (resp) => resp,
  (err: AxiosError<{ detail?: string }>) => {
    if (err.response?.status === 401) {
      const auth = useAuthStore()
      auth.logout()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  },
)

export function errorMessage(e: unknown): string {
  if (axios.isAxiosError(e)) {
    return e.response?.data?.detail || e.message || '请求失败'
  }
  return String(e)
}

export default client
