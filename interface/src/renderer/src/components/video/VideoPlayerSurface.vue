<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { FileVideo } from '@lucide/vue'
import { api, hasNativeApi } from '../../services/native'
import type { MediaHandle } from '../../services/api'

// T025 (specs/007-video-editor-player) — the <video> element itself.
//
// Media is served through the astros-media:// scheme the main process already
// registers (research.md Decisão 8). That handler answers byte-Range requests,
// which is not a detail: without it the timeline is unseekable and the whole
// file is pulled into memory to show a preview. Reimplementing it here would
// have reintroduced a bug the codebase already fixed.
//
// The source path comes from the caller rather than from the handle, because a
// handle deliberately never carries a path (Princípio XIII) — the renderer
// keeps the dialog-supplied path for display purposes only, and every API call
// uses the identifier.

const props = defineProps<{
  handle: MediaHandle | null
  /** Local path for the astros-media:// URL. Display/rendering only — never
      sent to the API. */
  sourcePath: string | null
}>()

const emit = defineEmits<{ ready: [HTMLVideoElement] }>()

const { t } = useI18n()
const video = ref<HTMLVideoElement | null>(null)
const failed = ref(false)

// content_key busts the cache when the file changed underneath us (FR-017):
// the same path with different bytes must not reuse a decoded stream.
const sourceUrl = ref('')

function refreshSource(): void {
  failed.value = false
  sourceUrl.value =
    hasNativeApi && props.sourcePath
      ? `${api.toFileUrl(props.sourcePath)}?v=${props.handle?.content_key ?? ''}`
      : ''
}

watch(() => [props.sourcePath, props.handle?.content_key], refreshSource, { immediate: true })

onMounted(() => {
  if (video.value) emit('ready', video.value)
})

watch(video, (element) => {
  if (element) emit('ready', element)
})
</script>

<template>
  <div class="relative flex h-full w-full items-center justify-center bg-surface-1">
    <video
      v-if="sourceUrl && !failed"
      ref="video"
      :src="sourceUrl"
      class="max-h-full max-w-full"
      preload="metadata"
      playsinline
      @error="failed = true"
    />

    <!-- FR-011: an empty box with no explanation reads as a broken app. Say
         that the file cannot be shown, and let the person move on. -->
    <div v-else class="flex flex-col items-center gap-2 p-8 text-center text-text-tertiary">
      <FileVideo :size="32" />
      <p class="text-(length:--fs-caption)">{{ t('videoEditor.player.notPreviewable') }}</p>
    </div>
  </div>
</template>
