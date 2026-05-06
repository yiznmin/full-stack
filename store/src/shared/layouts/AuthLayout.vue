<script setup lang="ts">
import { RouterView } from 'vue-router'
import SiteLogo from '@/shared/components/SiteLogo.vue'
</script>

<template>
  <div class="auth-layout">
    <header class="auth-header">
      <SiteLogo size="sm" />
    </header>

    <main class="auth-main">
      <div class="auth-card">
        <span class="card-stripe" aria-hidden="true"></span>
        <span class="card-mark" aria-hidden="true">Y</span>
        <RouterView />
      </div>
    </main>

    <footer class="auth-footer">
      <span>© 2026 易木 YIIMUI</span>
    </footer>
  </div>
</template>

<style scoped>
.auth-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.auth-header {
  padding: 32px 56px 16px;
  text-align: center;
}

.auth-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 24px 64px;
}

.auth-card {
  position: relative;
  width: 100%;
  max-width: 440px;
  background: var(--color-paper-surface);
  border: 1px solid var(--color-line-subtle);
  border-radius: var(--radius-sm);
  padding: 56px 44px 48px;
  box-shadow:
    0 1px 0 rgba(31, 26, 21, 0.02),
    0 12px 32px -16px rgba(31, 26, 21, 0.08);
  overflow: hidden;
}

/* 頂部苔綠細條 — magazine masthead 風格 */
.card-stripe {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(
    90deg,
    var(--color-fresh) 0%,
    var(--color-accent-soft) 60%,
    var(--color-accent-wine-soft) 100%
  );
}

/* 右上 Y 裝飾 — 編輯誌字標 */
.card-mark {
  position: absolute;
  top: 16px;
  right: 22px;
  font-family: var(--font-display);
  font-weight: 300;
  font-style: italic;
  font-size: 28px;
  line-height: 1;
  color: var(--color-accent);
  opacity: 0.45;
  user-select: none;
  pointer-events: none;
}

.auth-footer {
  padding: 24px 56px;
  text-align: center;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}

@media (max-width: 767px) {
  .auth-header { padding: 24px 24px 8px; }
  .auth-card { padding: 40px 24px 32px; }
  .card-mark { font-size: 22px; top: 12px; right: 16px; }
}
</style>
