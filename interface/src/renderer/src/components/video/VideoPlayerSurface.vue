<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { FileVideo, Loader2 } from '@lucide/vue'
import { api, hasNativeApi } from '../../services/native'
import { useVideoPreviewPipeline } from '../../composables/useVideoPreviewPipeline'
import type { MediaHandle } from '../../services/api'
import type { VideoAdjustments } from '../../composables/useVideoEdits'

// T025/T045 (specs/007-video-editor-player) — the <video> element and the
// canvas the preview shader draws into.
//
// Media is served through the astros-media:// scheme the main process already
// registers (research.md Decisão 8). That handler answers byte-Range requests,
// which is not a detail: without it the timeline is unseekable and the whole
// file is pulled into memory to show a preview.
//
// The <video> itself is hidden once the shader is running, and the canvas shown
// in its place. It keeps decoding and keeps driving playback — it is the source
// texture, not a fallback.

const props = defineProps<{
  handle: MediaHandle | null
  /** Local path for the astros-media:// URL. Display/rendering only — never
      sent to the API (Princípio XIII). */
  sourcePath: string | null
  adjustments: VideoAdjustments | null
  /** True while the on-demand preview is being recalculated (FR-014). */
  recalculating?: boolean
}>()

const emit = defineEmits<{ ready: [HTMLVideoElement] }>()

const { t } = useI18n()
const video = ref<HTMLVideoElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
const failed = ref(false)

const pipeline = useVideoPreviewPipeline()
const sourceUrl = ref('')

function refreshSource(): void {
  failed.value = false
  // content_key busts the cache when the file changed underneath us (FR-017):
  // the same path with different bytes must not reuse a decoded stream.
  sourceUrl.value =
    hasNativeApi && props.sourcePath
      ? `${api.toFileUrl(props.sourcePath)}?v=${props.handle?.content_key ?? ''}`
      : ''
}

watch(() => [props.sourcePath, props.handle?.content_key], refreshSource, { immediate: true })

// Adjustments are pushed to the pipeline rather than read by it, so the shader
// has no opinion about where state lives.
watch(
  () => props.adjustments,
  (value) => {
    if (value) pipeline.apply(value)
  },
  { immediate: true, deep: true }
)

function startPipeline(): void {
  if (video.value && canvas.value) pipeline.start(video.value, canvas.value)
}

onMounted(() => {
  if (video.value) {
    emit('ready', video.value)
    startPipeline()
  }
})

watch(video, (element) => {
  if (element) {
    emit('ready', element)
    startPipeline()
  }
})
</script>

<template>
  <div class="video-surface">
    <template v-if="sourceUrl && !failed">
      <video
        ref="video"
        :src="sourceUrl"
        class="video-canvas"
        :class="{ hidden: pipeline.supported.value }"
        preload="metadata"
        playsinline
        crossorigin="anonymous"
        @error="failed = true"
      />
      <canvas v-show="pipeline.supported.value" ref="canvas" class="video-canvas" />

      <!-- FR-014: say when the preview is being recalculated, rather than
           showing a stale frame that looks current. -->
      <div
        v-if="recalculating"
        class="absolute right-3 top-3 flex items-center gap-1.5 rounded bg-surface-2/90 px-2 py-1 text-(length:--fs-caption) text-text-tertiary"
      >
        <Loader2 :size="13" class="animate-spin" />
        {{ t('videoEditor.player.recalculating') }}
      </div>

      <!-- Without WebGL2 the untouched frame is all we can show. Saying so is
           the difference between an honest limitation and a preview that
           silently ignores every adjustment (FR-015). -->
      <p
        v-if="!pipeline.supported.value"
        class="absolute bottom-3 left-3 rounded bg-surface-2/90 px-2 py-1 text-(length:--fs-caption) text-text-tertiary"
      >
        {{ t('videoEditor.player.previewUnavailable') }}
      </p>
    </template>

    <!-- FR-011: an empty box with no explanation reads as a broken app. Say
         that the file cannot be shown, and let the person move on. -->
    <div v-else class="flex flex-col items-center gap-2 p-8 text-center text-text-tertiary">
      <FileVideo :size="32" />
      <p class="text-(length:--fs-caption)">{{ t('videoEditor.player.notPreviewable') }}</p>
    </div>
  </div>
</template>

<style scoped>
.video-surface {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-height: 0;
  background: var(--surface-1);
}

/* Both the <video> and the canvas use this. max-* rather than a fixed size:
   the element keeps its own aspect ratio and grows until whichever edge runs
   out first, so a tall clip and a wide one both fill the stage without
   distortion. */
.video-canvas {
  max-width: 100%;
  max-height: 100%;
  display: block;
}

/* The <video> stays in the tree while the shader draws — it is the source
   texture, not a fallback — but must not take layout space alongside the
   canvas. */
.hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  pointer-events: none;
}
</style>
