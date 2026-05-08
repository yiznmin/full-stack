<script setup lang="ts">
import { X, ArrowRight } from 'lucide-vue-next'
import { DIFFICULTY_LABEL, type CustomCase, type Difficulty } from '../api'

const props = defineProps<{
  caseData: CustomCase | null
}>()

const emit = defineEmits<{
  close: []
  consult: [caseData: CustomCase]
}>()

function onConsult() {
  if (props.caseData) emit('consult', props.caseData)
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div v-if="caseData" class="overlay" @click.self="emit('close')">
        <div class="modal" role="dialog" aria-modal="true">
          <button class="modal-close" @click="emit('close')" aria-label="關閉">
            <X :size="18" />
          </button>

          <div class="modal-body">
            <figure class="case-figure">
              <img :src="caseData.image_url" :alt="caseData.title" />
            </figure>
            <div class="case-content">
              <div class="kicker">
                <span class="kicker-no">CASE</span>
                <span class="kicker-dot"></span>
                <span class="kicker-chapter">客製案例</span>
              </div>
              <h2>{{ caseData.title }}</h2>
              <dl class="meta">
                <div v-if="caseData.canvas_w_cm">
                  <dt>尺寸</dt>
                  <dd>{{ caseData.canvas_w_cm }}×{{ caseData.canvas_h_cm }} cm</dd>
                </div>
                <div v-if="caseData.difficulty">
                  <dt>難度</dt>
                  <dd>{{ DIFFICULTY_LABEL[caseData.difficulty as Difficulty] || caseData.difficulty }}</dd>
                </div>
              </dl>
              <p v-if="caseData.description" class="desc">{{ caseData.description }}</p>
            </div>
          </div>

          <footer class="modal-footer">
            <button class="cta" @click="onConsult">
              諮詢類似規格 <ArrowRight :size="14" />
            </button>
            <button class="cta-ghost" @click="emit('close')">關閉</button>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed; inset: 0; z-index: 70;
  background: rgba(43, 36, 27, 0.55);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.modal {
  position: relative; width: 100%; max-width: 720px;
  max-height: 90vh; overflow: hidden;
  background: var(--color-paper-base, #F7F1E3);
  border-radius: var(--radius-md);
  display: flex; flex-direction: column;
}
.modal-close {
  position: absolute; top: 16px; right: 16px; z-index: 1;
  width: 36px; height: 36px; cursor: pointer;
  border: 0; background: rgba(255, 255, 255, 0.92);
  border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  color: var(--color-ink-strong);
  box-shadow: 0 2px 8px rgba(43, 36, 27, 0.12);
}
.modal-close:hover { background: #FFF; }

.modal-body {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 0; flex: 1; overflow-y: auto;
}
@media (max-width: 720px) {
  .modal-body { grid-template-columns: 1fr; }
}

.case-figure {
  margin: 0; aspect-ratio: 4 / 3;
  background: var(--color-paper-surface, #FCF7E5);
  overflow: hidden;
}
.case-figure img { width: 100%; height: 100%; object-fit: cover; display: block; }

.case-content { padding: 32px 36px; }
.kicker {
  display: flex; align-items: center; gap: 10px; margin-bottom: 16px;
}
.kicker-no { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.22em; color: var(--color-fresh); }
.kicker-dot { width: 4px; height: 4px; border-radius: 50%; background: var(--color-accent); }
.kicker-chapter { font-family: var(--font-display); font-style: italic; font-size: 14px; color: var(--color-accent); }

.case-content h2 {
  font-family: var(--font-cn-serif); font-weight: 300;
  font-size: 26px; letter-spacing: 0.04em;
  color: var(--color-ink-strong); margin: 0 0 20px; line-height: 1.3;
}
.meta { display: grid; grid-template-columns: 80px 1fr; gap: 8px 16px; margin: 0 0 20px; }
.meta > div { display: contents; }
.meta dt {
  font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.18em;
  color: var(--color-ink-muted); padding-top: 2px;
}
.meta dd { font-size: 14px; color: var(--color-ink-strong); margin: 0; }

.desc {
  font-size: 14px; color: var(--color-ink-default);
  line-height: 1.8; white-space: pre-line; margin: 0;
}

.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--color-line);
  background: var(--color-paper-surface, #FCF7E5);
  display: flex; gap: 12px; justify-content: flex-end;
}
.cta, .cta-ghost {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 10px 20px; cursor: pointer;
  border-radius: var(--radius-xs);
  font-family: var(--font-cn-serif); font-size: 14px; letter-spacing: 0.06em;
}
.cta {
  background: var(--color-accent-deep); color: #FCF7E5; border: 0;
}
.cta:hover { background: var(--color-accent); }
.cta-ghost {
  background: transparent; color: var(--color-ink-default);
  border: 1px solid var(--color-line);
}
.cta-ghost:hover { border-color: var(--color-accent); color: var(--color-accent-deep); }

.modal-enter-active, .modal-leave-active { transition: opacity 200ms; }
.modal-enter-active .modal, .modal-leave-active .modal { transition: transform 200ms, opacity 200ms; }
.modal-enter-from, .modal-leave-to { opacity: 0; }
.modal-enter-from .modal, .modal-leave-to .modal { transform: translateY(8px); opacity: 0; }
</style>
