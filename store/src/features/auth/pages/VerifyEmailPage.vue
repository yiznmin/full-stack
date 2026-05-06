<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { Loader2, Check, AlertCircle } from 'lucide-vue-next'
import * as authApi from '../api'

const route = useRoute()

// 同時支援 path param /verify-email/:token 與 query ?token=（backend 舊版本相容）
const token = computed(() => {
  const fromPath = route.params.token
  if (typeof fromPath === 'string' && fromPath.length > 0) return fromPath
  const fromQuery = route.query.token
  if (typeof fromQuery === 'string' && fromQuery.length > 0) return fromQuery
  return ''
})
const tokenValid = computed(() => token.value.length > 0)

type State = 'pending' | 'success' | 'failed'
const state = ref<State>('pending')
const tokenType = ref<'register' | 'email_change' | null>(null)
const apiError = ref<string | null>(null)

async function verify() {
  if (!tokenValid.value) {
    state.value = 'failed'
    apiError.value = '驗證連結缺少 token 或已損壞'
    return
  }
  try {
    const res = await authApi.verifyEmail(token.value)
    tokenType.value = res.token_type
    state.value = 'success'
  } catch (e) {
    const err = e as authApi.ApiError
    if (err.status === 400 || err.status === 410) {
      apiError.value = '驗證連結已失效或已使用'
    } else if (err.status === 409) {
      apiError.value = err.detail || '此 email 已被其他帳號使用'
    } else {
      apiError.value = err.detail || '驗證失敗，請稍後再試'
    }
    state.value = 'failed'
  }
}

onMounted(() => {
  verify()
})

const successMessage = computed(() => {
  return tokenType.value === 'email_change'
    ? 'Email 已成功更新'
    : 'Email 已驗證完成'
})

const successHint = computed(() => {
  return tokenType.value === 'email_change'
    ? '你的新 email 已生效，現在可以登入。'
    : '註冊完成 — 歡迎加入易木 YIIMUI。現在可以登入開始使用。'
})
</script>

<template>
  <div class="page" :class="state">
    <template v-if="state === 'pending'">
      <div class="pending-icon"><Loader2 class="spin-large" /></div>
      <h1 class="title">驗證中...</h1>
      <p class="lede">正在確認你的 email，請稍候。</p>
    </template>

    <template v-else-if="state === 'success'">
      <div class="success-icon"><Check /></div>
      <h1 class="title">{{ successMessage }}</h1>
      <p class="lede">{{ successHint }}</p>
      <RouterLink to="/login" class="btn-primary">前往登入</RouterLink>
    </template>

    <template v-else>
      <div class="error-icon"><AlertCircle /></div>
      <h1 class="title">驗證失敗</h1>
      <p class="lede">{{ apiError }}</p>
      <div class="actions">
        <RouterLink to="/register" class="btn-secondary">重新註冊</RouterLink>
        <RouterLink to="/login" class="btn-link">回到登入 →</RouterLink>
      </div>
    </template>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 28px;
  letter-spacing: 0.08em;
  color: var(--color-ink-strong);
  margin: 16px 0 12px;
}
.lede {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  line-height: 1.95;
  letter-spacing: 0.04em;
  color: var(--color-ink-muted);
  margin: 0 0 28px;
  max-width: 320px;
}

.pending-icon, .success-icon, .error-icon {
  width: 64px; height: 64px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
}
.pending-icon { background: var(--color-paper-deep); border: 1px solid var(--color-line); }
.pending-icon :deep(svg) {
  width: 28px; height: 28px;
  stroke: var(--color-accent); stroke-width: 1.75; fill: none;
}
.spin-large { animation: spin 1s linear infinite; }
.success-icon {
  background: var(--color-fresh-tint);
  border: 1px solid var(--color-fresh);
}
.success-icon :deep(svg) {
  width: 28px; height: 28px;
  stroke: var(--color-fresh); stroke-width: 2; fill: none;
}
.error-icon {
  background: rgba(155, 58, 80, 0.10);
  border: 1px solid var(--color-state-danger);
}
.error-icon :deep(svg) {
  width: 28px; height: 28px;
  stroke: var(--color-state-danger); stroke-width: 1.75; fill: none;
}
@keyframes spin { to { transform: rotate(360deg); } }

.btn-primary {
  height: 48px;
  padding: 0 36px;
  font-family: var(--font-body);
  font-size: 12px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-paper-canvas);
  background: var(--color-ink-strong);
  border: 1px solid var(--color-ink-strong);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  transition: background 200ms, border-color 200ms;
}
.btn-primary:hover {
  background: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
}

.btn-secondary {
  height: 48px;
  padding: 0 32px;
  font-family: var(--font-body);
  font-size: 12px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-ink-strong);
  background: transparent;
  border: 1px solid var(--color-line);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  transition: border-color 200ms, color 200ms;
}
.btn-secondary:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}

.btn-link {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  transition: color 150ms;
}
.btn-link:hover { color: var(--color-accent-deep); }
</style>
