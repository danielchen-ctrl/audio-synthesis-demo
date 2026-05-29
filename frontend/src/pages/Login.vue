<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useMessage } from 'naive-ui'
import { login, getSSOConfig, loginWithGoogle } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { errorMessage } from '@/api/client'

declare global {
  interface Window {
    google?: any
  }
}

const router = useRouter()
const auth = useAuthStore()
const message = useMessage()

const username = ref('')
const password = ref('')
const loading = ref(false)
const errorText = ref('')

const ssoEnabled = ref(false)
const ssoDomain = ref('')
let googleClientId = ''

// Google 按钮渲染容器
const googleBtnRef = ref<HTMLElement | null>(null)

async function submit() {
  errorText.value = ''
  if (!username.value || !password.value) {
    errorText.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  try {
    const resp = await login({ username: username.value, password: password.value })
    auth.setSession(resp.access_token, resp.user)
    message.success('登录成功')
    router.push('/home')
  } catch (e) {
    errorText.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

// 等 GIS SDK 加载
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
          message.success('登录成功')
          router.push('/home')
        } catch (e) { message.error(errorMessage(e)) }
      },
      // 关闭 FedCM 依赖（用 popup 流程，全浏览器兼容）
      use_fedcm_for_prompt: false,
    })
    // 渲染 Google 官方按钮（popup 流程，不依赖 FedCM）
    gid.renderButton(googleBtnRef.value, {
      type: 'standard',
      theme: 'outline',
      size: 'large',
      text: 'continue_with',
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
  } catch {
    // 拿不到就当 SSO 没启
  }
  // 配置就绪后渲染按钮
  if (ssoEnabled.value) {
    setTimeout(initGoogleButton, 100)  // 等 ref 挂载
  }
})

// 防止首次没渲染上：监听 ref 出现
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

      <div class="auth-title">欢迎回来</div>
      <div class="auth-subtitle">登录您的账号继续使用</div>

      <template v-if="ssoEnabled">
        <div class="google-btn-wrap">
          <div ref="googleBtnRef"></div>
          <div v-if="ssoDomain" class="sso-hint-line">仅 @{{ ssoDomain }} 账号可登录</div>
        </div>

        <div class="sso-divider"><span>或使用账号密码</span></div>
      </template>

      <form @submit.prevent="submit">
        <div class="form-group">
          <label class="form-label">用户名<span class="req">*</span></label>
          <input v-model="username" class="input-field" type="text"
                 placeholder="请输入用户名" autocomplete="username" />
        </div>
        <div class="form-group">
          <label class="form-label">密码<span class="req">*</span></label>
          <input v-model="password" class="input-field" type="password"
                 placeholder="请输入密码" autocomplete="current-password"
                 @keyup.enter="submit" />
          <div v-if="errorText" class="form-err">⚠ {{ errorText }}</div>
        </div>
        <button type="submit" class="btn btn-primary btn-full btn-lg mt8" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>

      <div class="auth-footer">
        还没有账号？<a @click="router.push('/register')">免费注册</a>
      </div>
    </div>
  </div>
</template>
