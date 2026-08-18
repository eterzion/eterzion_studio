<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { AlertCircle } from '@lucide/vue'
import TopBar from '../components/TopBar.vue'
import UploadZone from '../components/UploadZone.vue'
import MediaEditorShell, { type EditorItem } from '../components/MediaEditorShell.vue'
import VideoPlayer from '../components/video/VideoPlayer.vue'
import VideoAdjustmentsPanel from '../components/video/VideoAdjustmentsPanel.vue'
import VideoTransformPanel from '../components/video/VideoTransformPanel.vue'
import VideoTrimHandles from '../components/video/VideoTrimHandles.vue'
import { usePickFiles } from '../composables/usePickFiles'
import {
  useVideoEdits,
  type VideoAdjustments,
  type VideoEffects,
  type VideoTransform,
  type VideoTrim
} from '../composables/useVideoEdits'
import { useVideoTimeline } from '../composables/useVideoTimeline'
import { registerMediaHandle, type MediaHandle } from '../services/api'
import type { DescribedFile } from '../services/native'

// T031 (specs/007-video-editor-player) — the video editing area.
//
// Layout comes from MediaEditorShell, which the Imagem screen established and
// which knows nothing about jobs or processing (Princípio II: reuse it, do not
// grow a second one alongside).
//
// Handle registration happens in this view's addFile, not inside usePickFiles.
// tasks.md T019 records the reasoning: usePickFiles is shared with Áudio and the
// batch screens, and registering there would impose an API round trip on
// imports that need no handle. The addFile callback is the per-screen extension
// point, which is exactly what it is being used as here.

defineEmits<{ back: [] }>()

const { t } = useI18n()

interface EditorVideo {
  handle: MediaHandle
  /** Kept for the astros-media:// preview URL only. Never sent to the API —
      every call uses handle.handle_id (Princípio XIII). */
  sourcePath: string
}

const videos = ref<EditorVideo[]>([])
const activeId = ref<string | null>(null)
const importError = ref<string | null>(null)

const active = computed(
  () => videos.value.find((v) => v.handle.handle_id === activeId.value) ?? null
)

// Edits are keyed by handle, so switching videos cannot carry one file's
// settings onto another (FR-003).
const edits = useVideoEdits(activeId)

// Same conversions the player uses, for the trim readout in the panel.
const timeline = useVideoTimeline(computed(() => active.value?.handle ?? null))

const items = computed<EditorItem[]>(() =>
  videos.value.map((v) => ({
    id: v.handle.handle_id,
    fileName: v.handle.display_name,
    sourcePath: v.sourcePath,
    statusLabel: v.handle.frame_rate_is_variable
      ? t('videoEditor.player.frameUnavailable')
      : t('videoEditor.editor.ready'),
    kind: 'video' as const
  }))
)

async function addFile(file: DescribedFile): Promise<void> {
  try {
    const handle = await registerMediaHandle(file.path)
    videos.value.push({ handle, sourcePath: file.path })
    activeId.value ??= handle.handle_id
  } catch (error) {
    importError.value =
      error instanceof Error ? error.message : t('videoEditor.editor.importFailed')
  }
}

const { pickFiles, pickFolder, handleFilesDropped, uploading } = usePickFiles(
  addFile,
  importError,
  ['video']
)

// The panel emits; the view applies. Keeping the write here is what makes
// useVideoEdits the single owner of edit state.
function setAdjustment(key: keyof VideoAdjustments, value: number): void {
  if (activeId.value) edits.editsFor(activeId.value).adjustments[key] = value
}

function setEffect(key: keyof VideoEffects, value: number | boolean): void {
  if (!activeId.value) return
  const effects = edits.editsFor(activeId.value).effects
  // The key decides the type: a toggle takes the boolean, a strength the number.
  if (typeof value === 'boolean') (effects[key] as boolean) = value
  else (effects[key] as number) = value
}

function setTransform(patch: Partial<VideoTransform>): void {
  if (activeId.value) Object.assign(edits.editsFor(activeId.value).transform, patch)
}

function setTrim(trim: VideoTrim | null): void {
  if (activeId.value) edits.editsFor(activeId.value).trim = trim
}

function remove(id: string): void {
  videos.value = videos.value.filter((v) => v.handle.handle_id !== id)
  // Drop the edits with the video: keeping them would resurrect settings if the
  // same file were imported again, which is not what removing it means.
  edits.forget(id)
  if (activeId.value === id) activeId.value = videos.value[0]?.handle.handle_id ?? null
}
</script>

<template>
  <div class="flex h-full flex-col">
    <TopBar :title="t('videoEditor.editor.title')" @back="$emit('back')" />

    <p
      v-if="importError"
      class="flex items-center gap-2 px-4 py-2 text-(length:--fs-caption) text-state-danger"
    >
      <AlertCircle :size="14" />
      {{ importError }}
    </p>

    <!-- UploadZone's defaults are the Imagem screen's — "Arraste imagens aqui",
         PNG/JPG/WEBP. Left unset they render an image prompt inside a video
         editor, which is what a browser check caught. The prop is `loading`,
         not `uploading`. -->
    <UploadZone
      v-if="videos.length === 0"
      :loading="uploading"
      :error="importError"
      :title="t('videoEditor.editor.uploadTitle')"
      :subtitle="t('videoEditor.editor.uploadSubtitle')"
      :formats="['MP4', 'MOV', 'MKV', 'WEBM', 'AVI']"
      @pick-files="pickFiles"
      @pick-folder="pickFolder"
      @files-dropped="handleFilesDropped"
    />

    <MediaEditorShell
      v-else
      :items="items"
      :active-id="activeId"
      :add-label="t('videoEditor.editor.addMore')"
      @select="activeId = $event"
      @remove="remove"
      @add="pickFiles"
    >
      <template #preview>
        <VideoPlayer
          :handle="active?.handle ?? null"
          :source-path="active?.sourcePath ?? null"
          :adjustments="edits.current.value.adjustments"
        >
          <template #timeline-overlay>
            <VideoTrimHandles
              :trim="edits.current.value.trim"
              :duration="active?.handle.duration_seconds ?? 0"
              @update="setTrim"
            />
          </template>
        </VideoPlayer>
      </template>

      <template #panel>
        <!-- Transform, trim and export arrive with T047, T048 and T064. -->
        <VideoAdjustmentsPanel
          :adjustments="edits.current.value.adjustments"
          :effects="edits.current.value.effects"
          :shows-disclosure="edits.needsDisclosure.value"
          :disabled="!active"
          @reset="activeId && edits.reset(activeId)"
          @update-adjustment="setAdjustment"
          @update-effect="setEffect"
        />

        <VideoTransformPanel
          :transform="edits.current.value.transform"
          :trim="edits.current.value.trim"
          :source-width="active?.handle.width ?? null"
          :source-height="active?.handle.height ?? null"
          :format-time="timeline.formatTime"
          :disabled="!active"
          @update-transform="setTransform"
          @clear-trim="setTrim(null)"
        />
      </template>
    </MediaEditorShell>
  </div>
</template>
