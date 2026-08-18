<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { VideoTrim } from '../../composables/useVideoEdits'

// T048 (specs/007-video-editor-player) — FR-007b.
//
// Draws in the timeline's coordinate space, through its track-background slot.
// The excluded regions are dimmed rather than hidden: a person needs to see how
// much is being left out, not only what is being kept.

const props = defineProps<{ trim: VideoTrim | null; duration: number; disabled?: boolean }>()

const emit = defineEmits<{ update: [trim: VideoTrim] }>()

const { t } = useI18n()
const root = ref<HTMLElement | null>(null)
const dragging = ref<'start' | 'end' | null>(null)

const startPercent = computed(() =>
  props.duration > 0 && props.trim ? (props.trim.start_seconds / props.duration) * 100 : 0
)
const endPercent = computed(() =>
  props.duration > 0 && props.trim ? (props.trim.end_seconds / props.duration) * 100 : 100
)

function secondsFromEvent(event: PointerEvent): number {
  const box = root.value?.getBoundingClientRect()
  if (!box || box.width === 0) return 0
  const fraction = Math.min(1, Math.max(0, (event.clientX - box.left) / box.width))
  return fraction * props.duration
}

function onPointerDown(handle: 'start' | 'end', event: PointerEvent): void {
  if (props.disabled) return
  // Stops the timeline underneath treating this as a scrub. Dragging a trim
  // handle is not seeking, and doing both at once fights the person.
  event.stopPropagation()
  dragging.value = handle
  ;(event.target as HTMLElement).setPointerCapture(event.pointerId)
}

function onPointerMove(event: PointerEvent): void {
  if (!dragging.value || !props.trim) return
  event.stopPropagation()
  const seconds = secondsFromEvent(event)
  // The handles cannot cross. Letting them would produce a negative duration
  // that the ceiling check would then reject for a reason that looks unrelated
  // to what the person just did.
  if (dragging.value === 'start') {
    emit('update', {
      ...props.trim,
      start_seconds: Math.min(seconds, props.trim.end_seconds - 0.1)
    })
  } else {
    emit('update', {
      ...props.trim,
      end_seconds: Math.max(seconds, props.trim.start_seconds + 0.1)
    })
  }
}

function onPointerUp(event: PointerEvent): void {
  if (!dragging.value) return
  event.stopPropagation()
  dragging.value = null
}
</script>

<template>
  <div
    v-if="trim"
    ref="root"
    class="pointer-events-none absolute inset-0"
    @pointermove="onPointerMove"
    @pointerup="onPointerUp"
  >
    <!-- Excluded regions, dimmed. Seeing what is left out is the point. -->
    <div class="absolute inset-y-0 left-0 bg-surface-1/70" :style="{ width: startPercent + '%' }" />
    <div
      class="absolute inset-y-0 right-0 bg-surface-1/70"
      :style="{ width: 100 - endPercent + '%' }"
    />

    <button
      class="pointer-events-auto absolute inset-y-0 w-2 -translate-x-1/2 cursor-ew-resize rounded bg-accent"
      type="button"
      :disabled="disabled"
      :aria-label="t('videoEditor.edits.trimStart')"
      :style="{ left: startPercent + '%' }"
      @pointerdown="onPointerDown('start', $event)"
    />
    <button
      class="pointer-events-auto absolute inset-y-0 w-2 -translate-x-1/2 cursor-ew-resize rounded bg-accent"
      type="button"
      :disabled="disabled"
      :aria-label="t('videoEditor.edits.trimEnd')"
      :style="{ left: endPercent + '%' }"
      @pointerdown="onPointerDown('end', $event)"
    />
  </div>
</template>
