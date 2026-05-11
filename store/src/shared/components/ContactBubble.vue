<script setup lang="ts">
// 全站浮動聯絡泡泡 — 雜誌風 + 品牌核桃棕。
// 點圓圈展開卡片，列 IG / Email / 緊急 Gmail 三個聯絡選項。
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { Mail, Instagram, X, MessageCircle } from 'lucide-vue-next'

const open = ref(false)
const root = ref<HTMLElement | null>(null)

function toggle() {
  open.value = !open.value
}

function close() {
  open.value = false
}

function onDocClick(e: MouseEvent) {
  if (!open.value || !root.value) return
  if (!root.value.contains(e.target as Node)) close()
}

function onEsc(e: KeyboardEvent) {
  if (e.key === 'Escape') close()
}

onMounted(() => {
  document.addEventListener('click', onDocClick)
  document.addEventListener('keydown', onEsc)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  document.removeEventListener('keydown', onEsc)
})
</script>

<template>
  <div ref="root" class="bubble-root">
    <!-- 展開的卡片 -->
    <transition name="card">
      <div v-if="open" class="bubble-card" role="dialog" aria-label="聯絡我們">
        <header class="card-head">
          <span class="card-eyebrow">— Contact —</span>
          <button type="button" class="card-close" aria-label="關閉" @click="close">
            <X :size="14" :stroke-width="1.5" />
          </button>
        </header>
        <h3 class="card-title">有問題嗎？</h3>
        <p class="card-sub">挑一個方便的方式聯絡我們。</p>

        <ul class="card-list">
          <li>
            <a
              href="mailto:contact@yiimui.com"
              class="card-item"
            >
              <Mail :size="16" :stroke-width="1.5" class="card-icon" />
              <div class="card-text">
                <strong>contact@yiimui.com</strong>
                <span>主要聯絡 · 24h 內回</span>
              </div>
            </a>
          </li>
          <li>
            <a
              href="https://instagram.com/yii.mui"
              target="_blank"
              rel="noopener noreferrer"
              class="card-item"
            >
              <Instagram :size="16" :stroke-width="1.5" class="card-icon" />
              <div class="card-text">
                <strong>@yii.mui</strong>
                <span>Instagram 私訊</span>
              </div>
            </a>
          </li>
          <li>
            <a
              href="mailto:yiimui.studio@gmail.com"
              class="card-item card-item-urgent"
            >
              <Mail :size="16" :stroke-width="1.5" class="card-icon" />
              <div class="card-text">
                <strong>yiimui.studio@gmail.com</strong>
                <span>緊急聯絡 · 系統異常時備用</span>
              </div>
            </a>
          </li>
        </ul>
      </div>
    </transition>

    <!-- 觸發圓圈 -->
    <button
      type="button"
      class="bubble-trigger"
      :class="{ 'bubble-trigger-open': open }"
      :aria-expanded="open"
      aria-label="聯絡我們"
      @click.stop="toggle"
    >
      <component
        :is="open ? X : MessageCircle"
        :size="22"
        :stroke-width="1.5"
        class="trigger-icon"
      />
    </button>
  </div>
</template>

<style scoped>
.bubble-root {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 80;
  font-family: var(--font-body);
}

/* —— 觸發圓圈 —— */
.bubble-trigger {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--color-accent);
  color: var(--color-paper-canvas);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(72, 47, 30, 0.22), 0 2px 6px rgba(72, 47, 30, 0.12);
  transition: background 180ms, transform 200ms cubic-bezier(0.4, 0, 0.2, 1);
}
.bubble-trigger:hover {
  background: var(--color-accent-deep);
  transform: translateY(-2px);
}
.bubble-trigger:active {
  transform: translateY(0);
}
.bubble-trigger-open {
  background: var(--color-ink-strong);
}
.bubble-trigger-open:hover {
  background: var(--color-ink-strong);
}
.trigger-icon {
  stroke: currentColor;
  fill: none;
}

/* —— 展開卡片 —— */
.bubble-card {
  position: absolute;
  right: 0;
  bottom: 72px;
  width: 320px;
  background: var(--color-paper-canvas);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-sm, 12px);
  padding: 22px 22px 18px;
  box-shadow: 0 16px 40px rgba(72, 47, 30, 0.16), 0 4px 12px rgba(72, 47, 30, 0.08);
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.card-eyebrow {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.32em;
  text-transform: uppercase;
  color: var(--color-accent);
  font-weight: 500;
}
.card-close {
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--color-ink-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background 150ms, color 150ms;
}
.card-close:hover {
  background: var(--color-paper-deep);
  color: var(--color-ink-strong);
}

.card-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 22px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
  margin: 0 0 4px;
}
.card-sub {
  font-size: 12px;
  line-height: 1.7;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
  margin: 0 0 16px;
}

.card-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.card-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 10px;
  border-radius: 8px;
  text-decoration: none;
  color: var(--color-ink-default);
  transition: background 150ms, transform 120ms;
}
.card-item:hover {
  background: var(--color-paper-deep);
  transform: translateX(2px);
}
.card-icon {
  stroke: var(--color-accent);
  fill: none;
  flex-shrink: 0;
  margin-top: 2px;
}
.card-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.card-text strong {
  font-family: var(--font-mono);
  font-weight: 500;
  font-size: 12px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  overflow: hidden;
  text-overflow: ellipsis;
}
.card-text span {
  font-size: 11px;
  color: var(--color-ink-muted);
  letter-spacing: 0.04em;
}

.card-item-urgent .card-icon {
  stroke: var(--color-state-danger);
}
.card-item-urgent .card-text strong {
  color: var(--color-state-danger);
}

/* —— Transition —— */
.card-enter-active,
.card-leave-active {
  transition: opacity 180ms ease, transform 200ms cubic-bezier(0.4, 0, 0.2, 1);
}
.card-enter-from,
.card-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}

/* —— Responsive —— */
@media (max-width: 767px) {
  .bubble-root {
    right: 16px;
    bottom: 16px;
  }
  .bubble-card {
    width: calc(100vw - 32px);
    max-width: 320px;
    right: 0;
  }
}

/* —— Print: 隱藏 —— */
@media print {
  .bubble-root { display: none; }
}
</style>
