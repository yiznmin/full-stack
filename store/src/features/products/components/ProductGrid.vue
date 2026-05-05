<script setup lang="ts">
import type { ProductBrief } from '../api'
import ProductCard from './ProductCard.vue'

defineProps<{
  products: ProductBrief[]
  /** Dev 預覽模式 — 卡片標「示意」+ 不可點擊 */
  preview?: boolean
  /** 顯示 No. 編號（首頁 4 卡用，列表頁通常不用） */
  showNumber?: boolean
}>()
</script>

<template>
  <div class="grid">
    <ProductCard
      v-for="(p, idx) in products"
      :key="p.id"
      :product="p"
      :number="showNumber ? String(idx + 1).padStart(2, '0') : undefined"
      :preview="preview"
    />
  </div>
</template>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 32px;
}

@media (max-width: 1279px) {
  .grid { grid-template-columns: repeat(3, 1fr); gap: 28px; }
}
@media (max-width: 1023px) {
  .grid { grid-template-columns: repeat(2, 1fr); gap: 24px; }
}
@media (max-width: 767px) {
  .grid { grid-template-columns: 1fr; gap: 20px; }
}
</style>
