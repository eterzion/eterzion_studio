<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

// T027 (specs/007-video-editor-player) — FR-007.
//
// Scrubbing is pointer-based rather than an <input type="range"> because the
// timeline has to carry things a range input cannot: the thumbnail strip
// (FR-007a) and the trim handles (FR-007b) draw inside this same box. A range
// input would have meant faking those on top of a control that owns its own
// rendering.
//
// Keyboard access is not lost by that choice: the element is focusable and
// handles arrow keys itself, which is what FR-010 asks for.

const props = defineProps<{
  progress: number
  duration: number
  currentTime: number
  formatTime: (seconds: number) => string
  disabled?: boolean
}>()

const emit = defineEmits<{ seek: [progress: number] }>()

const { t } = useI18n()
const track = ref<HTMLElement | null>(null)
const scrubbing = ref(false)

function progressFromEvent(event: PointerEvent): number {
  const box = track.value?.getBoundingClientRect()
  if (!box || box.width === 0) return 0
  return Math.min(1, Math.max(0, (event.clientX - box.left) / box.width))
}

function onPointerDown(event: PointerEvent): void {
  if (props.disabled) return
  scrubbing.value = true
  // Capture on the track, so a drag that leaves the element keeps scrubbing
  // instead of stopping the moment the pointer crosses the edge.
  track.value?.setPointerCapture(event.pointerId)
  emit('seek', progressFromEvent(event))
}

function onPointerMove(event: PointerEvent): void {
  if (!scrubbing.value) return
  emit('seek', progressFromEvent(event))
}

function onPointerUp(event: PointerEvent): void {
  if (!scrubbing.value) return
  scrubbing.value = false
  track.value?.releasePointerCapture(event.pointerId)
}

// A second of arrow-key movement, five with shift. Proportional stepping would
// make a long video unnavigable and a short one jumpy.
function onKeydown(event: KeyboardEvent): void {
  if (props.disabled || props.duration <= 0) return
  const step = event.shiftKey ? 5 : 1
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    emit('seek', Math.max(0, (props.currentTime - step) / props.duration))
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    emit('seek', Math.min(1, (props.currentTime + step) / props.duration))
  } else if (event.key === 'Home') {
    event.preventDefault()
    emit('seek', 0)
  } else if (event.key === 'End') {
    event.preventDefault()
    emit('seek', 1)
  }
}
</script>

<template>
  <div
    ref="track"
    class="group relative h-6 cursor-pointer touch-none select-none py-2.5"
    :class="{ 'pointer-events-none opacity-50': disabled }"
    role="slider"
    tabindex="0"
    :aria-label="t('videoEditor.player.timeline')"
    :aria-valuemin="0"
    :aria-valuemax="Math.round(duration)"
    :aria-valuenow="Math.round(currentTime)"
    :aria-valuetext="formatTime(currentTime)"
    @pointerdown="onPointerDown"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
    @pointercancel="onPointerUp"
    @keydown="onKeydown"
  >
    <!-- Slot for the thumbnail strip and trim handles, which draw in this same
         coordinate space (T039, T048). -->
    <slot name="track-background" />

    <div class="relative h-1 w-full rounded-full bg-surface-3">
      <div
        class="absolute inset-y-0 left-0 rounded-full bg-accent"
        :style="{ width: `${progress * 100}%` }"
      />
      <div
        class="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent opacity-0 transition-opacity group-hover:opacity-100"
        :class="{ 'opacity-100': scrubbing }"
        :style="{ left: `${progress * 100}%` }"
      />
    </div>
  </div>
</template>
