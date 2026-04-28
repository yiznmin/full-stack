<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'
import { X } from 'lucide-vue-next'

const props = defineProps<{
  open: boolean
  title?: string
  size?: 'sm' | 'md' | 'lg'
}>()

const emit = defineEmits<{
  close: []
}>()

function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.open) {
    emit('close')
  }
}

watch(() => props.open, (v) => {
  if (typeof document === 'undefined') return
  document.body.style.overflow = v ? 'hidden' : ''
})

onMounted(() => {
  window.addEventListener('keydown', onKey)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})

const widthClass = {
  sm: 'max-w-[400px]',
  md: 'max-w-[520px]',
  lg: 'max-w-[720px]',
}
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center p-5 bg-ink-strong/40"
        @click.self="$emit('close')"
      >
        <Transition
          appear
          enter-active-class="transition-all duration-150 ease-out"
          enter-from-class="opacity-0 -translate-y-1"
          enter-to-class="opacity-100 translate-y-0"
        >
          <div
            class="bg-paper-surface border border-line-hairline rounded-[var(--radius-md)] shadow-[0_4px_16px_rgba(43,38,32,0.08)] w-full overflow-hidden"
            :class="widthClass[size ?? 'md']"
            role="dialog"
            aria-modal="true"
          >
            <header
              v-if="title || $slots.header"
              class="flex items-center justify-between px-6 py-4 border-b border-line-hairline"
            >
              <h2 class="font-display text-ink-strong text-[18px] leading-[26px]">
                <slot name="header">{{ title }}</slot>
              </h2>
              <button
                type="button"
                class="p-1 -mr-1 text-ink-muted hover:text-ink-strong transition-colors"
                aria-label="Close"
                @click="$emit('close')"
              >
                <X :size="18" :stroke-width="1.5" />
              </button>
            </header>

            <div class="px-6 py-5">
              <slot />
            </div>

            <footer
              v-if="$slots.footer"
              class="flex items-center justify-end gap-2 px-6 py-4 border-t border-line-hairline bg-paper-canvas"
            >
              <slot name="footer" />
            </footer>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>
