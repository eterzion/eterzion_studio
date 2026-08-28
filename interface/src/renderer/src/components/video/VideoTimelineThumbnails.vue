<script setup lang="ts">
import { computed } from 'vue'

// T039 (specs/007-video-editor-player) — FR-007a.
//
// The sprite is one horizontal row of frames. Rendering it as a repeating
// background rather than N <img> elements keeps a three-hour video's strip to a
// single decode, and lets the browser scale the row to whatever width the
// timeline happens to have.

const props = defineProps<{
  spriteUrl: string | null
  count: number
  thumbWidth: number
  thumbHeight: number
}>()

// Rendered height is fixed; the width each frame occupies follows from the
// source's aspect ratio so the pictures are not stretched.
const STRIP_HEIGHT = 32

const style = computed(() => {
  if (!props.spriteUrl || props.count < 1 || props.thumbHeight < 1) return undefined
  const scale = STRIP_HEIGHT / props.thumbHeight
  return {
    backgroundImage: `url(${props.spriteUrl})`,
    // The sprite is count frames wide; scaling by the height ratio keeps each
    // frame's own proportions.
    backgroundSize: `${props.count * props.thumbWidth * scale}px ${STRIP_HEIGHT}px`,
    backgroundRepeat: 'no-repeat',
    height: `${STRIP_HEIGHT}px`
  }
})
</script>

<template>
  <div
    v-if="style"
    class="pointer-events-none absolute inset-x-0 bottom-full mb-1 overflow-hidden rounded opacity-70"
    :style="style"
    aria-hidden="true"
  />
</template>
