<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ImageOff, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import type { ProductImage } from '../api'

const props = defineProps<{
  cover: string
  /** 額外圖片（cover 不重複包含）— 可能是 list or wrapped {items} */
  extras?: ProductImage[]
  /** 選定變體的 filled_template URL — 切到 variant 時顯示 */
  variantImage?: string | null
  alt: string
}>()

const allImages = computed(() => {
  const base: { url: string; key: string; label?: string }[] = []
  if (props.cover) base.push({ url: props.cover, key: 'cover', label: '封面' })
  for (const img of props.extras ?? []) {
    base.push({ url: img.image_url, key: img.id })
  }
  if (props.variantImage) {
    base.push({ url: props.variantImage, key: 'variant', label: '配色預覽' })
  }
  return base
})

const activeIdx = ref(0)
const errorMap = ref<Record<string, boolean>>({})

watch(
  () => allImages.value.length,
  () => {
    if (activeIdx.value >= allImages.value.length) activeIdx.value = 0
  },
)

watch(
  () => props.variantImage,
  (val) => {
    if (val) {
      // 切到 variant 圖
      activeIdx.value = allImages.value.findIndex((i) => i.key === 'variant')
      if (activeIdx.value < 0) activeIdx.value = 0
    }
  },
)

function go(idx: number) {
  if (idx < 0 || idx >= allImages.value.length) return
  activeIdx.value = idx
}
function prev() { go(activeIdx.value - 1) }
function next() { go(activeIdx.value + 1) }

const activeImage = computed(() => allImages.value[activeIdx.value])
const showFallback = computed(
  () => allImages.value.length === 0 || (activeImage.value && errorMap.value[activeImage.value.key]),
)
</script>

<template>
  <div class="gallery">
    <div class="main">
      <Transition name="fade" mode="out-in">
        <div
          v-if="showFallback"
          key="fallback"
          class="main-fallback"
        >
          <ImageOff class="fallback-icon" />
          <span class="fallback-text">商品圖即將上線</span>
        </div>
        <img
          v-else
          :key="activeImage.key"
          :src="activeImage.url"
          :alt="alt"
          @error="errorMap[activeImage.key] = true"
        />
      </Transition>

      <button
        v-if="allImages.length > 1"
        class="nav-btn nav-prev"
        :disabled="activeIdx <= 0"
        aria-label="上一張"
        @click="prev"
      ><ChevronLeft /></button>
      <button
        v-if="allImages.length > 1"
        class="nav-btn nav-next"
        :disabled="activeIdx >= allImages.length - 1"
        aria-label="下一張"
        @click="next"
      ><ChevronRight /></button>

      <span v-if="activeImage?.label" class="image-label">{{ activeImage.label }}</span>
    </div>

    <ul v-if="allImages.length > 1" class="thumbs">
      <li v-for="(img, i) in allImages" :key="img.key">
        <button
          type="button"
          class="thumb"
          :class="{ 'thumb-active': i === activeIdx }"
          @click="go(i)"
        >
          <ImageOff v-if="errorMap[img.key]" class="thumb-fallback-icon" />
          <img v-else :src="img.url" :alt="`${alt} ${i + 1}`" @error="errorMap[img.key] = true" />
        </button>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.gallery {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.main {
  position: relative;
  aspect-ratio: 4 / 5;
  background: var(--color-paper-deep);
  overflow: hidden;
  border: 1px solid var(--color-line-subtle);
}

.main img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: sepia(0.05) saturate(0.95);
}

.main-fallback {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: linear-gradient(135deg, var(--color-paper-deep) 0%, var(--color-accent-tint) 60%, var(--color-accent-soft) 120%);
  color: var(--color-ink-muted);
}
.fallback-icon {
  width: 40px; height: 40px;
  stroke: currentColor; stroke-width: 1.25; fill: none; opacity: 0.5;
}
.fallback-text {
  font-family: var(--font-body);
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  opacity: 0.7;
}

.nav-btn {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 40px; height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(245, 241, 232, 0.85);
  backdrop-filter: blur(8px);
  border: 1px solid var(--color-line-subtle);
  border-radius: 50%;
  color: var(--color-ink-strong);
  cursor: pointer;
  transition: all 200ms;
}
.nav-btn:hover:not(:disabled) {
  background: var(--color-paper-canvas);
  border-color: var(--color-accent);
}
.nav-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.nav-prev { left: 12px; }
.nav-next { right: 12px; }
.nav-btn :deep(svg) { width: 16px; height: 16px; stroke: currentColor; stroke-width: 1.5; fill: none; }

.image-label {
  position: absolute;
  bottom: 12px;
  left: 12px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-paper-canvas);
  background: rgba(46, 40, 35, 0.55);
  padding: 4px 10px;
  border-radius: var(--radius-xs);
  backdrop-filter: blur(4px);
}

.thumbs {
  display: flex;
  gap: 10px;
  list-style: none;
  padding: 0; margin: 0;
}

.thumb {
  width: 64px; height: 80px;
  background: var(--color-paper-deep);
  border: 1px solid var(--color-line-subtle);
  cursor: pointer;
  padding: 0;
  overflow: hidden;
  transition: border-color 150ms;
  display: flex;
  align-items: center;
  justify-content: center;
}
.thumb:hover { border-color: var(--color-accent-soft); }
.thumb-active {
  border-color: var(--color-accent);
  box-shadow: inset 0 0 0 1px var(--color-accent);
}
.thumb img {
  width: 100%; height: 100%;
  object-fit: cover;
  filter: sepia(0.05) saturate(0.95);
}
.thumb-fallback-icon {
  width: 18px; height: 18px;
  stroke: var(--color-ink-muted); stroke-width: 1.5; fill: none; opacity: 0.5;
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 240ms ease;
}
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
