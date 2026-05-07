<script setup lang="ts">
import { ref, watch } from 'vue'
import { Loader2, MapPin, Store } from 'lucide-vue-next'
import TaiwanAddressPicker from './TaiwanAddressPicker.vue'
import ConvenienceStorePicker from './ConvenienceStorePicker.vue'
import { useAuthStore } from '@/features/auth/store'
import type { ShippingProfile, ShippingProfileInput, ShippingType } from '../api'

const props = defineProps<{
  initial?: ShippingProfile | null
  submitting: boolean
  errorText?: string | null
  /** 結帳頁用 compact (隱藏「設為預設」勾選，因為新增本來就會作為當下選用) */
  compact?: boolean
}>()

const emit = defineEmits<{
  submit: [data: ShippingProfileInput]
  cancel: []
}>()

const authStore = useAuthStore()

const initialInput = (): ShippingProfileInput => ({
  shipping_type: 'home',
  recipient_name: '',
  phone: '',
  email: authStore.user?.email ?? null,
  city: '',
  district: '',
  address_detail: '',
  store_id: null,
  store_name: null,
  is_default: false,
})

const form = ref<ShippingProfileInput>(initialInput())

watch(
  () => props.initial,
  (p) => {
    if (p) {
      form.value = {
        shipping_type: p.shipping_type,
        recipient_name: p.recipient_name,
        phone: p.phone,
        email: p.email,
        city: p.city,
        district: p.district,
        address_detail: p.address_detail,
        store_id: p.store_id,
        store_name: p.store_name,
        is_default: p.is_default,
      }
    } else {
      form.value = initialInput()
    }
  },
  { immediate: true },
)

const SHIPPING_TYPE_LABEL: Record<ShippingType, string> = {
  home: '宅配到府',
  seven_eleven: '7-Eleven 取貨',
  family_mart: '全家取貨',
}

function onSubmit() {
  // 同步超商預設名稱
  if (form.value.shipping_type !== 'home' && !form.value.store_name) {
    form.value.store_name = form.value.shipping_type === 'seven_eleven' ? '7-Eleven' : '全家便利商店'
  }
  emit('submit', { ...form.value })
}
</script>

<template>
  <form class="form" @submit.prevent="onSubmit" novalidate>
    <!-- 配送方式 -->
    <div class="field">
      <label class="label">配送方式</label>
      <div class="radio-row">
        <label
          v-for="t in (['home', 'seven_eleven', 'family_mart'] as ShippingType[])"
          :key="t"
          class="radio-card"
          :class="{ 'radio-active': form.shipping_type === t }"
        >
          <input v-model="form.shipping_type" type="radio" :value="t" />
          <span class="radio-icon">
            <MapPin v-if="t === 'home'" :size="14" />
            <Store v-else :size="14" />
          </span>
          <span class="radio-text">{{ SHIPPING_TYPE_LABEL[t] }}</span>
        </label>
      </div>
    </div>

    <!-- 收件人 + 電話 -->
    <div class="field-row">
      <div class="field">
        <label class="label" for="spf-name">收件人</label>
        <input
          id="spf-name"
          v-model="form.recipient_name"
          type="text"
          class="input"
          required
          maxlength="30"
          placeholder="姓名"
        />
      </div>
      <div class="field">
        <label class="label" for="spf-phone">電話</label>
        <input
          id="spf-phone"
          v-model="form.phone"
          type="tel"
          class="input"
          required
          pattern="09\d{8}"
          placeholder="09xxxxxxxx"
        />
      </div>
    </div>

    <!-- 宅配欄位 -->
    <template v-if="form.shipping_type === 'home'">
      <TaiwanAddressPicker
        v-model:county="form.city"
        v-model:district="form.district"
      />
      <div class="field">
        <label class="label" for="spf-addr">地址</label>
        <input
          id="spf-addr"
          v-model="form.address_detail"
          type="text"
          class="input"
          required
          placeholder="例：松仁路 100 號 5 樓"
        />
      </div>
    </template>

    <!-- 超商欄位 -->
    <template v-else>
      <ConvenienceStorePicker
        :shipping-type="form.shipping_type"
        :store-id="form.store_id"
        :store-name="form.store_name"
        @update:store-id="(v: string) => form.store_id = v"
        @update:store-name="(v: string) => form.store_name = v"
      />
    </template>

    <!-- Email -->
    <div class="field">
      <label class="label" for="spf-email">Email（可選）</label>
      <input
        id="spf-email"
        v-model="form.email"
        type="email"
        class="input"
        placeholder="出貨通知用"
      />
      <p
        v-if="authStore.user?.email && form.email === authStore.user.email"
        class="hint"
      >
        已帶入帳號 Email，可改成其他收件信箱。
      </p>
    </div>

    <!-- 設為預設（compact 模式隱藏） -->
    <label v-if="!compact" class="check-row">
      <input v-model="form.is_default" type="checkbox" />
      <span>設為預設收件資料</span>
    </label>

    <p v-if="errorText" class="api-err">{{ errorText }}</p>

    <div class="form-foot">
      <button type="button" class="btn-ghost" @click="emit('cancel')">取消</button>
      <button type="submit" class="btn-primary" :disabled="submitting">
        <Loader2 v-if="submitting" class="spin" />
        <span>{{ submitting ? '送出中...' : (initial ? '儲存' : '新增') }}</span>
      </button>
    </div>
  </form>
</template>

<style scoped>
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

.spin {
  width: 14px;
  height: 14px;
  animation: spin 1s linear infinite;
  stroke: currentColor;
  stroke-width: 1.5;
  fill: none;
}
@keyframes spin { to { transform: rotate(360deg); } }

@media (max-width: 1023px) {
  .field-row { grid-template-columns: 1fr; }
  .radio-row { grid-template-columns: 1fr; }
}
</style>
