<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { onClickOutside } from '@vueuse/core'
import { ChevronDown, LogOut, Menu } from 'lucide-vue-next'

import { useAuthStore } from '@/features/auth/store'
import { useLogoutMutation } from '@/features/auth/queries'

defineEmits<{
  toggleSidebar: []
}>()

const route = useRoute()
const auth = useAuthStore()
const logout = useLogoutMutation()

const menuOpen = ref(false)
const menuRef = ref<HTMLElement | null>(null)
onClickOutside(menuRef, () => { menuOpen.value = false })

const initials = computed(() => {
  const name = auth.user?.name || 'AD'
  return name.slice(0, 2).toUpperCase()
})

// Crude breadcrumb from route path; will be replaced by per-page meta later
const crumbs = computed(() => {
  const parts = route.path.split('/').filter(Boolean)
  return parts.map((p, i) => ({
    label: friendly(p),
    path: '/' + parts.slice(0, i + 1).join('/'),
  }))
})

function friendly(slug: string): string {
  const map: Record<string, string> = {
    admin: '工坊',
    dashboard: '儀表板',
    orders: '訂單',
    'custom-requests': '客製訂單',
    production: '製作',
    products: '商品',
    colors: '色票',
    discounts: '折扣',
    notifications: '通知',
    'print-batches': '列印批次',
    reports: '報表',
    content: '內容',
    users: '用戶',
  }
  return map[slug] || slug
}

function handleLogout() {
  menuOpen.value = false
  logout.mutate()
}
</script>

<template>
  <header
    class="fixed top-0 right-0 left-0 lg:left-[240px] h-16 bg-paper-surface border-b border-line-hairline z-20"
  >
    <div class="h-full px-4 lg:px-7 flex items-center justify-between gap-3">
      <!-- Left: hamburger + breadcrumb -->
      <div class="flex items-center gap-3 min-w-0">
        <button
          type="button"
          class="lg:hidden p-1 -ml-1 text-ink-muted hover:text-ink-strong shrink-0"
          aria-label="Open menu"
          @click="$emit('toggleSidebar')"
        >
          <Menu :size="20" :stroke-width="1.5" />
        </button>

        <nav class="flex items-center gap-2 text-[12px] uppercase tracking-[0.06em] text-ink-muted overflow-hidden">
          <template v-for="(c, i) in crumbs" :key="c.path">
            <span v-if="i > 0" class="text-aux-rice-mid shrink-0">／</span>
            <span
              :class="[
                i === crumbs.length - 1 ? 'text-ink-default' : '',
                'truncate',
              ]"
            >
              {{ c.label }}
            </span>
          </template>
        </nav>
      </div>

      <!-- Right: user menu -->
      <div ref="menuRef" class="relative shrink-0">
        <button
          type="button"
          class="flex items-center gap-2 h-9 px-2.5 rounded-[var(--radius-xs)] hover:bg-paper-subtle transition-colors duration-[120ms]"
          @click="menuOpen = !menuOpen"
        >
          <span
            class="w-7 h-7 rounded-full bg-accent text-paper-surface flex items-center justify-center text-[11px] font-medium tracking-wider"
          >
            {{ initials }}
          </span>
          <span class="text-[13px] text-ink-default hidden sm:inline">{{ auth.user?.name || '管理員' }}</span>
          <ChevronDown :size="14" :stroke-width="1.5" class="text-ink-muted" />
        </button>

        <div
          v-if="menuOpen"
          class="absolute top-full right-0 mt-2 w-[240px] bg-paper-surface border border-line-hairline rounded-[var(--radius-md)] shadow-[0_4px_16px_rgba(43,38,32,0.08)] py-2"
        >
          <div class="px-4 py-2.5 border-b border-line-hairline">
            <p class="text-[13px] text-ink-strong">{{ auth.user?.name || '管理員' }}</p>
            <p v-if="auth.user?.email" class="text-[12px] text-ink-muted mt-0.5 truncate">
              {{ auth.user.email }}
            </p>
          </div>
          <button
            type="button"
            class="flex items-center gap-2 w-full px-4 py-2.5 text-[13px] text-ink-default hover:bg-paper-subtle transition-colors duration-[120ms]"
            @click="handleLogout"
          >
            <LogOut :size="14" :stroke-width="1.5" class="text-ink-muted" />
            登出
          </button>
        </div>
      </div>
    </div>
  </header>
</template>
