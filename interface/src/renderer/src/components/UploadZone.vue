<script setup lang="ts">
import { ref } from 'vue'
import { UploadCloud, FolderOpen, FolderUp, FileWarning } from '@lucide/vue'
import AppButton from './atoms/AppButton.vue'
import AppSpinner from './atoms/AppSpinner.vue'
import AppBadge from './atoms/AppBadge.vue'

// Copy/format chips are props (not hardcoded) so screens that accept more than
// images — Otimizar, which takes image/video/audio alike — can reuse this exact
// drop zone instead of falling back to a plain button-only empty state. The
// defaults are the original image-only wording, so ImageEditorView needs no
// changes.
withDefaults(
  defineProps<{
    error?: string | null
    loading?: boolean
    title?: string
    subtitle?: string
    formats?: string[]
  }>(),
  {
    loading: false,
    title: 'Arraste imagens aqui',
    subtitle: 'ou use os botões abaixo — imagens são identificadas automaticamente',
    formats: () => ['PNG', 'JPG', 'WEBP', 'BMP', 'TIFF']
  }
)

const emit = defineEmits<{
  filesDropped: [files: File[]]
  pickFiles: []
  pickFolder: []
}>()

const dragOver = ref(false)
let dragDepth = 0

// dragenter/dragleave fire for every descendant element too, so a plain boolean
// flickers as the pointer crosses child elements — a depth counter fixes that.
function onDragEnter(): void {
  dragDepth++
  dragOver.value = true
}
function onDragLeave(): void {
  dragDepth = Math.max(0, dragDepth - 1)
  if (dragDepth === 0) dragOver.value = false
}
function onDrop(e: DragEvent): void {
  dragDepth = 0
  dragOver.value = false
  if (e.dataTransfer?.files?.length) emit('filesDropped', Array.from(e.dataTransfer.files))
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    emit('pickFiles')
  }
}
</script>

<template>
  <div
    class="upload-zone"
    :class="{ 'drag-over': dragOver, 'has-error': !!error, loading }"
    role="button"
    tabindex="0"
    aria-label="Arraste arquivos aqui ou pressione Enter para selecionar"
    @dragenter.prevent="onDragEnter"
    @dragover.prevent
    @dragleave.prevent="onDragLeave"
    @drop.prevent="onDrop"
    @click="!loading && emit('pickFiles')"
    @keydown="onKeydown"
  >
    <div class="drop-ring" aria-hidden="true" />

    <template v-if="loading">
      <AppSpinner :size="26" class="icon-circle-spin" />
      <h3 class="upload-title">Importando arquivos…</h3>
    </template>
    <template v-else-if="error">
      <div class="icon-circle icon-error"><FileWarning :size="26" /></div>
      <h3 class="upload-title">Não foi possível importar os arquivos</h3>
      <p class="upload-subtitle">{{ error }}</p>
      <AppButton variant="primary" size="lg" @click.stop="emit('pickFiles')">
        Tentar novamente
      </AppButton>
    </template>
    <template v-else>
      <div class="icon-circle" :class="{ active: dragOver }"><UploadCloud :size="26" /></div>
      <h3 class="upload-title">
        {{ dragOver ? 'Solte para importar' : title }}
      </h3>
      <p class="upload-subtitle">{{ subtitle }}</p>

      <div class="upload-actions">
        <AppButton variant="primary" size="lg" @click.stop="emit('pickFiles')">
          <template #icon><FolderOpen :size="16" /></template>
          Selecionar arquivos
        </AppButton>
        <AppButton variant="secondary" size="lg" @click.stop="emit('pickFolder')">
          <template #icon><FolderUp :size="16" /></template>
          Selecionar pasta
        </AppButton>
      </div>

      <div class="upload-meta">
        <div class="format-chips">
          <AppBadge v-for="fmt in formats" :key="fmt" tone="neutral">{{ fmt }}</AppBadge>
        </div>
        <span class="upload-limit">até 500 MB por arquivo</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.upload-zone {
  position: relative;
  border: 1.5px dashed var(--surface-border);
  border-radius: var(--radius-lg);
  background: var(--surface-1);
  padding: var(--space-5) var(--space-4);
  display: flex;
  flex-direction: column;
  align-items: center;
  /* Keeps the contents centered when a screen stretches this zone to fill its
     whole area (Imagem/Otimizar); a no-op when the height is content-sized. */
  justify-content: center;
  text-align: center;
  gap: var(--space-2);
  cursor: pointer;
  overflow: hidden;
  transition:
    border-color var(--transition-fast),
    background var(--transition-fast),
    box-shadow var(--transition-fast);
}

.upload-zone:hover:not(.loading) {
  border-color: var(--text-tertiary);
  background: var(--surface-2);
}

.upload-zone:focus-visible {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-soft);
}

.upload-zone.drag-over {
  border-color: var(--color-primary);
  border-style: solid;
  background: var(--color-primary-soft);
}

.upload-zone.has-error {
  border-color: var(--color-danger);
  background: var(--color-danger-soft);
}

.upload-zone.loading {
  cursor: progress;
}

.drop-ring {
  position: absolute;
  inset: 8px;
  border-radius: calc(var(--radius-lg) - 4px);
  border: 2px solid var(--color-primary);
  opacity: 0;
  pointer-events: none;
  transition: opacity var(--transition-fast);
}

.drag-over .drop-ring {
  opacity: 1;
  animation: drop-ring-pulse 1.1s ease-in-out infinite;
}

@keyframes drop-ring-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 0.9;
  }
  50% {
    transform: scale(1.015);
    opacity: 0.4;
  }
}

.icon-circle {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  margin-bottom: var(--space-1);
  transition: transform var(--transition-fast);
}

.icon-circle.active {
  transform: scale(1.1);
}

.icon-circle.icon-error {
  color: var(--color-danger);
  background: var(--color-danger-soft);
}

.icon-circle-spin {
  color: var(--color-primary);
  margin-bottom: var(--space-1);
}

.upload-title {
  font-size: 17px;
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.upload-subtitle {
  font-size: var(--fs-label);
  color: var(--text-secondary);
  max-width: 420px;
}

.upload-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.upload-meta {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1-5);
  margin-top: var(--space-2);
}

.format-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-1-5);
  max-width: 480px;
}

.upload-limit {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
}
</style>
