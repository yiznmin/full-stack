<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useQuery } from '@tanstack/vue-query'
import { ArrowLeft, Loader2, FileQuestion } from 'lucide-vue-next'
import SectionMasthead from '@/shared/components/SectionMasthead.vue'
import {
  listCustomCases,
  listCaseCategories,
  DIFFICULTY_LABEL,
  type CustomCase,
  type Difficulty,
} from '../api'
import CaseDetailDialog from '../components/CaseDetailDialog.vue'

const router = useRouter()

// Categories filter
const categoriesQuery = useQuery({
  queryKey: ['case-categories'] as const,
  queryFn: listCaseCategories,
  staleTime: 30 * 60 * 1000,
})
const categories = computed(() => categoriesQuery.data.value?.items ?? [])

const activeCategoryId = ref<string | null>(null)
const page = ref(1)
const PAGE_SIZE = 12

const casesQuery = useQuery({
  queryKey: computed(() => ['custom-cases', { cat: activeCategoryId.value, page: page.value }] as const),
  queryFn: () => listCustomCases({
    category_id: activeCategoryId.value ?? undefined,
    page: page.value,
    page_size: PAGE_SIZE,
  }),
  staleTime: 5 * 60 * 1000,
})
const cases = computed(() => casesQuery.data.value?.items ?? [])
const total = computed(() => casesQuery.data.value?.total ?? 0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function setCategory(id: string | null) {
  activeCategoryId.value = id
  page.value = 1
}

// Modal
const activeCase = ref<CustomCase | null>(null)
function openCase(c: CustomCase) { activeCase.value = c }
function closeCase() { activeCase.value = null }

function consultCase(c: CustomCase) {
  // 跳到 /custom/apply 並帶 query 預填
  const q: Record<string, string> = {}
  if (c.canvas_w_cm) q.ref_canvas_w_cm = String(c.canvas_w_cm)
  if (c.canvas_h_cm) q.ref_canvas_h_cm = String(c.canvas_h_cm)
  if (c.difficulty) q.ref_difficulty = c.difficulty
  q.ref_case_title = c.title
  closeCase()
  router.push({ path: '/custom/apply', query: q })
}
</script>

<template>
  <main class="page">
    <RouterLink to="/custom" class="back-link">
      <ArrowLeft :size="14" /> 客製化首頁
    </RouterLink>

    <SectionMasthead
      no="02"
      chapter="Inspiration"
      title="客製案例參考"
      caption="From our archive"
    />

    <p class="intro">
      過去客戶實際完成的客製作品。<br />
      點選案例查看細節，喜歡的話可以「諮詢類似規格」直接帶入您的申請。
    </p>

    <!-- Category filter -->
    <div v-if="categories.length > 0" class="filter-row">
      <button
        type="button"
        class="filter-chip"
        :class="{ active: activeCategoryId === null }"
        @click="setCategory(null)"
      >
        全部
      </button>
      <button
        v-for="c in categories"
        :key="c.id"
        type="button"
        class="filter-chip"
        :class="{ active: activeCategoryId === c.id }"
        @click="setCategory(c.id)"
      >
        {{ c.name }}
      </button>
    </div>

    <!-- Loading -->
    <div v-if="casesQuery.isPending.value" class="state">
      <Loader2 :size="20" class="spin" /> 載入案例中…
    </div>

    <!-- Empty -->
    <div v-else-if="cases.length === 0" class="state empty">
      <FileQuestion :size="32" :stroke-width="1.25" />
      <p class="state-title">{{ activeCategoryId ? '此分類目前沒有案例。' : '案例陸續建構中。' }}</p>
      <RouterLink to="/custom/apply" class="cta">直接開始申請 →</RouterLink>
    </div>

    <!-- Grid -->
    <div v-else class="case-grid">
      <article
        v-for="c in cases"
        :key="c.id"
        class="case-card"
        @click="openCase(c)"
      >
        <div class="case-img">
          <img :src="c.image_url" :alt="c.title" loading="lazy" />
        </div>
        <div class="case-meta">
          <h3>{{ c.title }}</h3>
          <p v-if="c.canvas_w_cm" class="case-spec">
            {{ c.canvas_w_cm }}×{{ c.canvas_h_cm }} cm
            <span v-if="c.difficulty"> · {{ DIFFICULTY_LABEL[c.difficulty as Difficulty] || c.difficulty }}</span>
          </p>
        </div>
        <span class="case-cta">查看詳情 →</span>
      </article>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="pagination">
      <button :disabled="page <= 1" @click="page--">‹</button>
      <span>{{ page }} / {{ totalPages }}</span>
      <button :disabled="page >= totalPages" @click="page++">›</button>
    </div>

    <CaseDetailDialog
      :case-data="activeCase"
      @close="closeCase"
      @consult="consultCase"
    />
  </main>
</template>

<style scoped>
.page { max-width: 1080px; margin: 0 auto; padding: 32px 24px 96px; }
.back-link {
  display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em;
  color: var(--color-ink-muted); text-decoration: none; margin-bottom: 32px;
}
.back-link:hover { color: var(--color-accent-deep); }

.intro {
  font-size: 15px; line-height: 1.85; color: var(--color-ink-default);
  margin: 12px 0 32px; max-width: 640px;
}

.filter-row {
  display: flex; flex-wrap: wrap; gap: 8px;
  margin: 0 0 32px; padding-bottom: 24px; border-bottom: 1px solid var(--color-line);
}
.filter-chip {
  padding: 8px 14px; cursor: pointer;
  background: transparent; border: 1px solid var(--color-line);
  border-radius: var(--radius-xs); font-size: 13px; font-family: inherit;
  color: var(--color-ink-default);
  transition: border-color 150ms, color 150ms, background 150ms;
}
.filter-chip:hover { border-color: var(--color-accent); color: var(--color-accent-deep); }
.filter-chip.active {
  background: var(--color-accent-deep); border-color: var(--color-accent-deep);
  color: #FCF7E5;
}

.state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 12px; padding: 80px 16px; color: var(--color-ink-muted);
}
.state.empty .state-title {
  font-family: var(--font-cn-serif); font-size: 17px;
  color: var(--color-ink-default); margin: 0;
}
.cta {
  font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.2em;
  color: var(--color-accent-deep); text-decoration: none;
  border-bottom: 1px solid currentColor; padding-bottom: 2px;
}

.case-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 24px;
}
.case-card {
  position: relative; cursor: pointer;
  border: 1px solid var(--color-line); border-radius: var(--radius-sm);
  overflow: hidden; background: #FFF;
  transition: border-color 200ms, transform 200ms;
}
.case-card:hover { border-color: var(--color-accent); transform: translateY(-2px); }
.case-card:hover .case-cta { opacity: 1; transform: translateY(0); }
.case-img { aspect-ratio: 4 / 3; overflow: hidden; background: var(--color-paper-surface, #FCF7E5); }
.case-img img { width: 100%; height: 100%; object-fit: cover; }
.case-meta { padding: 14px 16px 12px; border-top: 1px solid var(--color-line); }
.case-meta h3 { font-family: var(--font-cn-serif); font-weight: 400; font-size: 15px; color: var(--color-ink-strong); margin: 0 0 4px; }
.case-spec { font-family: var(--font-mono); font-size: 11px; color: var(--color-ink-muted); margin: 0; letter-spacing: 0.06em; }
.case-cta {
  position: absolute; bottom: 12px; right: 14px;
  font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.16em;
  color: var(--color-accent-deep);
  background: var(--color-paper-surface, #FCF7E5);
  padding: 4px 10px; border-radius: 999px;
  opacity: 0; transform: translateY(4px);
  transition: opacity 200ms, transform 200ms;
}

.pagination {
  margin-top: 40px; display: flex; justify-content: center; align-items: center;
  gap: 16px; font-family: var(--font-mono); font-size: 13px;
  color: var(--color-ink-default);
}
.pagination button {
  width: 32px; height: 32px; cursor: pointer;
  background: transparent; border: 1px solid var(--color-line);
  border-radius: var(--radius-xs); font-size: 16px; color: var(--color-ink-default);
}
.pagination button:disabled { opacity: 0.3; cursor: not-allowed; }
.pagination button:hover:not(:disabled) { border-color: var(--color-accent); color: var(--color-accent-deep); }

.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
