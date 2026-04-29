<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Loader2,
  Plus,
  Pencil,
  Trash2,
  BarChart3,
  Send,
  Tag,
  AlertTriangle,
} from 'lucide-vue-next'

import PageHeader from '@/shared/components/PageHeader.vue'
import Card from '@/shared/ui/Card.vue'
import Button from '@/shared/ui/Button.vue'
import Select from '@/shared/ui/Select.vue'
import Input from '@/shared/ui/Input.vue'
import AppDataTable, { type Column } from '@/shared/components/AppDataTable.vue'

import DiscountsTabs from '../components/DiscountsTabs.vue'
import EditConfigDialog from '../components/EditConfigDialog.vue'
import PromoCodeDialog from '../components/PromoCodeDialog.vue'
import IssueCouponsDialog from '../components/IssueCouponsDialog.vue'
import {
  useCouponConfigsQuery,
  useCreateAutoCheckoutMutation,
  useCreatePromoCodeMutation,
  useDeleteCouponConfigMutation,
  useDeletePromoCodeMutation,
  useIssueCouponsMutation,
  usePatchCouponConfigMutation,
  usePromoCodesQuery,
  useUpdatePromoCodeMutation,
  useUserCouponsQuery,
} from '../queries'
import {
  COUPON_TYPE_LABEL,
  formatDiscount,
  type AdminUserCoupon,
  type CouponConfig,
  type CouponType,
  type PromoCode,
} from '../api'

const route = useRoute()
const router = useRouter()

const activeTab = computed(() => {
  const t = route.query.tab
  if (typeof t === 'string' && ['configs', 'promo', 'users'].includes(t)) return t
  return 'configs'
})

// ── Configs ───────────────────────────────────────────────────────────
const { data: configsData, isLoading: configsLoading, isError: configsError } = useCouponConfigsQuery()
const patchMut = usePatchCouponConfigMutation()
const createAutoMut = useCreateAutoCheckoutMutation()
const deleteConfigMut = useDeleteCouponConfigMutation()

const editConfigOpen = ref(false)
const editingConfig = ref<CouponConfig | null>(null)
const isCreatingAutoCheckout = ref(false)
const apiError = ref<string | null>(null)

const systemConfigs = computed(() =>
  (configsData.value?.items ?? []).filter((c) => c.coupon_type !== 'auto_checkout'),
)
const autoCheckoutConfigs = computed(() =>
  (configsData.value?.items ?? []).filter((c) => c.coupon_type === 'auto_checkout'),
)

function openEditConfig(c: CouponConfig) {
  editingConfig.value = c
  isCreatingAutoCheckout.value = false
  editConfigOpen.value = true
}

function openCreateAutoCheckout() {
  // 用一個 stub config 餵 dialog（id='new'）— 提交時會分流走 createAutoMut
  editingConfig.value = {
    id: 'new',
    coupon_type: 'auto_checkout',
    discount_type: 'fixed',
    discount_value: 0,
    min_purchase: null,
    is_active: true,
    params: {},
    updated_at: '',
  }
  isCreatingAutoCheckout.value = true
  editConfigOpen.value = true
}

async function onConfirmEditConfig(payload: {
  is_active: boolean
  discount_type: 'percentage' | 'fixed'
  discount_value: number
  min_purchase: number | null
  params: Record<string, unknown>
}) {
  apiError.value = null
  try {
    if (isCreatingAutoCheckout.value) {
      await createAutoMut.mutateAsync({
        discount_type: payload.discount_type,
        discount_value: payload.discount_value,
        min_purchase: payload.min_purchase,
        params: payload.params,
      })
    } else if (editingConfig.value) {
      await patchMut.mutateAsync({ id: editingConfig.value.id, payload })
    }
    editConfigOpen.value = false
  } catch (e) {
    apiError.value = (e as { message?: string }).message || '儲存失敗'
  }
}

async function deleteAutoCheckout(c: CouponConfig) {
  if (!confirm(`確定刪除此 auto_checkout 活動？已發放的券不受影響。`)) return
  try {
    await deleteConfigMut.mutateAsync(c.id)
  } catch (e) {
    alert((e as { message?: string }).message || '刪除失敗')
  }
}

async function toggleConfigActive(c: CouponConfig) {
  try {
    await patchMut.mutateAsync({ id: c.id, payload: { is_active: !c.is_active } })
  } catch (e) {
    alert((e as { message?: string }).message || '切換失敗')
  }
}

function goStats(c: CouponConfig) {
  router.push(`/admin/discounts/configs/${c.id}/stats`)
}

// ── PromoCodes ────────────────────────────────────────────────────────
const { data: promoData, isLoading: promoLoading, isError: promoError } = usePromoCodesQuery()
const createPromoMut = useCreatePromoCodeMutation()
const updatePromoMut = useUpdatePromoCodeMutation()
const deletePromoMut = useDeletePromoCodeMutation()

const promoDialogOpen = ref(false)
const editingPromo = ref<PromoCode | null>(null)

const promoColumns: Column<PromoCode>[] = [
  { key: 'code', label: '促銷碼', width: '160px' },
  { key: 'discount', label: '折扣', width: '140px' },
  { key: 'period', label: '活動期間' },
  { key: 'usage', label: '使用進度', width: '120px', align: 'right' },
  { key: 'active', label: '狀態', width: '70px', align: 'center' },
  { key: 'actions', label: '', width: '100px', align: 'right' },
]

function openCreatePromo() {
  editingPromo.value = null
  promoDialogOpen.value = true
}

function openEditPromo(p: PromoCode) {
  editingPromo.value = p
  promoDialogOpen.value = true
}

async function onConfirmPromo(payload: Parameters<typeof createPromoMut.mutateAsync>[0] & { is_active?: boolean }) {
  apiError.value = null
  try {
    if (editingPromo.value) {
      await updatePromoMut.mutateAsync({ id: editingPromo.value.id, payload })
    } else {
      const { is_active: _ia, ...createPayload } = payload
      await createPromoMut.mutateAsync(createPayload)
    }
    promoDialogOpen.value = false
  } catch (e) {
    const err = e as { status?: number; message?: string }
    if (err.status === 409) apiError.value = '促銷碼已存在'
    else apiError.value = err.message || '儲存失敗'
  }
}

async function deletePromo(p: PromoCode) {
  if (!confirm(`確定刪除「${p.code}」？已使用的客戶券記錄會保留。`)) return
  try {
    await deletePromoMut.mutateAsync(p.id)
  } catch (e) {
    alert((e as { message?: string }).message || '刪除失敗')
  }
}

// ── UserCoupons ───────────────────────────────────────────────────────
const filterUserId = ref<string>(typeof route.query.user_id === 'string' ? route.query.user_id : '')
const filterCouponType = ref<'' | CouponType>('')
const filterIsUsed = ref<'' | 'true' | 'false'>('')

const userCouponsParams = computed(() => ({
  user_id: filterUserId.value || undefined,
  coupon_type: filterCouponType.value || undefined,
  is_used:
    filterIsUsed.value === 'true' ? true : filterIsUsed.value === 'false' ? false : undefined,
}))

const { data: userCouponsData, isLoading: userCouponsLoading } = useUserCouponsQuery(userCouponsParams)

const userCouponColumns: Column<AdminUserCoupon>[] = [
  { key: 'user', label: '用戶 ID', width: '110px' },
  { key: 'type', label: '類型', width: '130px' },
  { key: 'discount', label: '折扣', width: '140px' },
  { key: 'min_purchase', label: '門檻', width: '110px', align: 'right' },
  { key: 'expires_at', label: '到期', width: '170px' },
  { key: 'status', label: '使用狀態', width: '120px' },
]

const issueOpen = ref(false)
const issueMut = useIssueCouponsMutation()
const issueResult = ref<string | null>(null)

async function onConfirmIssue(payload: { user_ids: string[]; coupon_config_id: string }) {
  apiError.value = null
  issueResult.value = null
  try {
    const r = await issueMut.mutateAsync(payload)
    issueResult.value = `已發放 ${r.issued_count} 張`
    issueOpen.value = false
  } catch (e) {
    apiError.value = (e as { message?: string }).message || '發放失敗'
  }
}

const couponTypeOptions = [
  { value: '', label: '全部類型' },
  { value: 'new_user', label: '新用戶歡迎券' },
  { value: 'spend_reward', label: '滿額回饋券' },
  { value: 'returning_loyal', label: '回頭客忠誠券' },
  { value: 'manual', label: '手動發放' },
]

const usedOptions = [
  { value: '', label: '全部使用狀態' },
  { value: 'false', label: '未使用' },
  { value: 'true', label: '已使用' },
]

// ── Format helpers ────────────────────────────────────────────────────
function fmtDate(iso: string | null): string {
  if (!iso) return '無限制'
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function fmtDateTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
</script>

<template>
  <PageHeader title="折扣與券" subtitle="券類型設定 / 公開促銷碼 / 個人券查詢" />

  <DiscountsTabs />

  <div
    v-if="apiError"
    class="mb-5 px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)] flex items-start gap-2"
  >
    <AlertTriangle :size="14" :stroke-width="1.5" class="mt-0.5" />
    <span class="flex-1">{{ apiError }}</span>
    <button class="text-[12px] underline" @click="apiError = null">關閉</button>
  </div>
  <div
    v-if="issueResult"
    class="mb-5 px-4 py-3 border border-state-success/40 bg-[var(--color-state-success)]/[0.06] text-state-success text-[13px] rounded-[var(--radius-xs)]"
  >
    {{ issueResult }}
  </div>

  <!-- Tab A：CouponConfigs -->
  <div v-if="activeTab === 'configs'">
    <div v-if="configsLoading" class="py-12 flex justify-center text-ink-muted">
      <Loader2 :size="20" :stroke-width="1.5" class="animate-spin" />
    </div>
    <div
      v-else-if="configsError"
      class="px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)]"
    >
      載入失敗
    </div>

    <template v-else>
      <Card class="mb-5">
        <h2 class="font-display text-ink-strong text-[18px] leading-[26px] mb-4">系統券類型</h2>
        <div v-if="systemConfigs.length === 0" class="text-ink-muted text-[13px]">尚無系統 config（後端 seed 應該已建好 4 種）</div>
        <div v-else class="divide-y divide-line-hairline">
          <div
            v-for="c in systemConfigs"
            :key="c.id"
            class="py-3 flex items-center justify-between gap-3 flex-wrap"
          >
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-medium text-ink-strong">{{ COUPON_TYPE_LABEL[c.coupon_type] }}</span>
                <span
                  class="inline-flex items-center px-2 h-[20px] text-[11px] tracking-[0.04em] rounded-[var(--radius-xs)]"
                  :class="
                    c.is_active
                      ? 'bg-[var(--color-state-success)]/[0.10] text-state-success'
                      : 'bg-paper-subtle text-ink-muted'
                  "
                >
                  {{ c.is_active ? '啟用中' : '已停用' }}
                </span>
              </div>
              <p class="mt-1 text-[12px] text-ink-muted">
                {{ formatDiscount(c.discount_type, c.discount_value) }}
                <span v-if="c.min_purchase">· 門檻 NT$ {{ c.min_purchase }}</span>
                <span v-if="typeof c.params?.valid_days === 'number'">· 有效 {{ c.params.valid_days }} 天</span>
                <span v-if="typeof c.params?.trigger_threshold === 'number'">· 觸發門檻 NT$ {{ c.params.trigger_threshold }}</span>
              </p>
            </div>
            <div class="flex items-center gap-1 shrink-0">
              <button
                type="button"
                class="h-8 px-2 inline-flex items-center gap-1 text-[12px] rounded-[var(--radius-xs)] text-ink-muted hover:text-ink-strong hover:bg-paper-subtle transition-colors"
                @click="toggleConfigActive(c)"
              >
                {{ c.is_active ? '停用' : '啟用' }}
              </button>
              <button
                type="button"
                class="h-8 w-8 inline-flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:text-ink-strong hover:bg-paper-subtle transition-colors"
                @click="goStats(c)"
                aria-label="使用統計"
              >
                <BarChart3 :size="14" :stroke-width="1.5" />
              </button>
              <button
                type="button"
                class="h-8 w-8 inline-flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:text-ink-strong hover:bg-paper-subtle transition-colors"
                @click="openEditConfig(c)"
                aria-label="編輯"
              >
                <Pencil :size="14" :stroke-width="1.5" />
              </button>
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-display text-ink-strong text-[18px] leading-[26px]">
            結帳自動促銷
            <span class="ml-2 text-[12px] text-ink-muted font-sans">{{ autoCheckoutConfigs.length }} 個活動</span>
          </h2>
          <Button variant="primary" @click="openCreateAutoCheckout">
            <Plus :size="14" :stroke-width="1.75" />
            新增活動
          </Button>
        </div>
        <div v-if="autoCheckoutConfigs.length === 0" class="text-ink-muted text-[13px] py-4 text-center">
          尚無活動。可同時存在多個，結帳時自動取折扣金額最高者。
        </div>
        <div v-else class="space-y-2">
          <div
            v-for="c in autoCheckoutConfigs"
            :key="c.id"
            class="p-3 border border-line-hairline rounded-[var(--radius-xs)] flex items-center justify-between gap-3 flex-wrap"
          >
            <div class="flex-1">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="font-medium text-ink-strong">{{ formatDiscount(c.discount_type, c.discount_value) }}</span>
                <span
                  class="inline-flex items-center px-2 h-[20px] text-[11px] tracking-[0.04em] rounded-[var(--radius-xs)]"
                  :class="
                    c.is_active
                      ? 'bg-[var(--color-state-success)]/[0.10] text-state-success'
                      : 'bg-paper-subtle text-ink-muted'
                  "
                >
                  {{ c.is_active ? '啟用' : '停用' }}
                </span>
              </div>
              <p class="mt-1 text-[12px] text-ink-muted">
                <span v-if="typeof c.params?.trigger_threshold === 'number'">滿 NT$ {{ c.params.trigger_threshold }} 自動套用</span>
                <span v-if="c.params?.start_at && c.params?.end_at">
                  · {{ fmtDate(c.params.start_at as string) }} ~ {{ fmtDate(c.params.end_at as string) }}
                </span>
              </p>
            </div>
            <div class="flex items-center gap-1 shrink-0">
              <button
                type="button"
                class="h-8 w-8 inline-flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:text-ink-strong hover:bg-paper-subtle transition-colors"
                @click="goStats(c)"
                aria-label="統計"
              >
                <BarChart3 :size="14" :stroke-width="1.5" />
              </button>
              <button
                type="button"
                class="h-8 w-8 inline-flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:text-ink-strong hover:bg-paper-subtle transition-colors"
                @click="openEditConfig(c)"
                aria-label="編輯"
              >
                <Pencil :size="14" :stroke-width="1.5" />
              </button>
              <button
                type="button"
                class="h-8 w-8 inline-flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:text-state-danger hover:bg-[var(--color-state-danger)]/[0.10] transition-colors"
                @click="deleteAutoCheckout(c)"
                aria-label="刪除"
              >
                <Trash2 :size="14" :stroke-width="1.5" />
              </button>
            </div>
          </div>
        </div>
      </Card>

      <EditConfigDialog
        :open="editConfigOpen"
        :config="editingConfig"
        :pending="patchMut.isPending.value || createAutoMut.isPending.value"
        @close="editConfigOpen = false"
        @confirm="onConfirmEditConfig"
      />
    </template>
  </div>

  <!-- Tab B：PromoCodes -->
  <div v-else-if="activeTab === 'promo'">
    <div class="flex items-center justify-end mb-3">
      <Button variant="primary" @click="openCreatePromo">
        <Plus :size="14" :stroke-width="1.75" />
        新增促銷碼
      </Button>
    </div>
    <AppDataTable
      :columns="promoColumns"
      :rows="promoData?.items ?? []"
      :loading="promoLoading"
      :row-key="(r) => r.id"
      empty-text="尚無促銷碼"
      :empty-icon="Tag"
    >
      <template #cell-code="{ row }">
        <span class="font-mono text-[13px] text-ink-strong">{{ row.code }}</span>
      </template>
      <template #cell-discount="{ row }">
        <span class="text-[13px]">{{ formatDiscount(row.discount_type, row.discount_value) }}</span>
        <span v-if="row.min_purchase" class="text-[11px] text-ink-muted ml-1">滿 {{ row.min_purchase }}</span>
      </template>
      <template #cell-period="{ row }">
        <span class="text-[12px] text-ink-default">{{ fmtDate(row.start_at) }} ~ {{ fmtDate(row.end_at) }}</span>
      </template>
      <template #cell-usage="{ row }">
        <span class="font-mono text-[12px]">
          {{ row.total_used }} / {{ row.max_total_uses ?? '∞' }}
        </span>
      </template>
      <template #cell-active="{ row }">
        <span
          class="inline-flex items-center px-2 h-[20px] text-[11px] rounded-[var(--radius-xs)]"
          :class="
            row.is_active
              ? 'bg-[var(--color-state-success)]/[0.10] text-state-success'
              : 'bg-paper-subtle text-ink-muted'
          "
        >
          {{ row.is_active ? '啟用' : '停用' }}
        </span>
      </template>
      <template #cell-actions="{ row }">
        <div class="flex items-center justify-end gap-1">
          <button
            type="button"
            class="h-8 w-8 inline-flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:text-ink-strong hover:bg-paper-subtle"
            @click="openEditPromo(row)"
          >
            <Pencil :size="14" :stroke-width="1.5" />
          </button>
          <button
            type="button"
            class="h-8 w-8 inline-flex items-center justify-center rounded-[var(--radius-xs)] text-ink-muted hover:text-state-danger hover:bg-[var(--color-state-danger)]/[0.10]"
            @click="deletePromo(row)"
          >
            <Trash2 :size="14" :stroke-width="1.5" />
          </button>
        </div>
      </template>
    </AppDataTable>

    <PromoCodeDialog
      :open="promoDialogOpen"
      :promo="editingPromo"
      :pending="createPromoMut.isPending.value || updatePromoMut.isPending.value"
      @close="promoDialogOpen = false"
      @confirm="onConfirmPromo"
    />
  </div>

  <!-- Tab C：UserCoupons -->
  <div v-else-if="activeTab === 'users'">
    <section class="bg-paper-surface border border-line-hairline rounded-[var(--radius-sm)] p-4 mb-5">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Input v-model="filterUserId" placeholder="User UUID（可選）" />
        <Select v-model="filterCouponType" :options="couponTypeOptions" />
        <Select v-model="filterIsUsed" :options="usedOptions" />
      </div>
    </section>

    <div class="flex items-center justify-end mb-3">
      <Button variant="primary" @click="issueOpen = true">
        <Send :size="14" :stroke-width="1.5" />
        批次發放優惠券
      </Button>
    </div>

    <AppDataTable
      :columns="userCouponColumns"
      :rows="userCouponsData?.items ?? []"
      :loading="userCouponsLoading"
      :row-key="(r) => r.id"
      empty-text="無符合條件的個人券"
    >
      <template #cell-user="{ row }">
        <span class="font-mono text-[12px]">{{ row.user_id.slice(0, 8) }}</span>
      </template>
      <template #cell-type="{ row }">
        <span class="text-[12px]">{{ row.coupon_type ? COUPON_TYPE_LABEL[row.coupon_type as CouponType] : '— public_code' }}</span>
      </template>
      <template #cell-discount="{ row }">
        <span class="text-[12px]">{{ formatDiscount(row.discount_type, row.discount_value) }}</span>
      </template>
      <template #cell-min_purchase="{ row }">
        <span class="font-mono text-[12px]">{{ row.min_purchase ? `NT$ ${row.min_purchase}` : '—' }}</span>
      </template>
      <template #cell-expires_at="{ row }">
        <span class="font-mono text-[12px] text-ink-muted">{{ fmtDateTime(row.expires_at) }}</span>
      </template>
      <template #cell-status="{ row }">
        <span
          class="inline-flex items-center px-2 h-[20px] text-[11px] rounded-[var(--radius-xs)]"
          :class="
            row.is_used
              ? 'bg-paper-subtle text-ink-muted'
              : 'bg-[var(--color-state-success)]/[0.10] text-state-success'
          "
        >
          {{ row.is_used ? '已使用' : '可用' }}
        </span>
      </template>
    </AppDataTable>

    <IssueCouponsDialog
      :open="issueOpen"
      :configs="configsData?.items ?? []"
      :pending="issueMut.isPending.value"
      @close="issueOpen = false"
      @confirm="onConfirmIssue"
    />
  </div>
</template>
