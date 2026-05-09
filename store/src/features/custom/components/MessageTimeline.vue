<script setup lang="ts">
import { computed } from 'vue'
import { Quote, ImageIcon } from 'lucide-vue-next'
import type { CustomMessage } from '../api'

const props = defineProps<{
  messages: CustomMessage[] | null | undefined
  // 報價事件渲染用
  quotedPrice?: number | null
  quoteSentAt?: string | null
  quoteExpiresAt?: string | null
}>()

// 事件卡是訊息流的事件記錄，CTA 由上方 status banner 統一提供（避免重複）。
// emit 暫保留 type 簽名作為 API surface（CustomRequestDetailPage 仍 @go-to-quote），
// 但不在 template 內 emit。
defineEmits<{
  goToQuote: []
}>()

interface DayGroup {
  dateKey: string  // yyyy-mm-dd
  dateLabel: string
  items: CustomMessage[]
}

// 把訊息按日期分組（asc）
const groups = computed<DayGroup[]>(() => {
  const list = props.messages ?? []
  const byDate = new Map<string, DayGroup>()
  for (const m of list) {
    const d = new Date(m.created_at)
    const key = d.toISOString().slice(0, 10)
    if (!byDate.has(key)) {
      byDate.set(key, {
        dateKey: key,
        dateLabel: d.toLocaleDateString('zh-TW', {
          year: 'numeric',
          month: 'long',
          day: 'numeric',
          weekday: 'short',
        }),
        items: [],
      })
    }
    byDate.get(key)!.items.push(m)
  }
  return Array.from(byDate.values())
})

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('zh-TW', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function senderClass(m: CustomMessage): string {
  if (m.sender_type === 'customer') return 'msg-customer'
  if (m.sender_type === 'admin') return 'msg-admin'
  // 系統訊息（backend 也會用 admin 發 first welcome message；前端用 starts-with 判斷）
  return 'msg-admin'
}

// 是否要在最末顯示「報價事件卡」
const showQuoteEvent = computed(
  () => !!props.quotedPrice && !!props.quoteSentAt,
)

const expiresLabel = computed(() => {
  if (!props.quoteExpiresAt) return null
  const ms = new Date(props.quoteExpiresAt).getTime() - Date.now()
  if (ms <= 0) return '已過期'
  const h = Math.floor(ms / 3_600_000)
  const m = Math.floor((ms % 3_600_000) / 60_000)
  return h > 0 ? `${h} 小時 ${m} 分後到期` : `${m} 分鐘後到期`
})
</script>

<template>
  <div class="timeline">
    <div v-if="!groups.length && !showQuoteEvent" class="empty">
      尚無訊息。
    </div>

    <template v-for="g in groups" :key="g.dateKey">
      <div class="day-mark">
        <span class="day-line" aria-hidden="true" />
        <span class="day-label">{{ g.dateLabel }}</span>
        <span class="day-line" aria-hidden="true" />
      </div>

      <div class="msg-list">
        <article
          v-for="m in g.items"
          :key="m.id"
          class="msg"
          :class="senderClass(m)"
        >
          <div class="msg-bubble">
            <p class="msg-text">{{ m.message }}</p>
            <a
              v-if="m.image_url"
              :href="m.image_url"
              target="_blank"
              rel="noopener noreferrer"
              class="msg-img-link"
            >
              <ImageIcon :size="11" :stroke-width="1.5" />
              附件圖
            </a>
          </div>
          <span class="msg-time">{{ fmtTime(m.created_at) }}</span>
        </article>
      </div>
    </template>

    <!-- 報價事件卡：當 quoted_price 存在 -->
    <div v-if="showQuoteEvent" class="quote-event">
      <div class="quote-event-icon">
        <Quote :size="14" :stroke-width="1.5" />
      </div>
      <div class="quote-event-body">
        <div class="quote-event-no">QUOTE</div>
        <div class="quote-event-title">管理員送出報價</div>
        <div class="quote-event-price">
          NT$ {{ quotedPrice?.toLocaleString() }}
        </div>
        <div v-if="expiresLabel" class="quote-event-meta">
          {{ expiresLabel }}
        </div>
        <p class="quote-event-hint">點頂部「前往報價頁」按鈕進入確認</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.empty {
  padding: 32px 16px;
  text-align: center;
  color: var(--color-ink-muted);
  font-size: 13px;
}

/* 日期分線 */
.day-mark {
  display: flex;
  align-items: center;
  gap: 14px;
  margin: 24px 0 16px;
}
.day-mark:first-child { margin-top: 0; }
.day-line {
  flex: 1;
  height: 1px;
  background: var(--color-line-subtle);
}
.day-label {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}

.msg-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.msg {
  display: flex;
  flex-direction: column;
  max-width: 78%;
  gap: 4px;
}
.msg-customer {
  align-self: flex-end;
  align-items: flex-end;
}
.msg-admin {
  align-self: flex-start;
  align-items: flex-start;
}

.msg-bubble {
  padding: 12px 16px;
  border-radius: var(--radius-sm);
  position: relative;
}
.msg-customer .msg-bubble {
  background: var(--color-accent-tint);
  border: 1px solid var(--color-accent-soft);
  color: var(--color-ink-strong);
}
.msg-admin .msg-bubble {
  background: var(--color-paper-deep);
  border: 1px solid var(--color-line-subtle);
  color: var(--color-ink-default);
}

.msg-text {
  font-size: 14px;
  line-height: 1.7;
  letter-spacing: 0.04em;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-img-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--color-accent);
  text-decoration: none;
}
.msg-img-link:hover { color: var(--color-accent-deep); }

.msg-time {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  color: var(--color-ink-muted);
}

/* 報價事件卡 */
.quote-event {
  margin-top: 32px;
  display: grid;
  grid-template-columns: 40px 1fr;
  gap: 20px;
  padding: 24px;
  border: 1px solid var(--color-accent);
  border-radius: var(--radius-sm);
  background: var(--color-paper-surface);
  position: relative;
}
.quote-event::before {
  content: '';
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 3px;
  background: linear-gradient(
    90deg,
    var(--color-accent),
    var(--color-accent-deep) 60%,
    var(--color-accent)
  );
}
.quote-event-icon {
  width: 40px; height: 40px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: var(--color-accent);
  color: var(--color-paper-canvas);
}
.quote-event-no {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.32em;
  color: var(--color-accent);
  margin-bottom: 4px;
}
.quote-event-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 16px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin-bottom: 12px;
}
.quote-event-price {
  font-family: var(--font-mono);
  font-size: 22px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin-bottom: 6px;
}
.quote-event-meta {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.16em;
  color: var(--color-ink-muted);
  margin-bottom: 16px;
}
.quote-event-hint {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}

@media (max-width: 639px) {
  .msg { max-width: 90%; }
  .quote-event { grid-template-columns: 1fr; gap: 12px; padding: 20px; }
  .quote-event-icon { width: 36px; height: 36px; }
}
</style>
