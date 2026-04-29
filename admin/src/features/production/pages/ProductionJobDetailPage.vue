<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ChevronLeft,
  Loader2,
  CheckCircle2,
  XCircle,
  Download,
  ImageOff,
  Link as LinkIcon,
  AlertTriangle,
  Palette,
} from 'lucide-vue-next'

import Card from '@/shared/ui/Card.vue'
import Button from '@/shared/ui/Button.vue'

import JobStatusBadge from '../components/JobStatusBadge.vue'
import {
  useApproveJobMutation,
  useJobQuery,
  useUnapproveJobMutation,
} from '../queries'
import {
  downloadJobPdf,
  getJobSignedUrl,
  DETAIL_LABEL,
  DIFFICULTY_LABEL,
} from '../api'

const route = useRoute()
const router = useRouter()

const jobId = computed(() => (typeof route.params.jobId === 'string' ? route.params.jobId : ''))

const { data: job, isLoading, isError, error } = useJobQuery(jobId)
const approveMut = useApproveJobMutation(jobId.value)
const unapproveMut = useUnapproveJobMutation(jobId.value)

const apiError = ref<string | null>(null)
const pdfDownloading = ref(false)

// SVG signed URL（私有檔案，需簽章）
const svgUrl = ref<string | null>(null)
const svgLoading = ref(false)
const svgFailed = ref(false)

watch(
  () => [job.value?.id, job.value?.svg_url],
  async ([id, raw]) => {
    svgUrl.value = null
    svgFailed.value = false
    if (!id || !raw) return
    svgLoading.value = true
    try {
      const r = await getJobSignedUrl(id, 'svg')
      svgUrl.value = r.url
    } catch (e) {
      apiError.value = (e as { message?: string }).message || '取得 SVG 連結失敗'
    } finally {
      svgLoading.value = false
    }
  },
  { immediate: true },
)

async function doApprove() {
  apiError.value = null
  try {
    await approveMut.mutateAsync(null)
  } catch (e) {
    apiError.value = (e as { message?: string }).message || '審核失敗'
  }
}

async function doUnapprove() {
  apiError.value = null
  try {
    await unapproveMut.mutateAsync()
  } catch (e) {
    apiError.value = (e as { message?: string }).message || '撤銷審核失敗'
  }
}

async function doExportPdf() {
  if (!job.value) return
  apiError.value = null
  pdfDownloading.value = true
  try {
    await downloadJobPdf(job.value.id)
  } catch (e) {
    apiError.value = (e as { message?: string }).message || 'PDF 匯出失敗'
  } finally {
    pdfDownloading.value = false
  }
}

const canApprove = computed(() => job.value?.status === 'completed' && !job.value.approved)
const canUnapprove = computed(() => job.value?.status === 'completed' && job.value.approved)
const canExportPdf = computed(() => job.value?.status === 'completed' && !!job.value.svg_url)

function fmtDateTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
</script>

<template>
  <div class="flex items-center gap-2 mb-3">
    <button
      type="button"
      class="text-[13px] text-ink-muted hover:text-ink-strong inline-flex items-center gap-1 transition-colors"
      @click="router.push('/admin/production')"
    >
      <ChevronLeft :size="14" :stroke-width="1.5" />
      返回任務列表
    </button>
  </div>

  <div v-if="isLoading" class="flex items-center justify-center py-20 text-ink-muted">
    <Loader2 :size="20" :stroke-width="1.5" class="animate-spin" />
    <span class="ml-2 text-[13px]">載入中...</span>
  </div>

  <div
    v-else-if="isError"
    class="px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)]"
  >
    載入失敗：{{ (error as { message?: string })?.message ?? '任務不存在' }}
  </div>

  <template v-else-if="job">
    <header class="mb-7 pb-5 border-b border-line-hairline flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
      <div>
        <div class="flex items-center gap-2 flex-wrap">
          <h1 class="font-display text-ink-strong text-[24px] leading-[32px] tracking-[-0.005em]">
            製作任務
            <span class="font-mono text-[20px] ml-1">#{{ job.id.slice(0, 8) }}</span>
          </h1>
          <JobStatusBadge :status="job.status" :approved="job.approved" />
          <span
            v-if="job.batch_id"
            class="inline-flex items-center px-2 h-[22px] text-[11px] tracking-[0.04em] rounded-[var(--radius-xs)] bg-paper-subtle text-ink-default"
          >
            批次 {{ job.batch_id.slice(0, 8) }}
          </span>
        </div>
        <p class="mt-1 text-[13px] text-ink-muted">建立於 {{ fmtDateTime(job.created_at) }}</p>
      </div>
      <div class="flex flex-wrap items-center gap-2 shrink-0">
        <Button v-if="canApprove" variant="primary" :disabled="approveMut.isPending.value" @click="doApprove">
          <Loader2 v-if="approveMut.isPending.value" :size="14" :stroke-width="1.5" class="animate-spin" />
          <CheckCircle2 v-else :size="14" :stroke-width="1.5" />
          確認儲存（審核通過）
        </Button>
        <Button v-if="canUnapprove" variant="secondary" :disabled="unapproveMut.isPending.value" @click="doUnapprove">
          <Loader2 v-if="unapproveMut.isPending.value" :size="14" :stroke-width="1.5" class="animate-spin" />
          <XCircle v-else :size="14" :stroke-width="1.5" />
          撤銷審核
        </Button>
        <Button v-if="canExportPdf" variant="secondary" :disabled="pdfDownloading" @click="doExportPdf">
          <Loader2 v-if="pdfDownloading" :size="14" :stroke-width="1.5" class="animate-spin" />
          <Download v-else :size="14" :stroke-width="1.5" />
          {{ pdfDownloading ? '轉換中...（最多 15 秒）' : '匯出 PDF' }}
        </Button>
        <Button
          v-if="job.approved"
          variant="secondary"
          @click="router.push(`/admin/colors/mapping/${job.id}`)"
        >
          <Palette :size="14" :stroke-width="1.5" />
          顏色對應
        </Button>
      </div>
    </header>

    <div
      v-if="apiError"
      class="mb-5 px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)] flex items-start gap-2"
    >
      <span class="flex-1">{{ apiError }}</span>
      <button class="text-[12px] underline" @click="apiError = null">關閉</button>
    </div>

    <div
      v-if="job.status === 'pending' || job.status === 'processing'"
      class="mb-5 px-4 py-3 border border-state-info/40 bg-[var(--color-state-info)]/[0.06] text-state-info text-[13px] rounded-[var(--radius-xs)] flex items-center gap-2"
    >
      <Loader2 :size="14" :stroke-width="1.5" class="animate-spin" />
      Celery 處理中，每 5 秒自動更新...
    </div>

    <div
      v-if="job.status === 'failed' || job.status === 'cancelled'"
      class="mb-5 px-4 py-3 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[13px] rounded-[var(--radius-xs)] flex items-center gap-2"
    >
      <AlertTriangle :size="14" :stroke-width="1.5" />
      <span v-if="job.status === 'failed'">任務執行失敗，無法繼續處理。請重新建立任務。</span>
      <span v-else>批次中前一筆失敗導致此任務取消。</span>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
      <!-- Main column -->
      <div class="lg:col-span-2 space-y-5">
        <Card>
          <h2 class="font-display text-ink-strong text-[18px] leading-[26px] mb-3">成品示意（filled_template）</h2>
          <div
            class="aspect-square rounded-[var(--radius-sm)] border border-line-hairline overflow-hidden bg-paper-canvas flex items-center justify-center"
          >
            <img
              v-if="job.filled_template_url"
              :src="job.filled_template_url"
              alt="成品示意圖"
              class="w-full h-full object-contain"
            />
            <div v-else class="text-center px-4 text-ink-muted">
              <ImageOff :size="32" :stroke-width="1.25" class="mx-auto mb-2" />
              <p class="text-[12px]">尚未產出</p>
            </div>
          </div>
        </Card>

        <Card>
          <h2 class="font-display text-ink-strong text-[18px] leading-[26px] mb-3">數字模板（template.svg）</h2>
          <div
            class="aspect-square rounded-[var(--radius-sm)] border border-line-hairline overflow-hidden bg-paper-surface flex items-center justify-center"
          >
            <Loader2 v-if="svgLoading" :size="24" :stroke-width="1.5" class="animate-spin text-ink-muted" />
            <img
              v-else-if="svgUrl && !svgFailed"
              :src="svgUrl"
              alt="數字模板"
              class="w-full h-full object-contain"
              @error="svgFailed = true"
            />
            <div v-else class="text-center px-4 text-ink-muted">
              <ImageOff :size="32" :stroke-width="1.25" class="mx-auto mb-2" />
              <p class="text-[12px]">尚未產出 SVG</p>
            </div>
          </div>
          <p class="mt-2 text-[11px] text-ink-muted">
            為保護核心資產，SVG 不開放下載；列印請點上方「匯出 PDF」（含 5cm 裝訂留白）
          </p>
        </Card>

        <Card v-if="job.palette_json && job.palette_json.length > 0">
          <h2 class="font-display text-ink-strong text-[18px] leading-[26px] mb-3">
            調色盤
            <span class="ml-2 text-[12px] text-ink-muted font-sans">{{ job.palette_json.length }} 色</span>
          </h2>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div
              v-for="c in job.palette_json"
              :key="c.template_id"
              class="flex items-center gap-3 p-2 border border-line-hairline rounded-[var(--radius-xs)]"
            >
              <div
                class="w-8 h-8 rounded-[var(--radius-xs)] border border-line-hairline shrink-0"
                :style="{ backgroundColor: c.hex }"
              />
              <div class="flex-1 min-w-0">
                <div class="text-[12px] font-medium text-ink-strong">
                  色號 {{ c.template_id }}
                  <span class="ml-2 font-mono text-ink-muted">{{ c.hex }}</span>
                </div>
                <div v-if="c.percent" class="text-[11px] text-ink-muted">{{ c.percent.toFixed(1) }}%</div>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <!-- Side column -->
      <div class="space-y-5">
        <Card>
          <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-3">參數</h2>
          <dl class="text-[13px] space-y-1.5">
            <div class="flex justify-between"><dt class="text-ink-muted">畫布</dt><dd class="font-mono">{{ job.canvas_w_cm }} × {{ job.canvas_h_cm }} cm</dd></div>
            <div class="flex justify-between"><dt class="text-ink-muted">難易度</dt><dd>{{ DIFFICULTY_LABEL[job.difficulty] }}</dd></div>
            <div class="flex justify-between"><dt class="text-ink-muted">細緻度</dt><dd>{{ DETAIL_LABEL[job.detail] }}</dd></div>
            <div class="flex justify-between"><dt class="text-ink-muted">模式</dt><dd class="font-mono">{{ job.mode }}</dd></div>
            <div v-if="job.num_colors_used !== null" class="flex justify-between">
              <dt class="text-ink-muted">使用色數</dt><dd class="font-mono">{{ job.num_colors_used }}</dd>
            </div>
          </dl>
        </Card>

        <Card>
          <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-3">來源</h2>
          <p v-if="job.custom_request_id" class="text-[13px]">
            <span class="text-ink-muted">客製申請：</span>
            <button
              type="button"
              class="text-accent hover:text-accent-hover inline-flex items-center gap-1 font-mono text-[12px]"
              @click="router.push(`/admin/custom-requests/${job.custom_request_id}`)"
            >
              <LinkIcon :size="12" :stroke-width="1.5" />
              #{{ job.custom_request_id.slice(0, 8) }}
            </button>
          </p>
          <p v-else-if="job.image_id" class="text-[13px]">
            <span class="text-ink-muted">圖片 ID：</span>
            <span class="font-mono text-[12px]">{{ job.image_id.slice(0, 8) }}</span>
          </p>
        </Card>

        <Card>
          <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-3">時間軸</h2>
          <ul class="text-[12px] space-y-1.5">
            <li class="flex justify-between"><span class="text-ink-muted">建立</span><span class="font-mono">{{ fmtDateTime(job.created_at) }}</span></li>
            <li v-if="job.approved_at" class="flex justify-between"><span class="text-ink-muted">審核通過</span><span class="font-mono">{{ fmtDateTime(job.approved_at) }}</span></li>
          </ul>
        </Card>

        <Card v-if="job.notes">
          <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-3">備註</h2>
          <p class="text-[12px] text-ink-default whitespace-pre-line">{{ job.notes }}</p>
        </Card>
      </div>
    </div>
  </template>
</template>
