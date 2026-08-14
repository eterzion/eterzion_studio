<script setup lang="ts">
import { Plus, X, Film, AudioLines, Image as ImageIcon } from '@lucide/vue'
import { api, hasNativeApi } from '../services/native'

// The editor layout the Imagem screen established — a large preview, a
// thumbnail strip of everything imported, and a settings panel on the right —
// extracted so Vídeo/Otimizar/Converter get the same shape without copying
// ImageEditorView's ~1800 lines (most of which is image-only: zoom/pan,
// before/after compare, denoise preview, export panel).
//
// Deliberately layout-only: it knows how to list/select/remove files and where
// to put a preview and a panel, and nothing about jobs, models or processing.
// Each screen keeps owning its own state and renders into the two slots.
export interface EditorItem {
  id: string
  fileName: string
  sourcePath: string
  /** Free-form, shown under the file name in the strip (e.g. 'Processando'). */
  statusLabel: string
  kind: 'image' | 'video' | 'audio'
}

defineProps<{
  items: EditorItem[]
  activeId: string | null
  /** Label for the trailing "add more" tile. */
  addLabel?: string
}>()

const emit = defineEmits<{
  select: [id: string]
  remove: [id: string]
  add: []
}>()

const KIND_ICON = { image: ImageIcon, video: Film, audio: AudioLines }
</script>

<template>
  <div class="editor-body">
    <div class="preview-area">
      <div class="preview-stage">
        <slot name="preview" />
      </div>

      <div class="thumb-strip">
        <!-- A wrapper div, not a <button>: the remove control is itself a
             button and nesting buttons is invalid HTML. -->
        <div
          v-for="item in items"
          :key="item.id"
          class="thumb-card"
          :class="{ active: item.id === activeId }"
        >
          <button class="thumb-select" type="button" @click="emit('select', item.id)">
            <img
              v-if="hasNativeApi && item.kind === 'image'"
              :src="api.toFileUrl(item.sourcePath)"
              alt=""
            />
            <video
              v-else-if="hasNativeApi && item.kind === 'video'"
              :src="api.toFileUrl(item.sourcePath)"
              muted
              preload="metadata"
            />
            <!-- Audio has nothing to show, and so does any file whose preview
                 can't load — fall back to the capability icon. -->
            <div v-else class="thumb-placeholder">
              <component :is="KIND_ICON[item.kind]" :size="20" />
            </div>
            <div class="thumb-meta">
              <span class="thumb-name">{{ item.fileName }}</span>
              <span class="thumb-status">{{ item.statusLabel }}</span>
            </div>
          </button>
          <button
            class="thumb-remove"
            type="button"
            :title="`Remover ${item.fileName}`"
            :aria-label="`Remover ${item.fileName}`"
            @click="emit('remove', item.id)"
          >
            <X :size="12" />
          </button>
        </div>

        <button class="thumb-add" type="button" @click="emit('add')">
          <Plus :size="16" />
          <span>{{ addLabel ?? 'Adicionar' }}</span>
        </button>
      </div>
    </div>

    <aside class="side-panel">
      <slot name="panel" />
    </aside>
  </div>
</template>

<style scoped>
.editor-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.preview-area {
  flex: 1;
  position: relative;
  display: flex;
  flex-direction: column;
  padding: var(--space-3);
  gap: var(--space-3);
  min-width: 0;
}

.preview-stage {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: var(--radius-md);
  background: var(--surface-1);
}

.thumb-strip {
  display: flex;
  gap: var(--space-2);
  overflow-x: auto;
  flex-shrink: 0;
}

.thumb-card {
  position: relative;
  width: 92px;
  flex-shrink: 0;
  border-radius: var(--radius-sm);
  overflow: hidden;
  border: 2px solid var(--surface-border);
  background: var(--surface-2);
}

.thumb-card.active {
  border-color: var(--color-primary);
}

/* Fills the card so the whole thumbnail stays one big click target for
   selecting; the remove control sits on top of it in the corner. */
.thumb-select {
  display: block;
  width: 100%;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
  text-align: left;
}

.thumb-select img,
.thumb-select video {
  width: 100%;
  height: 60px;
  object-fit: cover;
  display: block;
  background: var(--surface-3);
}

.thumb-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 60px;
  color: var(--text-tertiary);
  background: var(--surface-3);
}

.thumb-meta {
  padding: 4px 6px;
  display: flex;
  flex-direction: column;
}

.thumb-name {
  font-size: 10px;
  font-weight: var(--fw-medium);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thumb-status {
  font-size: 9px;
  color: var(--text-tertiary);
}

.thumb-remove {
  position: absolute;
  top: 3px;
  right: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  cursor: pointer;
  opacity: 0;
  transition:
    opacity var(--transition-fast),
    background var(--transition-fast);
}

/* Revealed on hover/focus so the strip stays clean, but never hidden from
   keyboard users (:focus-visible) or on touch, where hover never fires. */
.thumb-card:hover .thumb-remove,
.thumb-remove:focus-visible {
  opacity: 1;
}

@media (hover: none) {
  .thumb-remove {
    opacity: 1;
  }
}

.thumb-remove:hover {
  background: var(--color-danger);
}

.thumb-add {
  width: 92px;
  flex-shrink: 0;
  height: 88px;
  border: 1px dashed var(--surface-border);
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-size: 9px;
  cursor: pointer;
}

.thumb-add:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.side-panel {
  width: 320px;
  flex-shrink: 0;
  border-left: 1px solid var(--surface-border-soft);
  background: var(--surface-0);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  overflow-y: auto;
}

@media (max-width: 900px) {
  .editor-body {
    flex-direction: column;
  }

  .side-panel {
    width: auto;
    border-left: none;
    border-top: 1px solid var(--surface-border-soft);
  }
}
</style>
