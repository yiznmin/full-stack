<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Settings, Tag, Users } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const tabs = [
  { id: 'configs', label: '券類型設定', icon: Settings },
  { id: 'promo', label: '公開促銷碼', icon: Tag },
  { id: 'users', label: '個人券記錄', icon: Users },
] as const

const currentTab = computed(() => {
  const t = route.query.tab
  if (typeof t === 'string' && tabs.find((x) => x.id === t)) return t
  return 'configs'
})

function selectTab(id: string) {
  router.replace({ query: { ...route.query, tab: id } })
}
</script>

<template>
  <nav class="flex items-center gap-1 mb-6 border-b border-line-hairline">
    <button
      v-for="t in tabs"
      :key="t.id"
      type="button"
      class="inline-flex items-center gap-1.5 h-10 px-4 text-[13px] border-b-2 -mb-px transition-colors"
      :class="
        currentTab === t.id
          ? 'border-accent text-ink-strong font-medium'
          : 'border-transparent text-ink-muted hover:text-ink-strong'
      "
      @click="selectTab(t.id)"
    >
      <component :is="t.icon" :size="14" :stroke-width="1.5" />
      {{ t.label }}
    </button>
  </nav>
</template>
