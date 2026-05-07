<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Loader2, Save } from 'lucide-vue-next'

import Card from '@/shared/ui/Card.vue'
import Button from '@/shared/ui/Button.vue'
import Input from '@/shared/ui/Input.vue'
import Label from '@/shared/ui/Label.vue'
import Textarea from '@/shared/ui/Textarea.vue'

import { useSettingsQuery, useUpsertSettingMutation } from '../queries'
import { SETTING_LABEL, SETTING_GROUP_LABEL, type SettingMeta } from '../api'

const { data, isLoading } = useSettingsQuery()
const upsertMut = useUpsertSettingMutation()

const localValues = ref<Record<string, string>>({})
const saving = ref<string | null>(null)
const apiError = ref<string | null>(null)

watch(
  () => data.value?.items,
  (items) => {
    if (items) {
      const map: Record<string, string> = {}
      for (const s of items) map[s.key] = s.value
      // 已知但 DB 還沒值的 key → 補空字串，UI 才會渲染輸入框
      for (const key of Object.keys(SETTING_LABEL)) {
        if (!(key in map)) map[key] = ''
      }
      localValues.value = map
    }
  },
  { immediate: true },
)

interface Row {
  key: string
  meta: SettingMeta
  value: string
  updatedAt: string | null
  saved: boolean
}

const allRows = computed<Row[]>(() => {
  const items = data.value?.items ?? []
  const itemMap: Record<string, { value: string; updated_at: string }> = {}
  for (const s of items) itemMap[s.key] = { value: s.value, updated_at: s.updated_at }

  const rows: Row[] = []
  // 已知 key（依 SETTING_LABEL 順序）
  for (const [key, meta] of Object.entries(SETTING_LABEL)) {
    const persisted = itemMap[key]
    rows.push({
      key,
      meta,
      value: persisted?.value ?? '',
      updatedAt: persisted?.updated_at ?? null,
      saved: !!persisted,
    })
  }
  // 未在 SETTING_LABEL 但 DB 有的 key（後加的）→ 歸 misc
  for (const s of items) {
    if (!(s.key in SETTING_LABEL)) {
      rows.push({
        key: s.key,
        meta: { label: s.key, type: 'text', group: 'misc' },
        value: s.value,
        updatedAt: s.updated_at,
        saved: true,
      })
    }
  }
  return rows
})

type Group = SettingMeta['group']
const grouped = computed<Array<{ group: Group; label: string; rows: Row[] }>>(() => {
  const map = new Map<Group, Row[]>()
  for (const r of allRows.value) {
    const list = map.get(r.meta.group) ?? []
    list.push(r)
    map.set(r.meta.group, list)
  }
  // group 順序：依 SETTING_GROUP_LABEL key 順序
  const order: Group[] = ['payment', 'ecpay_sender', 'product_info', 'paint', 'custom', 'misc']
  return order
    .filter((g) => map.has(g))
    .map((g) => ({ group: g, label: SETTING_GROUP_LABEL[g], rows: map.get(g) ?? [] }))
})

async function saveOne(key: string) {
  apiError.value = null
  saving.value = key
  try {
    await upsertMut.mutateAsync({ key, value: localValues.value[key] ?? '' })
  } catch (e) {
    apiError.value = (e as { message?: string }).message || '儲存失敗'
  } finally {
    saving.value = null
  }
}

function isDirty(row: Row): boolean {
  return (localValues.value[row.key] ?? '') !== row.value
}
</script>

<template>
  <div class="space-y-5">
    <p
      v-if="apiError"
      class="px-3 py-2 border border-state-danger/40 bg-[var(--color-state-danger)]/[0.06] text-state-danger text-[12px] rounded-[var(--radius-xs)]"
    >{{ apiError }}</p>

    <div v-if="isLoading" class="py-12 flex justify-center text-ink-muted">
      <Loader2 :size="20" :stroke-width="1.5" class="animate-spin" />
    </div>

    <template v-else>
      <Card v-for="g in grouped" :key="g.group">
        <h2 class="font-display text-ink-strong text-[16px] leading-[24px] mb-4 pb-3 border-b border-line-hairline">
          {{ g.label }}
        </h2>

        <ul class="divide-y divide-line-hairline">
          <li v-for="row in g.rows" :key="row.key" class="py-4 first:pt-0 last:pb-0">
            <div class="flex items-start justify-between gap-3 flex-wrap">
              <div class="flex-1 min-w-0 max-w-2xl">
                <Label>
                  {{ row.meta.label }}
                  <span class="text-[10px] text-ink-muted font-mono ml-1">{{ row.key }}</span>
                  <span
                    v-if="!row.saved"
                    class="ml-2 inline-flex items-center px-1.5 h-[16px] text-[9px] tracking-[0.18em] uppercase rounded-[var(--radius-xs)] bg-[var(--color-state-warning)]/[0.18] text-state-warning"
                  >
                    未設定
                  </span>
                </Label>
                <Input
                  v-if="row.meta.type === 'text'"
                  v-model="localValues[row.key]"
                />
                <Input
                  v-else-if="row.meta.type === 'number'"
                  v-model="localValues[row.key]"
                  type="number"
                />
                <Textarea
                  v-else
                  v-model="localValues[row.key]"
                  :rows="4"
                  class="font-mono text-[13px]"
                />
                <p v-if="row.meta.hint" class="mt-1 text-[11px] text-ink-muted">{{ row.meta.hint }}</p>
                <p v-if="row.updatedAt" class="mt-1 text-[11px] text-ink-muted">
                  最後更新 {{ new Date(row.updatedAt).toLocaleString('zh-TW') }}
                </p>
              </div>
              <div class="shrink-0">
                <Button
                  variant="secondary"
                  :disabled="saving === row.key || !isDirty(row)"
                  @click="saveOne(row.key)"
                >
                  <Loader2 v-if="saving === row.key" :size="14" :stroke-width="1.5" class="animate-spin" />
                  <Save v-else :size="14" :stroke-width="1.5" />
                  儲存
                </Button>
              </div>
            </div>
          </li>
        </ul>
      </Card>
    </template>
  </div>
</template>
