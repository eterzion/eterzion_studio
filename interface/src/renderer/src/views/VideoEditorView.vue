<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { AlertCircle } from '@lucide/vue'
import TopBar from '../components/TopBar.vue'
import UploadZone from '../components/UploadZone.vue'
import MediaEditorShell, { type EditorItem } from '../components/MediaEditorShell.vue'
import VideoPlayer from '../components/video/VideoPlayer.vue'
import { usePickFiles } from '../composables/usePickFiles'
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

function remove(id: string): void {
  videos.value = videos.value.filter((v) => v.handle.handle_id !== id)
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
        <VideoPlayer :handle="active?.handle ?? null" :source-path="active?.sourcePath ?? null" />
      </template>

      <template #panel>
        <!-- Adjustments, effects, transform, trim and audio arrive in US2 and
             US3 (T046-T048, T064). US1 is the player alone, and stops here on
             purpose: it is independently testable and independently useful. -->
        <p class="p-4 text-(length:--fs-caption) text-text-tertiary">
          {{ t('videoEditor.editor.panelPending') }}
        </p>
      </template>
    </MediaEditorShell>
  </div>
</template>
