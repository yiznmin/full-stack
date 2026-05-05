<script setup lang="ts">
import { ref } from 'vue'
import { ChevronDown } from 'lucide-vue-next'

defineProps<{
  description: string | null
}>()

interface Section {
  key: string
  title: string
  body: string
}

// 品牌共通說明（store 端寫死、每個商品都有）
const SECTIONS: Section[] = [
  {
    key: 'kit',
    title: '畫具內容',
    body:
      '每份 kit 包含：已繃好的畫布（含基底框架）、配好色號的水性壓克力顏料、3 支不同粗細的畫筆、色號對照表、操作說明書。',
  },
  {
    key: 'canvas',
    title: '畫布材質',
    body:
      '加厚棉麻畫布，pre-primed 適合壓克力顏料，繃在 1.5 cm 厚 FSC 認證松木框架上。完成後可直接掛牆。',
  },
  {
    key: 'tip',
    title: '使用建議',
    body:
      '建議從大色塊先畫，由淺到深；同色號區塊一次畫完。顏料約 30 分鐘表面乾、24 小時完全乾。塗錯時等乾燥後用旁邊正確顏色覆蓋即可。',
  },
  {
    key: 'note',
    title: '注意事項',
    body:
      '水性壓克力顏料無毒但仍應避免幼兒誤食、寵物舔食。畫畫過程保持通風。完成的畫避免長時間日曬以延緩褪色。',
  },
]

const open = ref<Record<string, boolean>>({
  kit: true,
})

function toggle(key: string) {
  open.value[key] = !open.value[key]
}
</script>

<template>
  <div class="desc">
    <!-- 商家自填的商品描述（admin 寫的 markdown / 純文字） -->
    <section v-if="description" class="lead">
      <h3 class="lead-title">關於這幅畫</h3>
      <p class="lead-body">{{ description }}</p>
    </section>

    <!-- 品牌共通 4 區（每個商品都有）-->
    <section v-for="s in SECTIONS" :key="s.key" class="acc">
      <button
        type="button"
        class="acc-toggle"
        :aria-expanded="!!open[s.key]"
        @click="toggle(s.key)"
      >
        <span class="acc-title">{{ s.title }}</span>
        <ChevronDown class="acc-chevron" :class="{ 'is-open': open[s.key] }" />
      </button>
      <div v-show="open[s.key]" class="acc-body">
        <p>{{ s.body }}</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.desc {
  display: flex;
  flex-direction: column;
}

.lead {
  padding: 24px 0 32px;
  border-bottom: 1px solid var(--color-line-subtle);
  margin-bottom: 8px;
}
.lead-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 18px;
  letter-spacing: 0.04em;
  color: var(--color-ink-strong);
  margin: 0 0 14px;
}
.lead-body {
  font-size: 14px;
  line-height: 2;
  color: var(--color-ink-default);
  letter-spacing: 0.04em;
  margin: 0;
  white-space: pre-wrap;
}

.acc {
  border-bottom: 1px solid var(--color-line-subtle);
}

.acc-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: transparent;
  border: none;
  padding: 18px 0;
  cursor: pointer;
  font-family: inherit;
}

.acc-title {
  font-family: var(--font-cn-serif);
  font-weight: 300;
  font-size: 16px;
  letter-spacing: 0.06em;
  color: var(--color-ink-strong);
}

.acc-chevron {
  width: 14px; height: 14px;
  stroke: var(--color-ink-muted); stroke-width: 1.5; fill: none;
  transition: transform 200ms;
}
.acc-chevron.is-open {
  transform: rotate(180deg);
  stroke: var(--color-accent);
}

.acc-body {
  padding: 0 0 24px;
}
.acc-body p {
  font-size: 13px;
  line-height: 2;
  color: var(--color-ink-default);
  letter-spacing: 0.04em;
  margin: 0;
}
</style>
