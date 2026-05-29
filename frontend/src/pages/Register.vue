<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { register, getSSOConfig, loginWithGoogle } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { errorMessage } from '@/api/client'

declare global {
  interface Window { google?: any }
}

const googleBtnRef = ref<HTMLElement | null>(null)

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()

const username = ref('')
const password = ref('')
const confirm = ref('')
const loading = ref(false)
const userErr = ref('')
const confErr = ref('')
const generalErr = ref('')

const ssoEnabled = ref(false)
const ssoDomain = ref('')
let googleClientId = ''

function clearErr() { userErr.value = ''; confErr.value = ''; generalErr.value = '' }

async function submit() {
  clearErr()
  if (!username.value) { userErr.value = '请输入用户名'; return }
  if (!/^[A-Za-z0-9_]{3,20}$/.test(username.value)) {
    userErr.value = '用户名 3-20 字符，仅字母/数字/下划线'
    return
  }
  if (password.value.length < 6 || password.value.length > 30) {
    generalErr.value = '密码长度需 6-30 字符'
    return
  }
  if (password.value !== confirm.value) {
    confErr.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    const resp = await register({ username: username.value, password: password.value })
    auth.setSession(resp.access_token, resp.user)
    message.success('注册成功')
    router.push('/home')
  } catch (e) {
    generalErr.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

function waitForGoogle(timeoutMs = 5000): Promise<any> {
  return new Promise((resolve, reject) => {
    const start = Date.now()
    const check = () => {
      if (window.google?.accounts?.id) return resolve(window.google.accounts.id)
      if (Date.now() - start > timeoutMs) return reject(new Error('Google SDK 加载超时'))
      setTimeout(check, 100)
    }
    check()
  })
}

async function initGoogleButton() {
  if (!ssoEnabled.value || !googleBtnRef.value) return
  try {
    const gid = await waitForGoogle()
    gid.initialize({
      client_id: googleClientId,
      callback: async (resp: any) => {
        try {
          const r = await loginWithGoogle(resp.credential)
          auth.setSession(r.access_token, r.user)
          message.success('注册并登录成功')
          router.push('/home')
        } catch (e) { message.error(errorMessage(e)) }
      },
      use_fedcm_for_prompt: false,
    })
    gid.renderButton(googleBtnRef.value, {
      type: 'standard',
      theme: 'outline',
      size: 'large',
      text: 'signup_with',
      shape: 'rectangular',
      logo_alignment: 'center',
      width: 336,
      locale: 'zh_CN',
    })
  } catch (e) {
    console.error('Google init failed:', e)
  }
}

onMounted(async () => {
  try {
    const cfg = await getSSOConfig()
    ssoEnabled.value = cfg.google_enabled
    googleClientId = cfg.google_client_id || ''
    ssoDomain.value = cfg.allowed_domain || ''
  } catch { /* silent */ }
  if (ssoEnabled.value) setTimeout(initGoogleButton, 100)
})

watch(googleBtnRef, (el) => {
  if (el && ssoEnabled.value) initGoogleButton()
})
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-logo">
        <div class="auth-logo-row">
          <div class="auth-logo-icon">
            <svg viewBox="0 0 40 40" width="36" height="36" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4 36 L14 10 Q20 5 26 10 L36 36"
                    stroke="white" stroke-width="7"
                    stroke-linecap="round" stroke-linejoin="round" />
              <circle cx="20" cy="26" r="3.2" fill="white" />
            </svg>
          </div>
          <div class="auth-logo-text">PLAUD</div>
        </div>
        <div class="auth-platform-name">音频语料平台</div>
      </div>

      <div class="auth-title">创建账号</div>
      <div class="auth-subtitle">加入 Plaud 音频语料生成平台</div>

      <template v-if="ssoEnabled">
        <div class="google-btn-wrap">
          <div ref="googleBtnRef"></div>
          <div v-if="ssoDomain" class="sso-hint-line">仅 @{{ ssoDomain }} 账号可注册</div>
        </div>

        <div class="sso-divider"><span>或填写账号密码注册</span></div>
      </template>

      <form @submit.prevent="submit">
        <div class="form-group">
          <label class="form-label">用户名<span class="req">*</span></label>
          <input v-model="username" class="input-field" type="text"
                 placeholder="请输入用户名" autocomplete="username" @input="clearErr" />
          <div class="form-hint">3–20 字符，字母 / 数字 / 下划线</div>
          <div v-if="userErr" class="form-err">⚠ {{ userErr }}</div>
        </div>
        <div class="form-group">
          <label class="form-label">密码<span class="req">*</span></label>
          <input v-model="password" class="input-field" type="password"
                 placeholder="请输入密码" autocomplete="new-password" @input="clearErr" />
          <div class="form-hint">6–30 字符</div>
        </div>
        <div class="form-group">
          <label class="form-label">确认密码<span class="req">*</span></label>
          <input v-model="confirm" class="input-field" type="password"
                 placeholder="请再次输入密码" autocomplete="new-password"
                 @input="clearErr" @keyup.enter="submit" />
          <div v-if="confErr" class="form-err">⚠ {{ confErr }}</div>
        </div>
        <div v-if="generalErr" class="form-err mb8">⚠ {{ generalErr }}</div>
        <button type="submit" class="btn btn-primary btn-full btn-lg mt8" :disabled="loading">
          {{ loading ? '注册中...' : '注册账号' }}
        </button>
      </form>

      <div class="auth-footer">
        已有账号？<a @click="router.push('/login')">去登录</a>
      </div>
    </div>
  </div>
</template>
