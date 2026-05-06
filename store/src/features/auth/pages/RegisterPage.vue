<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useForm } from 'vee-validate'
import { toTypedSchema } from '@vee-validate/zod'
import { Loader2, Check } from 'lucide-vue-next'
import * as authApi from '../api'
import { registerSchema, type RegisterValues } from '../schemas'

const RESEND_COOLDOWN = 60

const apiError = ref<string | null>(null)
const submitting = ref(false)
const sentEmail = ref<string | null>(null)
const resending = ref(false)
const resendCooldown = ref(0)
let cooldownTimer: ReturnType<typeof setInterval> | null = null

const { handleSubmit, errors, defineField } = useForm<RegisterValues>({
  validationSchema: toTypedSchema(registerSchema),
  initialValues: { name: '', email: '', password: '' },
})

const [name, nameAttrs] = defineField('name')
const [email, emailAttrs] = defineField('email')
const [password, passwordAttrs] = defineField('password')

function startCooldown() {
  resendCooldown.value = RESEND_COOLDOWN
  if (cooldownTimer) clearInterval(cooldownTimer)
  cooldownTimer = setInterval(() => {
    resendCooldown.value -= 1
    if (resendCooldown.value <= 0 && cooldownTimer) {
      clearInterval(cooldownTimer)
      cooldownTimer = null
    }
  }, 1000)
}

const onSubmit = handleSubmit(async (values) => {
  apiError.value = null
  submitting.value = true
  try {
    await authApi.register(values.name, values.email, values.password)
    sentEmail.value = values.email
    startCooldown() // 第一封信也開始冷卻，避免馬上重送
  } catch (e) {
    const err = e as authApi.ApiError
    if (err.status === 409) {
      apiError.value = 'Email 已註冊，請改為登入'
    } else {
      apiError.value = err.detail || '註冊失敗，請稍後再試'
    }
  } finally {
    submitting.value = false
  }
})

const resendDisabled = computed(
  () => resending.value || resendCooldown.value > 0,
)

const resendLabel = computed(() => {
  if (resending.value) return '重新寄送中...'
  if (resendCooldown.value > 0) return `重新寄送（${resendCooldown.value}s）`
  return '重新寄送'
})

async function resend() {
  if (!sentEmail.value || resendDisabled.value) return
  resending.value = true
  try {
    await authApi.resendVerification(sentEmail.value)
    startCooldown()
  } catch {
    // 後端統一回固定訊息，不會壞
  } finally {
    resending.value = false
  }
}

onUnmounted(() => {
  if (cooldownTimer) clearInterval(cooldownTimer)
})
</script>

<template>
  <!-- Success state — 寄出驗證信後 -->
  <div v-if="sentEmail" class="page success">
    <div class="success-icon">
      <Check />
    </div>
    <h1 class="title">驗證信已寄出</h1>
    <p class="lede">
      我們寄了一封驗證信到<br />
      <strong>{{ sentEmail }}</strong><br />
      請點擊信中連結完成註冊。
    </p>
    <p class="hint">
      沒收到信？檢查垃圾郵件夾，或
      <button
        type="button"
        class="link-btn"
        :disabled="resendDisabled"
        @click="resend"
      >
        {{ resendLabel }}
      </button>
    </p>
    <RouterLink to="/login" class="btn-secondary">回到登入</RouterLink>
  </div>

  <!-- Form state -->
  <div v-else class="page">
    <header class="head">
      <span class="eyebrow">— Sign Up —</span>
      <h1 class="title">建立帳號</h1>
      <p class="lede">在易木 YIIMUI 開始你的數字油畫旅程。</p>
    </header>

    <form class="form" @submit.prevent="onSubmit" novalidate>
      <div class="field">
        <label for="reg-name">名稱</label>
        <input
          id="reg-name"
          v-model="name"
          v-bind="nameAttrs"
          type="text"
          autocomplete="name"
          autofocus
          :class="{ invalid: !!errors.name }"
        />
        <p v-if="errors.name" class="err">{{ errors.name }}</p>
        <p v-else class="hint-line">至少 4 個字元</p>
      </div>

      <div class="field">
        <label for="reg-email">Email</label>
        <input
          id="reg-email"
          v-model="email"
          v-bind="emailAttrs"
          type="email"
          autocomplete="email"
          :class="{ invalid: !!errors.email }"
        />
        <p v-if="errors.email" class="err">{{ errors.email }}</p>
      </div>

      <div class="field">
        <label for="reg-pwd">密碼</label>
        <input
          id="reg-pwd"
          v-model="password"
          v-bind="passwordAttrs"
          type="password"
          autocomplete="new-password"
          :class="{ invalid: !!errors.password }"
        />
        <p v-if="errors.password" class="err">{{ errors.password }}</p>
        <p v-else class="hint-line">至少 10 字元，須含英文字母與數字</p>
      </div>

      <p v-if="apiError" class="api-err">{{ apiError }}</p>

      <button type="submit" class="btn-primary" :disabled="submitting">
        <Loader2 v-if="submitting" class="spin" />
        <span>{{ submitting ? '註冊中...' : '建立帳號' }}</span>
      </button>
    </form>

    <div class="alt">
      已經有帳號？
      <RouterLink to="/login" class="alt-link">登入 →</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.page { display: flex; flex-direction: column; }
.success { text-align: center; align-items: center; }

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
  margin: 0 0 16px;
}
.lede strong { color: var(--color-ink-strong); font-weight: 400; }

.success-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--color-fresh-tint);
  border: 1px solid var(--color-fresh);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}
.success-icon :deep(svg) {
  width: 28px; height: 28px;
  stroke: var(--color-fresh);
  stroke-width: 2;
  fill: none;
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
.hint {
  font-size: 13px;
  color: var(--color-ink-muted);
  margin: 0 0 24px;
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

.link-btn {
  background: transparent;
  border: none;
  color: var(--color-accent);
  font: inherit;
  cursor: pointer;
  padding: 0;
  border-bottom: 1px solid var(--color-accent);
  transition: color 150ms, border-color 150ms, opacity 150ms;
}
.link-btn:hover:not(:disabled) {
  color: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}
.link-btn:disabled {
  color: var(--color-ink-muted);
  border-color: var(--color-line);
  cursor: not-allowed;
  opacity: 0.7;
}

.alt {
  margin-top: 28px;
  padding-top: 24px;
  border-top: 1px solid var(--color-line-subtle);
  text-align: center;
  font-size: 13px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
}
.alt-link {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
  margin-left: 8px;
}
.alt-link:hover { color: var(--color-accent-deep); }
</style>
