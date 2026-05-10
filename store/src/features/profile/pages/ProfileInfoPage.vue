<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { ArrowLeft, Check, Edit2, Loader2, Mail, RefreshCcw } from 'lucide-vue-next'
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

// Edit state
const editingName = ref(false)
const nameInput = ref('')
const genderInput = ref<Gender | ''>('')
const birthYear = ref<number | ''>('')
const birthMonth = ref<number | ''>('')
const birthDay = ref<number | ''>('')

// Sync inputs from server data on load
watch(profile, (p) => {
  if (!p) return
  nameInput.value = p.name
  genderInput.value = p.gender ?? ''
  if (p.birthday) {
    const [y, m, d] = p.birthday.split('-').map(Number)
    birthYear.value = y
    birthMonth.value = m
    birthDay.value = d
  } else {
    birthYear.value = ''
    birthMonth.value = ''
    birthDay.value = ''
  }
}, { immediate: true })

// Year / Month / Day options
const currentYear = new Date().getFullYear()
const yearOptions = Array.from({ length: 100 }, (_, i) => currentYear - i)
const monthOptions = Array.from({ length: 12 }, (_, i) => i + 1)
const dayOptions = computed(() => {
  if (!birthYear.value || !birthMonth.value) return Array.from({ length: 31 }, (_, i) => i + 1)
  const lastDay = new Date(Number(birthYear.value), Number(birthMonth.value), 0).getDate()
  return Array.from({ length: lastDay }, (_, i) => i + 1)
})

const updateMut = useMutation({
  mutationFn: (payload: UpdateProfilePayload) => profileApi.updateProfile(payload),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['user-profile'] })
    showSavedToast()
  },
})

const apiError = ref<string | null>(null)
const savedToast = ref(false)
let savedToastTimer: ReturnType<typeof setTimeout> | null = null

function showSavedToast() {
  savedToast.value = true
  if (savedToastTimer) clearTimeout(savedToastTimer)
  savedToastTimer = setTimeout(() => { savedToast.value = false }, 2000)
}

async function saveName() {
  if (!nameInput.value.trim()) {
    apiError.value = '姓名不可為空'
    return
  }
  if (nameInput.value.length < 4) {
    apiError.value = '姓名最少 4 個字元'
    return
  }
  apiError.value = null
  try {
    await updateMut.mutateAsync({ name: nameInput.value.trim() })
    editingName.value = false
  } catch (e) {
    apiError.value = (e as profileApi.ApiError).detail || '姓名更新失敗'
  }
}

async function saveGender() {
  apiError.value = null
  try {
    await updateMut.mutateAsync({
      gender: genderInput.value === '' ? null : genderInput.value as Gender,
    })
  } catch (e) {
    apiError.value = (e as profileApi.ApiError).detail || '性別更新失敗'
  }
}

const birthdayString = computed<string | null>(() => {
  if (birthYear.value === '' || birthMonth.value === '' || birthDay.value === '') return null
  const m = String(birthMonth.value).padStart(2, '0')
  const d = String(birthDay.value).padStart(2, '0')
  return `${birthYear.value}-${m}-${d}`
})

async function saveBirthday() {
  apiError.value = null
  try {
    await updateMut.mutateAsync({ birthday: birthdayString.value })
  } catch (e) {
    apiError.value = (e as profileApi.ApiError).detail || '生日更新失敗'
  }
}

// Email
const showChangeEmail = ref(false)
const showChangePassword = ref(false)
const emailToastText = ref<string | null>(null)

const resendMut = useMutation({
  mutationFn: profileApi.resendEmailChangeVerification,
  onSuccess: () => { emailToastText.value = '驗證信已重新寄出' },
})

function onEmailChangeSuccess(newEmail: string) {
  emailToastText.value = `驗證信已寄至 ${newEmail}`
  queryClient.invalidateQueries({ queryKey: ['user-profile'] })
}

const GENDER_LABEL: Record<Gender, string> = {
  female: '女',
  male: '男',
  other: '其他',
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

    <nav class="sub-nav">
      <RouterLink to="/profile" class="sub-link" exact-active-class="is-active">概覽</RouterLink>
      <RouterLink to="/profile/info" class="sub-link" active-class="is-active">個人資料</RouterLink>
      <RouterLink to="/profile/shipping" class="sub-link" active-class="is-active">收件資料</RouterLink>
      <RouterLink to="/profile/coupons" class="sub-link" active-class="is-active">折扣券錢包</RouterLink>
    </nav>

    <div v-if="profileQuery.isPending.value" class="state">
      <Loader2 :size="20" class="spin" /> 載入中…
    </div>
    <div v-else-if="profileQuery.isError.value" class="state error">
      <p>無法載入個人資料</p>
    </div>

    <template v-else-if="profile">
      <section class="form">
        <!-- Name -->
        <div class="field">
          <label class="field-label">姓名</label>
          <div v-if="!editingName" class="field-readonly">
            <span>{{ profile.name }}</span>
            <button class="link-btn" @click="editingName = true">
              <Edit2 :size="12" :stroke-width="1.5" /> 修改
            </button>
          </div>
          <div v-else class="field-edit">
            <input v-model="nameInput" type="text" minlength="4" autofocus />
            <button class="btn-ghost-sm" @click="editingName = false; nameInput = profile.name">取消</button>
            <button class="btn-primary-sm" :disabled="updateMut.isPending.value" @click="saveName">
              <Loader2 v-if="updateMut.isPending.value" :size="12" class="spin" />
              儲存
            </button>
          </div>
        </div>

        <!-- Email -->
        <div class="field">
          <label class="field-label">Email</label>
          <div class="field-readonly">
            <span>{{ profile.email }}</span>
            <button class="link-btn" @click="showChangeEmail = true">
              <Mail :size="12" :stroke-width="1.5" /> 變更
            </button>
          </div>
          <div v-if="profile.pending_email" class="pending-banner">
            <p>
              已寄驗證信至 <strong>{{ profile.pending_email }}</strong>，
              點信內連結即可完成變更（驗證前舊 Email 仍可登入）。
            </p>
            <button
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
          <label class="field-label">性別</label>
          <div class="field-edit-inline">
            <select v-model="genderInput" class="select" @change="saveGender">
              <option value="">不指定</option>
              <option value="female">女</option>
              <option value="male">男</option>
              <option value="other">其他</option>
            </select>
          </div>
        </div>

        <!-- Birthday (3-段 select) -->
        <div class="field">
          <label class="field-label">生日</label>
          <div class="field-edit-inline birthday-row">
            <select v-model.number="birthYear" class="select" @change="saveBirthday">
              <option value="">年</option>
              <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}</option>
            </select>
            <select v-model.number="birthMonth" class="select" @change="saveBirthday">
              <option value="">月</option>
              <option v-for="m in monthOptions" :key="m" :value="m">{{ m }}</option>
            </select>
            <select v-model.number="birthDay" class="select" @change="saveBirthday">
              <option value="">日</option>
              <option v-for="d in dayOptions" :key="d" :value="d">{{ d }}</option>
            </select>
          </div>
        </div>

        <!-- Password -->
        <div class="field">
          <label class="field-label">密碼</label>
          <div class="field-readonly">
            <span class="muted">已設定（最後變更時間略）</span>
            <button class="link-btn" @click="showChangePassword = true">
              <Edit2 :size="12" :stroke-width="1.5" /> 修改密碼
            </button>
          </div>
        </div>

        <p v-if="apiError" class="error">{{ apiError }}</p>
      </section>
    </template>

    <Transition name="toast">
      <p v-if="savedToast" class="saved-toast">
        <Check :size="14" :stroke-width="2" /> 已儲存
      </p>
    </Transition>

    <Transition name="toast">
      <p v-if="emailToastText" class="saved-toast" @click="emailToastText = null">
        <Mail :size="14" :stroke-width="1.5" /> {{ emailToastText }}
      </p>
    </Transition>

    <ChangePasswordDialog
      :open="showChangePassword"
      @close="showChangePassword = false"
      @success="emailToastText = '密碼已更新'"
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
  max-width: 880px;
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

.state {
  display: flex; align-items: center; justify-content: center;
  gap: 12px; padding: 80px 16px; color: var(--color-ink-muted);
}
.state.error { color: var(--color-state-danger); }

.spin { animation: spin 900ms linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.sub-nav {
  display: flex; gap: 24px;
  margin: 32px 0 40px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-line-subtle);
}
.sub-link {
  font-family: var(--font-cn-serif); font-weight: 300;
  font-size: 14px; letter-spacing: 0.06em;
  color: var(--color-ink-muted); text-decoration: none;
  padding-bottom: 12px; margin-bottom: -13px;
  border-bottom: 1px solid transparent;
  transition: color 150ms, border-color 150ms;
}
.sub-link:hover { color: var(--color-accent-deep); }
.sub-link.is-active {
  color: var(--color-ink-strong);
  border-bottom-color: var(--color-accent);
}

.form { display: flex; flex-direction: column; gap: 28px; }

.field { display: flex; flex-direction: column; gap: 10px; }
.field-label {
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em;
  text-transform: uppercase; color: var(--color-ink-muted);
}

.field-readonly {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-line-subtle);
}
.field-readonly span { font-size: 15px; color: var(--color-ink-strong); letter-spacing: 0.04em; }
.field-readonly .muted { color: var(--color-ink-muted); }

.field-edit {
  display: flex; align-items: center; gap: 8px;
}
.field-edit input {
  flex: 1; padding: 9px 12px;
  border: 1px solid var(--color-accent);
  background: var(--color-paper-canvas);
  border-radius: var(--radius-xs);
  font: inherit; font-size: 14px;
  color: var(--color-ink-default);
}
.field-edit input:focus { outline: none; }

.field-edit-inline { display: flex; gap: 8px; }
.birthday-row .select { flex: 1; }

.select {
  padding: 9px 12px;
  border: 1px solid var(--color-line-subtle);
  background: var(--color-paper-surface);
  border-radius: var(--radius-xs);
  font: inherit; font-size: 14px;
  color: var(--color-ink-default);
  cursor: pointer;
  appearance: none;
}
.select:focus { outline: none; border-color: var(--color-accent); }

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

.btn-ghost-sm {
  padding: 7px 14px; border: 1px solid var(--color-line);
  background: transparent; border-radius: var(--radius-xs);
  cursor: pointer; font-family: var(--font-cn-serif); font-size: 12px;
  color: var(--color-ink-default);
}
.btn-ghost-sm:hover { border-color: var(--color-accent); color: var(--color-accent-deep); }

.btn-primary-sm {
  padding: 7px 16px; border: 0;
  background: var(--color-ink-strong); color: var(--color-paper-canvas);
  border-radius: var(--radius-xs); cursor: pointer;
  font-family: var(--font-cn-serif); font-size: 12px;
  display: inline-flex; align-items: center; gap: 6px;
}
.btn-primary-sm:hover { background: var(--color-accent-deep); }
.btn-primary-sm:disabled { opacity: 0.5; cursor: not-allowed; }

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

.error {
  font-size: 12px; color: var(--color-state-danger); margin: 0;
}

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
