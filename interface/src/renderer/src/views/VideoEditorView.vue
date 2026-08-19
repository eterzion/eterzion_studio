<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { AlertCircle, AlertTriangle, Download, Play, Upload } from '@lucide/vue'
import TopBar from '../components/TopBar.vue'
import UploadZone from '../components/UploadZone.vue'
import MediaEditorShell, { type EditorItem } from '../components/MediaEditorShell.vue'
import AppButton from '../components/atoms/AppButton.vue'
import VideoPlayer from '../components/video/VideoPlayer.vue'
import VideoEnhancePanel, { type EnhanceSettings } from '../components/video/VideoEnhancePanel.vue'
import VideoAdjustmentsPanel from '../components/video/VideoAdjustmentsPanel.vue'
import VideoTransformPanel from '../components/video/VideoTransformPanel.vue'
import VideoTrimHandles from '../components/video/VideoTrimHandles.vue'
import VideoExportPanel from '../components/video/VideoExportPanel.vue'
import { usePickFiles } from '../composables/usePickFiles'
import {
  useVideoEdits,
  type VideoAdjustments,
  type VideoEffects,
  type VideoTransform,
  type VideoTrim
} from '../composables/useVideoEdits'
import { useVideoTimeline } from '../composables/useVideoTimeline'
import { useVideoProcessing, type VideoRequest } from '../composables/useVideoProcessing'
import { registerMediaHandle, type MediaHandle, type VideoContainer } from '../services/api'
import { api, hasNativeApi, type DescribedFile } from '../services/native'

// The one Vídeo screen (specs/007-video-editor-player, FR-032 as amended).
//
// Replaces both the editor and the separate upscale screen. The two used to
// coexist as modes, which was my reading of an ambiguous requirement; the
// product decision is one screen, so VideoView.vue is retired rather than left
// beside this as a second way to do the same thing (Princípio X: dead code is
// deleted, not archived).
//
// Everything the old screen could do still happens here: content type, scale,
// profile, device, batch processing, and — the one that matters most — the
// secondary-elements confirmation, which warns before enhance silently drops
// extra audio tracks, subtitles or chapters.

defineEmits<{ back: [] }>()

const { t } = useI18n()

interface EditorVideo {
  handle: MediaHandle
  /** For the astros-media:// preview URL and the enhance route, which predates
      handles. Never sent to the edit routes — those take handle_id only
      (Princípio XIII). */
  sourcePath: string
}

const videos = ref<EditorVideo[]>([])
const activeId = ref<string | null>(null)
const importError = ref<string | null>(null)
const exportDirectory = ref<string | null>(null)
const container = ref<VideoContainer>('mp4')

const active = computed(
  () => videos.value.find((v) => v.handle.handle_id === activeId.value) ?? null
)

const edits = useVideoEdits(activeId)
const timeline = useVideoTimeline(computed(() => active.value?.handle ?? null))
const processing = useVideoProcessing()

// Enhance settings are per video for the same reason edits are: a batch of
// clips rarely wants one scale for all of them, and carrying one video's choice
// onto another silently is the bug nobody notices until the output is wrong.
const enhanceByHandle = reactive(new Map<string, EnhanceSettings>())

function enhanceFor(handleId: string): EnhanceSettings {
  let settings = enhanceByHandle.get(handleId)
  if (!settings) {
    settings = {
      scale: 'none',
      customWidth: null,
      customHeight: null,
      contentType: 'real_video',
      profile: 'balanced',
      device: 'auto'
    }
    enhanceByHandle.set(handleId, settings)
  }
  return settings
}

const activeEnhance = computed(() =>
  activeId.value ? enhanceFor(activeId.value) : enhanceFor('__none__')
)

const items = computed<EditorItem[]>(() =>
  videos.value.map((v) => ({
    id: v.handle.handle_id,
    fileName: v.handle.display_name,
    sourcePath: v.sourcePath,
    statusLabel: t(`videoEditor.status.${processing.stateFor(v.handle.handle_id).status}`),
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

// The panels emit; the view applies. Keeping the writes here is what makes
// useVideoEdits the single owner of edit state.
function setAdjustment(key: keyof VideoAdjustments, value: number): void {
  if (activeId.value) edits.editsFor(activeId.value).adjustments[key] = value
}

function setEffect(key: keyof VideoEffects, value: number | boolean): void {
  if (!activeId.value) return
  const effects = edits.editsFor(activeId.value).effects
  if (typeof value === 'boolean') (effects[key] as boolean) = value
  else (effects[key] as number) = value
}

function setTransform(patch: Partial<VideoTransform>): void {
  if (activeId.value) Object.assign(edits.editsFor(activeId.value).transform, patch)
}

function setTrim(trim: VideoTrim | null): void {
  if (activeId.value) edits.editsFor(activeId.value).trim = trim
}

function setEnhance(patch: Partial<EnhanceSettings>): void {
  if (activeId.value) Object.assign(enhanceFor(activeId.value), patch)
}

async function pickDirectory(): Promise<void> {
  if (!hasNativeApi) return
  exportDirectory.value = await api.selectOutputFolder(exportDirectory.value ?? undefined)
}

function requestFor(video: EditorVideo): VideoRequest {
  return {
    handleId: video.handle.handle_id,
    displayName: video.handle.display_name,
    sourcePath: video.sourcePath,
    edits: JSON.parse(JSON.stringify(edits.editsFor(video.handle.handle_id))),
    enhance: { ...enhanceFor(video.handle.handle_id) },
    container: container.value,
    directory: exportDirectory.value
  }
}

function runActive(choice: { container: VideoContainer }): void {
  if (!active.value) return
  container.value = choice.container
  processing.start(requestFor(active.value))
}

/** Batch, kept from the old screen: every video that is not already running. */
function runAll(): void {
  for (const video of videos.value) {
    if (!processing.isBusy(video.handle.handle_id)) processing.start(requestFor(video))
  }
}

const pendingCount = computed(
  () => videos.value.filter((v) => !processing.isBusy(v.handle.handle_id)).length
)

const activeState = computed(() => (activeId.value ? processing.stateFor(activeId.value) : null))

// FR-081 to FR-086. The list is what enhance would drop; the person decides
// before anything is processed.
// `losses` is the backend's own list of what would be dropped — the same
// strings VideoView mapped through LOSS_LABELS. Reading it rather than
// re-deriving from the stream counts means the warning cannot disagree with
// what the backend actually decided.
const losses = computed(() => activeState.value?.secondaryElements?.losses ?? [])

/** Reveals a finished result in the file manager — the capability the old
 *  screen's "Exportar tudo" actually provided. It never re-exported anything;
 *  it opened the folder, which is what someone wants after a batch finishes. */
function revealFirstResult(): void {
  if (!hasNativeApi) return
  const done = videos.value
    .map((v) => processing.stateFor(v.handle.handle_id))
    .find((state) => state.status === 'done' && state.outputPath)
  if (done?.outputPath) api.showItemInFolder(done.outputPath)
}

const doneCount = computed(
  () => videos.value.filter((v) => processing.stateFor(v.handle.handle_id).status === 'done').length
)

function remove(id: string): void {
  videos.value = videos.value.filter((v) => v.handle.handle_id !== id)
  edits.forget(id)
  enhanceByHandle.delete(id)
  if (activeId.value === id) activeId.value = videos.value[0]?.handle.handle_id ?? null
}
</script>

<template>
  <!-- data-module drives the module accent (theme.css: --accent-video, the
       purple the sidebar's Vídeo entry uses). Imagem and Áudio carry the same
       attribute; this screen lost it when it was rewritten, which is why it was
       rendering in the neutral accent. -->
  <div class="video-view" data-module="video">
    <!-- Title and actions follow Imagem and Áudio: the active file's name rather
         than a fixed screen title, and Importar / Processar todos / Exportar
         tudo in that order. Someone moving between the three screens should not
         have to relearn where anything is. -->
    <TopBar
      :title="active?.handle.display_name ?? t('actions.noVideoSelected')"
      show-back
      @back="$emit('back')"
    >
      <template #actions>
        <AppButton variant="outline" @click="pickFiles">
          <template #icon><Upload :size="15" /></template>
          {{ t('actions.import') }}
        </AppButton>
        <AppButton variant="outline" :disabled="!pendingCount" @click="runAll">
          <template #icon><Play :size="15" /></template>
          {{ t('actions.processAll') }}
        </AppButton>
        <AppButton variant="outline" :disabled="!doneCount" @click="revealFirstResult">
          <template #icon><Download :size="15" /></template>
          {{ t('actions.exportAll') }}
        </AppButton>
      </template>
    </TopBar>

    <div class="video-content">
      <!-- Only while the list has videos: with an empty list the UploadZone
           below already surfaces the same message in its own error state. Same
           treatment as Imagem and Áudio. -->
      <p v-if="importError && videos.length" class="banner-error">
        <AlertCircle :size="14" /> {{ importError }}
      </p>

      <UploadZone
        v-if="videos.length === 0"
        class="upload-fill"
        :loading="uploading"
        :error="importError"
        :title="t('upload.videoTitle')"
        :formats="['MP4', 'MOV', 'MKV', 'WEBM', 'AVI']"
        @pick-files="pickFiles"
        @pick-folder="pickFolder"
        @files-dropped="handleFilesDropped"
      />

      <MediaEditorShell
        v-else
        class="editor-shell"
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
          <!-- FR-081 to FR-086: what enhance would silently drop, shown BEFORE
             anything is processed. Carried over from the old screen — losing it
             in the unification would mean deleting people's subtitles without
             telling them. -->
          <div
            v-if="losses.length"
            class="flex flex-col gap-2 rounded border border-state-danger bg-state-danger-soft px-3 py-2"
          >
            <p class="flex items-start gap-2 text-(length:--fs-caption) text-state-danger">
              <AlertTriangle :size="14" class="mt-0.5 shrink-0" />
              {{ t('videoEditor.secondary.warning') }}
            </p>
            <ul class="ml-6 list-disc text-(length:--fs-caption) text-text-secondary">
              <li v-for="loss in losses" :key="loss">
                {{ t(`videoEditor.secondary.${loss}`, loss) }}
              </li>
            </ul>
            <AppButton
              variant="danger"
              size="sm"
              class="self-start"
              @click="activeId && processing.confirm(activeId)"
            >
              {{ t('videoEditor.secondary.proceed') }}
            </AppButton>
          </div>

          <VideoEnhancePanel
            :settings="activeEnhance"
            :source-width="active?.handle.width ?? null"
            :source-height="active?.handle.height ?? null"
            :disabled="!active || processing.isBusy(activeId ?? '')"
            @update="setEnhance"
          />

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

          <VideoExportPanel
            :state="activeState"
            :directory="exportDirectory"
            :disabled="!active"
            @export="runActive"
            @cancel="activeId && processing.cancel(activeId)"
            @pick-directory="pickDirectory"
          />
        </template>
      </MediaEditorShell>
    </div>
  </div>
</template>

<style scoped>
/* Mirrors AudioView/ImageEditorView so the three media screens share one
   shape — height, padding, and an empty state that fills the area instead of
   sitting as a strip at the top. */
.video-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  flex: 1;
  min-width: 0;
}
.video-content {
  flex: 1;
  min-height: 0;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* The editor lays out its own preview/strip/panel — no outer padding fighting
   it once files are loaded. */
.video-content:has(.editor-shell) {
  padding: 0;
}

.upload-fill {
  flex: 1;
  min-height: 0;
}
.editor-shell {
  flex: 1;
  min-height: 0;
}
.banner-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-danger);
  font-size: var(--fs-body-sm);
}
</style>
