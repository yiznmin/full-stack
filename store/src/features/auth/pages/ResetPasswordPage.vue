<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useForm } from 'vee-validate'
import { toTypedSchema } from '@vee-validate/zod'
import { Loader2, Check, AlertCircle } from 'lucide-vue-next'
import * as authApi from '../api'
import { resetPasswordSchema, type ResetPasswordValues } from '../schemas'

const route = useRoute()
const router = useRouter()

// 同時支援 path param /reset-password/:token 與 query ?token=（backend 舊版本相容）
const token = computed(() => {
  const fromPath = route.params.token
  if (typeof fromPath === 'string' && fromPath.length > 0) return fromPath
  const fromQuery = route.query.token
  if (typeof fromQuery === 'string' && fromQuery.length > 0) return fromQuery
  return ''
})
const tokenValid = computed(() => token.value.length > 0)

const apiError = ref<string | null>(null)
const submitting = ref(false)
const success = ref(false)

const { handleSubmit, errors, defineField } = useForm<ResetPasswordValues>({
  validationSchema: toTypedSchema(resetPasswordSchema),
  initialValues: { new_password: '', confirm_password: '' },
})

const [newPassword, newPasswordAttrs] = defineField('new_password')
const [confirmPassword, confirmPasswordAttrs] = defineField('confirm_password')

const onSubmit = handleSubmit(async (values) => {
  apiError.value = null
  submitting.value = true
  try {
    await authApi.resetPassword(token.value, values.new_password)
    success.value = true
    setTimeout(() => router.push('/login'), 1800)
  } catch (e) {
    const err = e as authApi.ApiError
    if (err.status === 400 || err.status === 410) {
      apiError.value = '連結已失效或已使用，請重新申請忘記密碼'
    } else {
      apiError.value = err.detail || '重設失敗，請稍後再試'
    }
  } finally {
    submitting.value = false
  }
})
</script>

<template>
  <div v-if="!tokenValid" class="page error">
    <div class="error-icon"><AlertCircle /></div>
    <h1 class="title">連結無效</h1>
    <p class="lede">這個重設密碼連結缺少 token 或已損壞。</p>
    <RouterLink to="/forgot-password" class="btn-secondary">重新申請</RouterLink>
  </div>

  <div v-else-if="success" class="page success">
    <div class="success-icon"><Check /></div>
    <h1 class="title">密碼已更新</h1>
    <p class="lede">即將為你跳到登入頁...</p>
  </div>

  <div v-else class="page">
    <header class="head">
      <span class="eyebrow">— Reset Password —</span>
      <h1 class="title">重設密碼</h1>
      <p class="lede">請輸入新密碼。</p>
    </header>

    <form class="form" @submit.prevent="onSubmit" novalidate>
      <div class="field">
        <label for="rp-pwd">新密碼</label>
        <input
          id="rp-pwd"
          v-model="newPassword"
          v-bind="newPasswordAttrs"
          type="password"
          autocomplete="new-password"
          autofocus
          :class="{ invalid: !!errors.new_password }"
        />
        <p v-if="errors.new_password" class="err">{{ errors.new_password }}</p>
        <p v-else class="hint-line">至少 10 字元，須含英文字母與數字</p>
      </div>

      <div class="field">
        <label for="rp-confirm">確認新密碼</label>
        <input
          id="rp-confirm"
          v-model="confirmPassword"
          v-bind="confirmPasswordAttrs"
          type="password"
          autocomplete="new-password"
          :class="{ invalid: !!errors.confirm_password }"
        />
        <p v-if="errors.confirm_password" class="err">{{ errors.confirm_password }}</p>
      </div>

      <p v-if="apiError" class="api-err">{{ apiError }}</p>

      <button type="submit" class="btn-primary" :disabled="submitting">
        <Loader2 v-if="submitting" class="spin" />
        <span>{{ submitting ? '更新中...' : '更新密碼' }}</span>
      </button>
    </form>
  </div>
</template>

<style scoped>
.page { display: flex; flex-direction: column; }
.success, .error { text-align: center; align-items: center; }

.head { text-align: center; margin-bottom: 32px; }
.eyebrow {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-fresh);
}
.title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 32px;
  letter-spacing: 0.08em;
  color: var(--color-ink-strong);
  margin: 12px 0 8px;
}
.lede {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  line-height: 1.95;
  letter-spacing: 0.04em;
  color: var(--color-ink-muted);
  margin: 0 0 24px;
}

.success-icon, .error-icon {
  width: 64px; height: 64px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 24px;
}
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

.form { display: flex; flex-direction: column; gap: 20px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-default);
}
.field input {
  font-family: var(--font-body);
  font-size: 15px;
  color: var(--color-ink-strong);
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  padding: 12px 14px;
  outline: none;
  transition: border-color 150ms, box-shadow 150ms;
}
.field input:focus {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-tint);
}
.field input.invalid { border-color: var(--color-state-danger); }

.err {
  font-size: 12px;
  color: var(--color-state-danger);
  margin: 2px 0 0;
  letter-spacing: 0.04em;
}
.hint-line {
  font-size: 11px;
  color: var(--color-ink-muted);
  margin: 2px 0 0;
  letter-spacing: 0.04em;
}
.api-err {
  margin: 0;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--color-state-danger);
  background: rgba(155, 58, 80, 0.08);
  border: 1px solid var(--color-state-danger);
  border-radius: var(--radius-xs);
  letter-spacing: 0.04em;
}

.btn-primary {
  margin-top: 8px;
  height: 48px;
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
  gap: 10px;
  transition: background 200ms, border-color 200ms;
}
.btn-primary:hover:not(:disabled) {
  background: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

.btn-secondary {
  margin-top: 8px;
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

.spin {
  width: 14px; height: 14px;
  stroke: currentColor; stroke-width: 1.75; fill: none;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
