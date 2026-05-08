<script setup lang="ts">
// admin 端 ECpay CVS 地圖選店元件（與 store 端 ConvenienceStorePicker 邏輯一致）
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
  'selected': [info: { storeId: string; storeName: string; address: string; phone: string }]
}>()

// shipping_type → ECpay LogisticsSubType (C2C)
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
  store_outside: string
  extra_data: string
}

function handleMessage(e: MessageEvent) {
  const data = e.data as CvsSelectedPayload | null
  if (!data || data.type !== 'ecpay-cvs-selected') return

  opening.value = false
  stopClosedPoll()
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
  stopClosedPoll()
  if (popupRef.value && !popupRef.value.closed) {
    popupRef.value.close()
  }
})

let closedPollHandle: number | null = null
function stopClosedPoll() {
  if (closedPollHandle !== null) {
    clearInterval(closedPollHandle)
    closedPollHandle = null
  }
}

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
    return
  }

  stopClosedPoll()
  closedPollHandle = window.setInterval(() => {
    if (!popupRef.value || popupRef.value.closed) {
      opening.value = false
      stopClosedPoll()
    }
  }, 500)
}

function clearStore() {
  emit('update:storeId', '')
  emit('update:storeName', '')
  lastSelectedAddress.value = null
  lastSelectedPhone.value = null
}
</script>

<template>
  <div class="space-y-2">
    <template v-if="storeId && storeName">
      <div class="grid grid-cols-[28px_1fr_auto] gap-3 items-center px-3 py-2.5 bg-accent/[0.10] border border-accent/40 rounded-[var(--radius-xs)]">
        <span class="w-[28px] h-[28px] rounded-full inline-flex items-center justify-center bg-paper-surface border border-line-hairline text-accent">
          <Store :size="14" :stroke-width="1.5" />
        </span>
        <div class="min-w-0">
          <div class="text-[14px] text-ink-strong">{{ storeName }}</div>
          <div class="text-[11px] font-mono text-ink-muted">門市代碼 {{ storeId }}</div>
          <div v-if="lastSelectedAddress" class="text-[11px] text-ink-muted mt-0.5">{{ lastSelectedAddress }}</div>
        </div>
        <button
          type="button"
          class="w-7 h-7 rounded-[var(--radius-xs)] inline-flex items-center justify-center text-ink-muted hover:text-state-danger hover:border hover:border-state-danger transition-colors"
          @click="clearStore"
          aria-label="清除門市"
        >
          <X :size="14" :stroke-width="1.5" />
        </button>
      </div>
      <button
        type="button"
        class="inline-flex items-center gap-2 px-3 py-1.5 bg-transparent border border-line-hairline text-ink-default text-[12px] rounded-[var(--radius-xs)] cursor-pointer hover:bg-paper-subtle hover:border-accent hover:text-accent disabled:opacity-60 disabled:cursor-not-allowed self-start transition-colors"
        :disabled="opening"
        @click="openPicker"
      >
        <Loader2 v-if="opening" :size="13" :stroke-width="1.5" class="animate-spin" />
        <MapPin v-else :size="13" :stroke-width="1.5" />
        <span>{{ opening ? '正在開啟選店視窗…' : '重新選擇門市' }}</span>
      </button>
    </template>

    <button
      v-else
      type="button"
      class="inline-flex items-center gap-2 px-4 py-2.5 bg-paper-surface border border-dashed border-accent text-accent text-[13px] rounded-[var(--radius-xs)] cursor-pointer hover:bg-accent/[0.08] disabled:opacity-60 disabled:cursor-not-allowed self-start"
      :disabled="opening"
      @click="openPicker"
    >
      <Loader2 v-if="opening" :size="14" :stroke-width="1.5" class="animate-spin" />
      <MapPin v-else :size="14" :stroke-width="1.5" />
      <span>{{ opening ? '正在開啟選店視窗…' : '選擇門市' }}</span>
    </button>

    <p class="text-[11px] text-ink-muted">
      會跳出 ECpay 選店視窗，挑好門市後資料會自動帶回。
    </p>
    <p v-if="errorText" class="text-[12px] text-state-danger">{{ errorText }}</p>
  </div>
</template>
