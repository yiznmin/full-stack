<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query'
import { Loader2, MapPin, Store, Plus, Pencil, Trash2, Star } from 'lucide-vue-next'
import * as profileApi from '../api'
import type { ShippingProfile, ShippingProfileInput, ShippingType, ApiError } from '../api'
import ShippingProfileForm from '../components/ShippingProfileForm.vue'

const queryClient = useQueryClient()
const profilesQuery = useQuery({
  queryKey: ['shipping-profiles'],
  queryFn: profileApi.listShippingProfiles,
})

const profiles = computed(() => profilesQuery.data.value ?? [])
const isEmpty = computed(
  () => !profilesQuery.isPending.value && profiles.value.length === 0,
)

const editingId = ref<string | null>(null) // null = no form / 'new' = adding / uuid = editing
const showForm = computed(() => editingId.value !== null)
const editingProfile = computed<ShippingProfile | null>(() => {
  if (!editingId.value || editingId.value === 'new') return null
  return profiles.value.find((p) => p.id === editingId.value) ?? null
})

const apiError = ref<string | null>(null)

function openNew() {
  apiError.value = null
  editingId.value = 'new'
}

function openEdit(p: ShippingProfile) {
  apiError.value = null
  editingId.value = p.id
}

function cancelForm() {
  editingId.value = null
  apiError.value = null
}

const createMut = useMutation({
  mutationFn: profileApi.createShippingProfile,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['shipping-profiles'] })
    editingId.value = null
  },
})

const updateMut = useMutation({
  mutationFn: ({ id, data }: { id: string; data: ShippingProfileInput }) =>
    profileApi.updateShippingProfile(id, data),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['shipping-profiles'] })
    editingId.value = null
  },
})

const deleteMut = useMutation({
  mutationFn: profileApi.deleteShippingProfile,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['shipping-profiles'] })
  },
})

const setDefaultMut = useMutation({
  mutationFn: profileApi.setDefaultShippingProfile,
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['shipping-profiles'] })
  },
})

const submitting = computed(
  () => createMut.isPending.value || updateMut.isPending.value,
)

async function handleSubmit(data: ShippingProfileInput) {
  apiError.value = null
  // 第一筆收件資料自動設為預設
  const payload =
    editingId.value === 'new' && profiles.value.length === 0
      ? { ...data, is_default: true }
      : data
  try {
    if (editingId.value === 'new') {
      await createMut.mutateAsync(payload)
    } else if (editingId.value) {
      await updateMut.mutateAsync({ id: editingId.value, data: payload })
    }
  } catch (e) {
    const err = e as ApiError
    apiError.value = err.detail || '送出失敗，請稍後再試'
  }
}

async function remove(p: ShippingProfile) {
  if (!confirm(`確定刪除「${p.recipient_name}」的收件資料？`)) return
  try {
    await deleteMut.mutateAsync(p.id)
  } catch (e) {
    alert((e as ApiError).detail || '刪除失敗')
  }
}

async function setDefault(p: ShippingProfile) {
  if (p.is_default || setDefaultMut.isPending.value) return
  await setDefaultMut.mutateAsync(p.id)
}

function profileSummary(p: ShippingProfile): string {
  if (p.shipping_type === 'home') {
    return [p.city, p.district, p.address_detail].filter(Boolean).join('') || '宅配地址'
  }
  return p.store_name || `超商 ${p.store_id ?? ''}`
}

const SHIPPING_TYPE_LABEL: Record<ShippingType, string> = {
  home: '宅配到府',
  seven_eleven: '7-Eleven 取貨',
  family_mart: '全家取貨',
}
</script>

<template>
  <main class="page">
    <nav class="breadcrumb">
      <RouterLink to="/profile">會員中心</RouterLink>
      <span>/</span>
      <span class="current">收件資料</span>
    </nav>

    <header class="head">
      <span class="eyebrow">— Shipping Profiles —</span>
      <h1 class="title">收件資料</h1>
      <p class="lede">
        管理常用的宅配地址與超商門市，結帳時可直接挑選。
      </p>
    </header>

    <div v-if="profilesQuery.isPending.value" class="loading">
      <Loader2 :size="22" />
    </div>

    <template v-else>
      <!-- 新增按鈕 / 列表 -->
      <section class="actions" v-if="!showForm">
        <button type="button" class="add-btn" @click="openNew">
          <Plus :size="14" />
          <span>新增收件資料</span>
        </button>
      </section>

      <!-- Form -->
      <section v-if="showForm" class="form-block">
        <div class="form-head">
          <h2 class="form-title">
            {{ editingId === 'new' ? '新增收件資料' : '編輯收件資料' }}
          </h2>
          <button type="button" class="form-cancel" @click="cancelForm">取消</button>
        </div>

        <ShippingProfileForm
          :initial="editingProfile"
          :submitting="submitting"
          :error-text="apiError"
          @submit="handleSubmit"
          @cancel="cancelForm"
        />
      </section>

      <!-- Empty -->
      <section v-else-if="isEmpty" class="empty">
        <MapPin class="empty-icon" />
        <h2 class="empty-title">還沒有收件資料</h2>
        <p class="empty-hint">新增第一筆收件資料，結帳時就可以直接挑選。</p>
      </section>

      <!-- List -->
      <section v-else class="list">
        <article
          v-for="p in profiles"
          :key="p.id"
          class="profile"
          :class="{ 'profile-default': p.is_default }"
        >
          <div class="profile-icon">
            <MapPin v-if="p.shipping_type === 'home'" :size="14" />
            <Store v-else :size="14" />
          </div>
          <div class="profile-info">
            <div class="profile-head">
              <span class="profile-name">{{ p.recipient_name }}</span>
              <span v-if="p.is_default" class="profile-badge">
                <Star :size="10" :fill="'currentColor'" :stroke="'currentColor'" />
                預設
              </span>
              <span class="profile-type">{{ SHIPPING_TYPE_LABEL[p.shipping_type] }}</span>
            </div>
            <div class="profile-phone">{{ p.phone }}</div>
            <div class="profile-addr">{{ profileSummary(p) }}</div>
          </div>
          <div class="profile-actions">
            <button
              v-if="!p.is_default"
              type="button"
              class="btn-icon"
              :disabled="setDefaultMut.isPending.value"
              @click="setDefault(p)"
              title="設為預設"
            >
              <Star :size="14" />
            </button>
            <button
              type="button"
              class="btn-icon"
              @click="openEdit(p)"
              title="編輯"
            >
              <Pencil :size="14" />
            </button>
            <button
              type="button"
              class="btn-icon btn-icon-danger"
              :disabled="deleteMut.isPending.value"
              @click="remove(p)"
              title="刪除"
            >
              <Trash2 :size="14" />
            </button>
          </div>
        </article>
      </section>
    </template>
  </main>
</template>

<style scoped>
.page {
  max-width: 880px;
  margin: 0 auto;
  padding: 56px 56px 96px;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  margin-bottom: 24px;
}
.breadcrumb a { color: inherit; text-decoration: none; transition: color 150ms; }
.breadcrumb a:hover { color: var(--color-accent); }
.breadcrumb .current { color: var(--color-ink-default); }

.head { margin-bottom: 36px; }
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
  font-size: 36px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 12px 0 8px;
}
.lede {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 14px;
  line-height: 1.95;
  color: var(--color-ink-default);
  margin: 0;
  letter-spacing: 0.04em;
}

.loading {
  display: flex;
  justify-content: center;
  padding: 64px 0;
  color: var(--color-ink-muted);
}
.loading :deep(svg),
.spin {
  animation: spin 1s linear infinite;
  stroke: currentColor; stroke-width: 1.5; fill: none;
}
.spin { width: 14px; height: 14px; }
@keyframes spin { to { transform: rotate(360deg); } }

.actions { margin-bottom: 24px; }
.add-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-body);
  font-size: 12px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  padding: 12px 22px;
  background: var(--color-ink-strong);
  color: var(--color-paper-canvas);
  border: 1px solid var(--color-ink-strong);
  cursor: pointer;
  transition: background 200ms, border-color 200ms;
}
.add-btn:hover {
  background: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}
.add-btn :deep(svg) {
  stroke: currentColor; stroke-width: 1.75; fill: none;
}

/* Empty */
.empty {
  text-align: center;
  padding: 80px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.empty-icon {
  width: 36px; height: 36px;
  stroke: var(--color-ink-muted);
  stroke-width: 1.25;
  fill: none;
  margin-bottom: 20px;
  opacity: 0.6;
}
.empty-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 24px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 8px;
}
.empty-hint {
  font-size: 13px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  margin: 0;
}

/* List */
.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.profile {
  display: grid;
  grid-template-columns: 32px 1fr auto;
  gap: 18px;
  align-items: center;
  padding: 20px 24px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-xs);
  transition: border-color 150ms;
}
.profile:hover {
  border-color: var(--color-line);
}
.profile-default {
  border-color: var(--color-accent);
  background: var(--color-accent-tint);
}

.profile-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line-subtle);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-accent);
}
.profile-icon :deep(svg) {
  stroke: currentColor; stroke-width: 1.5; fill: none;
}

.profile-info { min-width: 0; }
.profile-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}
.profile-name {
  font-family: var(--font-cn-serif);
  font-weight: 400;
  font-size: 16px;
  color: var(--color-ink-strong);
  letter-spacing: 0.04em;
}
.profile-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-fresh);
  border: 1px solid var(--color-fresh);
  padding: 1px 6px;
  border-radius: var(--radius-xs);
  font-weight: 500;
}
.profile-badge :deep(svg) {
  stroke: currentColor; stroke-width: 1.5;
}
.profile-type {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}
.profile-phone {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.06em;
  color: var(--color-ink-muted);
  margin-bottom: 4px;
}
.profile-addr {
  font-size: 13px;
  color: var(--color-ink-default);
  letter-spacing: 0.02em;
}

.profile-actions {
  display: flex;
  gap: 4px;
}
.btn-icon {
  width: 32px;
  height: 32px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-xs);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-ink-muted);
  transition: color 150ms, background 150ms, border-color 150ms;
}
.btn-icon:hover:not(:disabled) {
  color: var(--color-accent);
  background: var(--color-paper-canvas);
  border-color: var(--color-line-subtle);
}
.btn-icon:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-icon-danger:hover:not(:disabled) {
  color: var(--color-state-danger);
  border-color: var(--color-state-danger);
}
.btn-icon :deep(svg) {
  stroke: currentColor; stroke-width: 1.5; fill: none;
}

/* Form */
.form-block {
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-sm);
  padding: 36px 36px 32px;
  margin-bottom: 24px;
}
.form-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 28px;
}
.form-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 22px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0;
}
.form-cancel {
  background: transparent;
  border: none;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  cursor: pointer;
}
.form-cancel:hover { color: var(--color-state-danger); }

.form { display: flex; flex-direction: column; gap: 18px; }
.field { display: flex; flex-direction: column; gap: 6px; }
.field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }

.label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-default);
}
.input {
  font-family: var(--font-body);
  font-size: 14px;
  color: var(--color-ink-strong);
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  padding: 11px 13px;
  outline: none;
  transition: border-color 150ms, box-shadow 150ms;
}
.input:focus {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px var(--color-accent-tint);
}

.radio-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
.radio-card {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: border-color 150ms;
  font-size: 13px;
}
.radio-card input { display: none; }
.radio-card:hover { border-color: var(--color-accent-soft); }
.radio-active { border-color: var(--color-accent) !important; background: var(--color-accent-tint); }
.radio-icon {
  width: 22px; height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-accent);
}
.radio-icon :deep(svg) { stroke: currentColor; stroke-width: 1.5; fill: none; }
.radio-text { color: var(--color-ink-strong); letter-spacing: 0.04em; }

.hint {
  font-size: 11px;
  color: var(--color-ink-muted);
  margin: -4px 0 0;
  letter-spacing: 0.04em;
}

.check-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--color-ink-default);
  letter-spacing: 0.04em;
  cursor: pointer;
  user-select: none;
}
.check-row input { width: 16px; height: 16px; accent-color: var(--color-accent); }

.api-err {
  margin: 0;
  padding: 10px 12px;
  font-size: 12px;
  color: var(--color-state-danger);
  background: rgba(123, 46, 64, 0.06);
  border: 1px solid var(--color-state-danger);
  border-radius: var(--radius-xs);
  letter-spacing: 0.04em;
}

.form-foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}
.btn-ghost {
  height: 44px;
  padding: 0 24px;
  background: transparent;
  border: 1px solid var(--color-line);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: uppercase;
  color: var(--color-ink-default);
  cursor: pointer;
  transition: border-color 150ms, color 150ms;
}
.btn-ghost:hover {
  border-color: var(--color-accent);
  color: var(--color-accent);
}
.btn-primary {
  height: 44px;
  padding: 0 28px;
  background: var(--color-ink-strong);
  border: 1px solid var(--color-ink-strong);
  font-family: var(--font-body);
  font-size: 11px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--color-paper-canvas);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  transition: background 200ms, border-color 200ms;
}
.btn-primary:hover:not(:disabled) {
  background: var(--color-accent-deep);
  border-color: var(--color-accent-deep);
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

@media (max-width: 1023px) {
  .page { padding: 40px 32px 64px; }
  .form-block { padding: 28px 24px 24px; }
  .field-row { grid-template-columns: 1fr; }
  .radio-row { grid-template-columns: 1fr; }
}
@media (max-width: 767px) {
  .page { padding: 32px 24px 48px; }
  .profile {
    grid-template-columns: 28px 1fr;
    grid-template-rows: auto auto;
  }
  .profile-icon { grid-row: 1; }
  .profile-info { grid-row: 1; grid-column: 2; }
  .profile-actions { grid-row: 2; grid-column: 1 / 3; justify-self: end; }
}
</style>
