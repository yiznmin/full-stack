<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import {
  ArrowLeft, Check, Loader2, Mail, RefreshCcw,
} from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'
import * as profileApi from '../api'
import type { Gender, UpdateProfilePayload, UserProfile } from '../api'
import ChangePasswordDialog from '../components/ChangePasswordDialog.vue'
import ChangeEmailDialog from '../components/ChangeEmailDialog.vue'

const queryClient = useQueryClient()

const profileQuery = useQuery({
  queryKey: ['user-profile'] as const,
  queryFn: profileApi.fetchProfile,
})

const profile = computed<UserProfile | null>(() => profileQuery.data.value ?? null)

// 整體表單 state（不再 inline auto-save）
interface FormState {
  name: string
  gender: Gender | ''
  birthYear: number | ''
  birthMonth: number | ''
  birthDay: number | ''
}
const form = reactive<FormState>({
  name: '',
  gender: '',
  birthYear: '',
  birthMonth: '',
  birthDay: '',
})

// Field-level error
const errors = reactive<Record<string, string>>({})

function loadFromProfile(p: UserProfile) {
  form.name = p.name
  form.gender = p.gender ?? ''
  if (p.birthday) {
    const [y, m, d] = p.birthday.split('-').map(Number)
    form.birthYear = y
    form.birthMonth = m
    form.birthDay = d
  } else {
    form.birthYear = ''
    form.birthMonth = ''
    form.birthDay = ''
  }
  // clear errors
  for (const k of Object.keys(errors)) delete errors[k]
}

watch(profile, (p) => { if (p) loadFromProfile(p) }, { immediate: true })

// Year / Month / Day options
const currentYear = new Date().getFullYear()
const yearOptions = Array.from({ length: 100 }, (_, i) => currentYear - i)
const monthOptions = Array.from({ length: 12 }, (_, i) => i + 1)
const dayOptions = computed(() => {
  if (!form.birthYear || !form.birthMonth) return Array.from({ length: 31 }, (_, i) => i + 1)
  const last = new Date(Number(form.birthYear), Number(form.birthMonth), 0).getDate()
  return Array.from({ length: last }, (_, i) => i + 1)
})

// 是否有改動 (dirty)
const isDirty = computed(() => {
  if (!profile.value) return false
  if (form.name !== profile.value.name) return true
  if (form.gender !== (profile.value.gender ?? '')) return true
  const original = profile.value.birthday ?? ''
  const current = (form.birthYear && form.birthMonth && form.birthDay)
    ? `${form.birthYear}-${String(form.birthMonth).padStart(2, '0')}-${String(form.birthDay).padStart(2, '0')}`
    : ''
  if (current !== original) return true
  return false
})

// ── 驗證 ─────────────────────────────────────────────────────────────────────

function validate(): boolean {
  for (const k of Object.keys(errors)) delete errors[k]

  // 姓名：非空 + ≥ 4 字
  const name = form.name.trim()
  if (!name) {
    errors.name = '姓名不可為空'
  } else if (name.length < 4) {
    errors.name = '姓名至少 4 個字元'
  }

  // 生日：三段式必須一致 — 要嘛全空（不填）、要嘛三個都填且日期合法
  const yFilled = form.birthYear !== ''
  const mFilled = form.birthMonth !== ''
  const dFilled = form.birthDay !== ''
  const allFilled = yFilled && mFilled && dFilled
  const allEmpty = !yFilled && !mFilled && !dFilled
  if (!allFilled && !allEmpty) {
    errors.birthday = '生日年/月/日 三欄需一起填寫或一起留空'
  } else if (allFilled) {
    const y = Number(form.birthYear)
    const m = Number(form.birthMonth)
    const d = Number(form.birthDay)
    // 必須是合法日期
    const date = new Date(y, m - 1, d)
    if (
      date.getFullYear() !== y
      || date.getMonth() !== m - 1
      || date.getDate() !== d
    ) {
      errors.birthday = '請輸入有效的日期'
    } else if (date > new Date()) {
      errors.birthday = '生日不可為未來日期'
    } else if (y < 1900) {
      errors.birthday = '生日年份不合理（早於 1900 年）'
    }
  }

  return Object.keys(errors).length === 0
}

// ── 儲存 ─────────────────────────────────────────────────────────────────────
const apiError = ref<string | null>(null)
const savedToast = ref<string | null>(null)
let savedToastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(text: string) {
  savedToast.value = text
  if (savedToastTimer) clearTimeout(savedToastTimer)
  savedToastTimer = setTimeout(() => { savedToast.value = null }, 2400)
}

const updateMut = useMutation({
  mutationFn: (payload: UpdateProfilePayload) => profileApi.updateProfile(payload),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['user-profile'] })
    showToast('已儲存')
  },
})

async function save() {
  apiError.value = null
  if (!validate()) return

  // build payload — 只送有變動的欄位
  const payload: UpdateProfilePayload = {}
  if (!profile.value) return

  if (form.name.trim() !== profile.value.name) {
    payload.name = form.name.trim()
  }
  const newGender: Gender | null = form.gender === '' ? null : form.gender as Gender
  if (newGender !== (profile.value.gender ?? null)) {
    payload.gender = newGender
  }
  const newBirthday = (form.birthYear && form.birthMonth && form.birthDay)
    ? `${form.birthYear}-${String(form.birthMonth).padStart(2, '0')}-${String(form.birthDay).padStart(2, '0')}`
    : null
  if (newBirthday !== (profile.value.birthday ?? null)) {
    payload.birthday = newBirthday
  }

  if (Object.keys(payload).length === 0) {
    showToast('沒有變動')
    return
  }

  try {
    await updateMut.mutateAsync(payload)
  } catch (e) {
    apiError.value = (e as profileApi.ApiError).detail || '儲存失敗'
  }
}

function reset() {
  if (profile.value) loadFromProfile(profile.value)
  apiError.value = null
}

// ── Email / Password dialogs ─────────────────────────────────────────────────
const showChangeEmail = ref(false)
const showChangePassword = ref(false)

const resendMut = useMutation({
  mutationFn: profileApi.resendEmailChangeVerification,
  onSuccess: () => { showToast('驗證信已重新寄出') },
})

function onEmailChangeSuccess(newEmail: string) {
  showToast(`驗證信已寄至 ${newEmail}`)
  queryClient.invalidateQueries({ queryKey: ['user-profile'] })
}
</script>

<template>
  <main class="page">
    <RouterLink to="/profile" class="back-link" aria-label="會員中心">
      <ArrowLeft :size="14" />
      會員中心
    </RouterLink>

    <SectionMasthead
      no="22"
      chapter="Account"
      title="個人資料"
      caption="Personal Info"
    />

    <div v-if="profileQuery.isPending.value" class="state">
      <Loader2 :size="20" class="spin" /> 載入中…
    </div>
    <div v-else-if="profileQuery.isError.value" class="state error">
      <p>無法載入個人資料</p>
    </div>

    <template v-else-if="profile">
      <form class="form" @submit.prevent="save">
        <!-- Name -->
        <div class="field" :class="{ 'has-error': errors.name }">
          <label class="field-label" for="profile-name">姓名 <span class="req">*</span></label>
          <input
            id="profile-name"
            v-model="form.name"
            type="text"
            minlength="4"
            maxlength="40"
            placeholder="請輸入姓名（至少 4 字）"
            @blur="validate"
          />
          <p v-if="errors.name" class="field-error">{{ errors.name }}</p>
        </div>

        <!-- Email（不能直接編，需走變更流程）-->
        <div class="field">
          <label class="field-label">Email</label>
          <div class="field-readonly">
            <span>{{ profile.email }}</span>
            <button type="button" class="link-btn" @click="showChangeEmail = true">
              <Mail :size="12" :stroke-width="1.5" /> 變更
            </button>
          </div>
          <div v-if="profile.pending_email" class="pending-banner">
            <p>
              已寄驗證信至 <strong>{{ profile.pending_email }}</strong>，
              點信內連結即可完成變更（驗證前舊 Email 仍可登入）。
            </p>
            <button
              type="button"
              class="link-btn"
              :disabled="resendMut.isPending.value"
              @click="resendMut.mutate()"
            >
              <Loader2 v-if="resendMut.isPending.value" :size="12" class="spin" />
              <RefreshCcw v-else :size="12" :stroke-width="1.5" />
              重新寄送
            </button>
          </div>
        </div>

        <!-- Gender -->
        <div class="field">
          <label class="field-label" for="profile-gender">性別</label>
          <select id="profile-gender" v-model="form.gender" class="select">
            <option value="">不指定</option>
            <option value="female">女</option>
            <option value="male">男</option>
            <option value="other">其他</option>
          </select>
        </div>

        <!-- Birthday -->
        <div class="field" :class="{ 'has-error': errors.birthday }">
          <label class="field-label">生日</label>
          <div class="birthday-row">
            <select v-model.number="form.birthYear" class="select" aria-label="年">
              <option value="">年</option>
              <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}</option>
            </select>
            <select v-model.number="form.birthMonth" class="select" aria-label="月">
              <option value="">月</option>
              <option v-for="m in monthOptions" :key="m" :value="m">{{ m }}</option>
            </select>
            <select v-model.number="form.birthDay" class="select" aria-label="日">
              <option value="">日</option>
              <option v-for="d in dayOptions" :key="d" :value="d">{{ d }}</option>
            </select>
          </div>
          <p v-if="errors.birthday" class="field-error">{{ errors.birthday }}</p>
          <p v-else class="field-hint">三欄要嘛一起填，要嘛一起留空（選填）</p>
        </div>

        <!-- Password section -->
        <div class="field">
          <label class="field-label">密碼</label>
          <div class="field-readonly">
            <span class="muted">已設定</span>
            <button type="button" class="link-btn" @click="showChangePassword = true">
              <Mail :size="12" :stroke-width="1.5" /> 修改密碼
            </button>
          </div>
        </div>

        <!-- Actions -->
        <div class="actions">
          <p v-if="apiError" class="api-error">{{ apiError }}</p>
          <div class="actions-row">
            <button
              type="button"
              class="btn-ghost"
              :disabled="!isDirty || updateMut.isPending.value"
              @click="reset"
            >
              還原
            </button>
            <button
              type="submit"
              class="btn-primary"
              :disabled="!isDirty || updateMut.isPending.value"
            >
              <Loader2 v-if="updateMut.isPending.value" :size="14" class="spin" />
              <Check v-else :size="14" :stroke-width="1.5" />
              儲存變更
            </button>
          </div>
        </div>
      </form>
    </template>

    <Transition name="toast">
      <p v-if="savedToast" class="saved-toast" @click="savedToast = null">
        <Check :size="14" :stroke-width="2" /> {{ savedToast }}
      </p>
    </Transition>

    <ChangePasswordDialog
      :open="showChangePassword"
      @close="showChangePassword = false"
      @success="showToast('密碼已更新')"
    />
    <ChangeEmailDialog
      v-if="profile"
      :open="showChangeEmail"
      :current-email="profile.email"
      @close="showChangeEmail = false"
      @success="onEmailChangeSuccess"
    />
  </main>
</template>

<style scoped>
.page {
  max-width: 720px;
  margin: 0 auto;
  padding: 32px 24px 96px;
}

.back-link {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted); text-decoration: none;
  margin-bottom: 32px;
}
.back-link:hover { color: var(--color-accent-deep); }

.spin { animation: spin 900ms linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.state {
  display: flex; align-items: center; justify-content: center;
  gap: 12px; padding: 80px 16px; color: var(--color-ink-muted);
}
.state.error { color: var(--color-state-danger); }

.form {
  display: flex; flex-direction: column; gap: 28px;
  margin-top: 40px;
}

.field { display: flex; flex-direction: column; gap: 8px; }
.field-label {
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em;
  text-transform: uppercase; color: var(--color-ink-muted);
}
.req { color: var(--color-state-danger); margin-left: 4px; }

.field input[type="text"],
.field input[type="email"],
.select {
  width: 100%;
  padding: 11px 14px;
  border: 1px solid var(--color-line-subtle);
  background: var(--color-paper-surface);
  border-radius: var(--radius-xs);
  font: inherit; font-size: 14px;
  color: var(--color-ink-default);
}
.field input:focus, .select:focus {
  outline: none;
  border-color: var(--color-accent);
}

.field.has-error input,
.field.has-error .select {
  border-color: var(--color-state-danger);
}

.birthday-row { display: grid; grid-template-columns: 1.4fr 1fr 1fr; gap: 8px; }

.field-error {
  margin: 0; font-size: 12px;
  color: var(--color-state-danger);
  letter-spacing: 0.04em;
}
.field-hint {
  margin: 0; font-size: 11px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
}

.field-readonly {
  display: flex; align-items: center; justify-content: space-between;
  padding: 11px 14px;
  border: 1px solid var(--color-line-subtle);
  background: var(--color-paper-deep);
  border-radius: var(--radius-xs);
  color: var(--color-ink-strong);
  font-size: 14px;
}
.field-readonly .muted { color: var(--color-ink-muted); font-style: italic; }

.link-btn {
  display: inline-flex; align-items: center; gap: 6px;
  background: transparent; border: 0; cursor: pointer;
  padding: 4px 8px;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-accent);
}
.link-btn:hover { color: var(--color-accent-deep); }
.link-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.pending-banner {
  margin-top: 4px;
  padding: 12px 14px;
  background: var(--color-fresh-tint);
  border: 1px solid var(--color-fresh-soft);
  border-radius: var(--radius-xs);
  font-size: 13px; line-height: 1.7;
  color: var(--color-fresh);
  display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
  flex-wrap: wrap;
}
.pending-banner p { margin: 0; flex: 1; min-width: 200px; }
.pending-banner strong { font-weight: 500; color: var(--color-ink-strong); }

/* ── Actions ─────────────────────────────────────────────────────── */
.actions {
  margin-top: 16px;
  padding-top: 24px;
  border-top: 1px solid var(--color-line-subtle);
}
.api-error {
  font-size: 13px; color: var(--color-state-danger); margin: 0 0 12px;
}
.actions-row {
  display: flex; justify-content: flex-end; gap: 10px;
}
.btn-ghost,
.btn-primary {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 11px 24px;
  border-radius: var(--radius-xs);
  cursor: pointer;
  font-family: var(--font-cn-serif);
  font-size: 13px; letter-spacing: 0.04em;
}
.btn-ghost {
  background: transparent;
  border: 1px solid var(--color-line);
  color: var(--color-ink-default);
}
.btn-ghost:hover:not(:disabled) {
  border-color: var(--color-accent);
  color: var(--color-accent-deep);
}
.btn-primary {
  background: var(--color-ink-strong);
  color: var(--color-paper-canvas);
  border: 0;
}
.btn-primary:hover:not(:disabled) { background: var(--color-accent-deep); }
.btn-ghost:disabled, .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Toast ──────────────────────────────────────────────────────── */
.saved-toast {
  position: fixed; right: 32px; bottom: 32px; z-index: 1100;
  padding: 12px 18px;
  background: var(--color-ink-strong); color: var(--color-paper-canvas);
  border-radius: var(--radius-sm);
  font-family: var(--font-cn-serif); font-size: 13px; letter-spacing: 0.04em;
  display: inline-flex; align-items: center; gap: 8px;
  cursor: pointer;
  margin: 0;
  box-shadow: 0 8px 24px rgba(46, 40, 35, 0.18);
}

.toast-enter-active, .toast-leave-active { transition: opacity 200ms, transform 200ms; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(8px); }
</style>
