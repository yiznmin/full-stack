<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { Store, MapPin, Loader2, X } from 'lucide-vue-next'
import type { ShippingType } from '../api'

const props = defineProps<{
  shippingType: ShippingType  // 'seven_eleven' | 'family_mart' (home 不會走這裡)
  storeId: string | null
  storeName: string | null
}>()

const emit = defineEmits<{
  'update:storeId': [value: string]
  'update:storeName': [value: string]
  /** 額外資訊（地址、電話）— 父層可選擇要不要保存 */
  'selected': [info: { storeId: string; storeName: string; address: string; phone: string }]
}>()

// shipping_type → ECpay LogisticsSubType (C2C 個人寄件，新商家預設選這個)
const SUB_TYPE_MAP: Record<string, string> = {
  seven_eleven: 'UNIMARTC2C',
  family_mart: 'FAMIC2C',
}

const opening = ref(false)
const errorText = ref<string | null>(null)
const popupRef = ref<Window | null>(null)
const lastSelectedAddress = ref<string | null>(null)
const lastSelectedPhone = ref<string | null>(null)

interface CvsSelectedPayload {
  type: 'ecpay-cvs-selected'
  ok: boolean
  logistics_sub_type: string
  store_id: string
  store_name: string
  store_address: string
  store_phone: string
  store_outside: string  // '0' / '1' / ''
  extra_data: string
}

function handleMessage(e: MessageEvent) {
  const data = e.data as CvsSelectedPayload | null
  if (!data || data.type !== 'ecpay-cvs-selected') return

  opening.value = false
  if (!data.ok || !data.store_id) {
    errorText.value = '選店失敗或簽章驗證未通過，請再試一次'
    return
  }

  errorText.value = null
  lastSelectedAddress.value = data.store_address
  lastSelectedPhone.value = data.store_phone
  emit('update:storeId', data.store_id)
  emit('update:storeName', data.store_name)
  emit('selected', {
    storeId: data.store_id,
    storeName: data.store_name,
    address: data.store_address,
    phone: data.store_phone,
  })
}

window.addEventListener('message', handleMessage)
onBeforeUnmount(() => {
  window.removeEventListener('message', handleMessage)
  if (popupRef.value && !popupRef.value.closed) {
    popupRef.value.close()
  }
})

function openPicker() {
  errorText.value = null
  const subType = SUB_TYPE_MAP[props.shippingType]
  if (!subType) {
    errorText.value = `不支援的配送方式：${props.shippingType}`
    return
  }
  const url = `/api/v1/logistics/cvs-map?type=${encodeURIComponent(subType)}`
  const features = 'width=900,height=700,resizable=yes,scrollbars=yes'
  opening.value = true
  popupRef.value = window.open(url, 'ecpay-cvs-picker', features)
  if (!popupRef.value) {
    opening.value = false
    errorText.value = '無法開啟選店視窗，請允許彈出視窗後再試'
  }
}

function clearStore() {
  emit('update:storeId', '')
  emit('update:storeName', '')
  lastSelectedAddress.value = null
  lastSelectedPhone.value = null
}
</script>

<template>
  <div class="cvs-picker">
    <div v-if="storeId && storeName" class="selected-card">
      <div class="selected-icon">
        <Store :size="14" />
      </div>
      <div class="selected-info">
        <div class="selected-name">{{ storeName }}</div>
        <div class="selected-meta">門市代碼 {{ storeId }}</div>
        <div v-if="lastSelectedAddress" class="selected-addr">{{ lastSelectedAddress }}</div>
      </div>
      <button type="button" class="clear-btn" @click="clearStore" aria-label="清除門市">
        <X :size="14" />
      </button>
    </div>

    <button
      v-else
      type="button"
      class="open-btn"
      :disabled="opening"
      @click="openPicker"
    >
      <Loader2 v-if="opening" :size="14" class="spin" />
      <MapPin v-else :size="14" />
      <span>{{ opening ? '正在開啟選店視窗…' : '選擇門市' }}</span>
    </button>

    <p class="hint">
      會跳出 ECpay 選店視窗，挑好門市後資料會自動帶回。
    </p>
    <p v-if="errorText" class="err">{{ errorText }}</p>
  </div>
</template>

<style scoped>
.cvs-picker {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.open-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px;
  background: var(--color-paper-canvas);
  border: 1px dashed var(--color-accent);
  color: var(--color-accent);
  font-family: var(--font-body);
  font-size: 13px;
  letter-spacing: 0.04em;
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: background 150ms, border-color 150ms;
  align-self: flex-start;
}
.open-btn:hover:not(:disabled) {
  background: var(--color-accent-tint);
  border-color: var(--color-accent-deep);
}
.open-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.open-btn :deep(svg) { stroke: currentColor; stroke-width: 1.5; fill: none; }

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.selected-card {
  display: grid;
  grid-template-columns: 28px 1fr auto;
  gap: 12px;
  align-items: center;
  padding: 14px 16px;
  background: var(--color-accent-tint);
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-xs);
}

.selected-icon {
  width: 28px; height: 28px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line-subtle);
  color: var(--color-accent);
}
.selected-icon :deep(svg) { stroke: currentColor; stroke-width: 1.5; fill: none; }

.selected-info { min-width: 0; }
.selected-name {
  font-family: var(--font-cn-serif);
  font-size: 15px;
  color: var(--color-ink-strong);
  letter-spacing: 0.04em;
  margin-bottom: 2px;
}
.selected-meta {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.06em;
  color: var(--color-ink-muted);
}
.selected-addr {
  font-size: 12px;
  color: var(--color-ink-muted);
  letter-spacing: 0.02em;
  margin-top: 2px;
  line-height: 1.5;
}

.clear-btn {
  width: 28px; height: 28px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-xs);
  color: var(--color-ink-muted);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: color 150ms, border-color 150ms;
}
.clear-btn:hover {
  color: var(--color-state-danger);
  border-color: var(--color-state-danger);
}
.clear-btn :deep(svg) { stroke: currentColor; stroke-width: 1.5; fill: none; }

.hint {
  font-size: 11px;
  color: var(--color-ink-muted);
  margin: 0;
  letter-spacing: 0.04em;
}

.err {
  font-size: 12px;
  color: var(--color-state-danger);
  margin: 0;
  letter-spacing: 0.04em;
}
</style>
