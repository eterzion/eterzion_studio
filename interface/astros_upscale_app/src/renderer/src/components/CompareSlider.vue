<script setup lang="ts">
import { ref } from 'vue'
import { MoveHorizontal } from '@lucide/vue'

withDefaults(
  defineProps<{
    beforeSrc: string
    afterSrc: string
    /** Shared viewport transform (zoom/pan) applied to both images — the clip and
     *  the divider stay in container coordinates so the handle doesn't scale. */
    mediaStyle?: Record<string, string>
  }>(),
  { mediaStyle: () => ({}) }
)

const position = ref(50)
const dragging = ref(false)
const container = ref<HTMLDivElement | null>(null)

function updateFromClientX(clientX: number): void {
  const el = container.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const pct = ((clientX - rect.left) / rect.width) * 100
  position.value = Math.min(100, Math.max(0, pct))
}

function onPointerDown(e: PointerEvent): void {
  dragging.value = true
  updateFromClientX(e.clientX)
  ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
}

function onPointerMove(e: PointerEvent): void {
  if (!dragging.value) return
  updateFromClientX(e.clientX)
}

function onPointerUp(): void {
  dragging.value = false
}
</script>

<template>
  <div
    ref="container"
    class="compare"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
  >
    <div class="layer-clip">
      <img :src="afterSrc" alt="Depois" class="media" draggable="false" :style="mediaStyle" />
    </div>
    <div class="layer-clip" :style="{ clipPath: `inset(0 ${100 - position}% 0 0)` }">
      <img :src="beforeSrc" alt="Antes" class="media" draggable="false" :style="mediaStyle" />
    </div>

    <span class="tag tag-before">Antes</span>
    <span class="tag tag-after">Depois</span>

    <div class="handle" :style="{ left: position + '%' }">
      <div class="handle-line" />
      <div class="handle-knob"><MoveHorizontal :size="14" /></div>
    </div>
  </div>
</template>

<style scoped>
.compare {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  border-radius: var(--radius-md);
  cursor: ew-resize;
  user-select: none;
  touch-action: none;
}

.layer-clip {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.media {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.tag {
  position: absolute;
  top: var(--space-3);
  font-size: 11px;
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  background: rgba(11, 14, 20, 0.72);
  padding: 3px 8px;
  border-radius: 999px;
  letter-spacing: 0.03em;
  pointer-events: none;
}

.tag-before {
  left: var(--space-3);
}

.tag-after {
  right: var(--space-3);
}

.handle {
  position: absolute;
  top: 0;
  bottom: 0;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.handle-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #fff;
  box-shadow: var(--shadow-sm);
}

.handle-knob {
  position: relative;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #fff;
  color: var(--surface-1);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-md);
}
</style>
