<script setup lang="ts">
import { RouterLink } from 'vue-router'
import {
  Package,
  ShoppingBag,
  Sparkles,
  Wrench,
  Palette,
  Tag,
  Bell,
  Printer,
  BarChart3,
  FileText,
  Users,
  LayoutDashboard,
  X,
} from 'lucide-vue-next'

import AppLogo from './AppLogo.vue'

defineProps<{
  mobileOpen: boolean
}>()

defineEmits<{
  close: []
}>()

interface NavItem {
  to: string
  label: string
  icon: typeof Package
}

const navItems: NavItem[] = [
  { to: '/admin/dashboard', label: '儀表板', icon: LayoutDashboard },
  { to: '/admin/orders', label: '訂單管理', icon: ShoppingBag },
  { to: '/admin/custom-requests', label: '客製訂單', icon: Sparkles },
  { to: '/admin/production', label: '製作系統', icon: Wrench },
  { to: '/admin/products', label: '商品管理', icon: Package },
  { to: '/admin/colors', label: '實體色管理', icon: Palette },
  { to: '/admin/discounts', label: '折扣與券', icon: Tag },
  { to: '/admin/notifications', label: '通知中心', icon: Bell },
  { to: '/admin/print-batches', label: '列印批次', icon: Printer },
  { to: '/admin/reports', label: '銷售報表', icon: BarChart3 },
  { to: '/admin/content', label: '內容管理', icon: FileText },
  { to: '/admin/users', label: '用戶管理', icon: Users },
]
</script>

<template>
  <!-- Mobile backdrop -->
  <div
    v-if="mobileOpen"
    class="fixed inset-0 bg-ink-strong/40 z-30 lg:hidden"
    @click="$emit('close')"
  />

  <aside
    class="fixed inset-y-0 left-0 w-[240px] bg-paper-surface border-r border-line-hairline flex flex-col z-40 transition-transform duration-200 lg:translate-x-0"
    :class="mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'"
  >
    <!-- Logo area -->
    <div class="h-16 flex items-center justify-between px-5 border-b border-line-hairline">
      <AppLogo size="sm" />
      <button
        type="button"
        class="lg:hidden p-1 -mr-1 text-ink-muted hover:text-ink-strong"
        aria-label="Close menu"
        @click="$emit('close')"
      >
        <X :size="18" :stroke-width="1.5" />
      </button>
    </div>

    <!-- Nav -->
    <nav class="flex-1 overflow-y-auto py-3">
      <ul class="space-y-px px-2">
        <li v-for="item in navItems" :key="item.to">
          <RouterLink
            :to="item.to"
            class="group flex items-center gap-2.5 h-10 px-3 rounded-[var(--radius-xs)] text-[13px] transition-colors duration-[120ms] relative"
            :class="[
              $route.path.startsWith(item.to)
                ? 'bg-paper-subtle text-ink-strong font-medium'
                : 'text-ink-muted hover:bg-paper-subtle hover:text-ink-strong',
            ]"
          >
            <span
              v-if="$route.path.startsWith(item.to)"
              class="absolute left-0 top-1.5 bottom-1.5 w-0.5 bg-accent rounded-full"
            />
            <component :is="item.icon" :size="16" :stroke-width="1.5" />
            <span>{{ item.label }}</span>
          </RouterLink>
        </li>
      </ul>
    </nav>

    <!-- Footer note -->
    <div class="p-4 border-t border-line-hairline">
      <p class="text-[11px] text-ink-muted tracking-[0.04em]">
        易木工房 · v0.1
      </p>
    </div>
  </aside>
</template>
