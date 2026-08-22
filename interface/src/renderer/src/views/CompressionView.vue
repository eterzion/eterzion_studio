<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  COMPRESSION_MEDIA_KINDS,
  DEFAULT_COMPRESSION_MODE,
  DEFAULT_MEDIA_KIND,
  type CompressionMode,
  type MediaKind
} from '../constants/compression'

// specs/008-compression-centre — Fase 1, T026 (casca).
//
// A tela existe, é laranja e navega entre os quatro tipos de mídia. Ainda não
// comprime nada: a Fase 2 traz capacidades, estimativa, presets e importação, e
// a Fase 3 entrega Imagem ponta a ponta.
//
// O que já está certo aqui e não deve regredir: o modo padrão é Básico
// (FR-038), e isso é constitucional — a condição 2 da exceção do Princípio V
// exige que quem nunca abrir o Avançado jamais encontre um nome de codec.

defineEmits<{ back: [] }>()

const { t } = useI18n()

const mediaKind = ref<MediaKind>(DEFAULT_MEDIA_KIND)
const mode = ref<CompressionMode>(DEFAULT_COMPRESSION_MODE)
</script>

<template>
  <div class="compression-view" data-module="compression">
    <header class="compression-header">
      <h1>{{ t('compression.title') }}</h1>
      <p>{{ t('compression.subtitle') }}</p>
    </header>

    <nav class="media-tabs" :aria-label="t('compression.title')">
      <button
        v-for="entry in COMPRESSION_MEDIA_KINDS"
        :key="entry.value"
        type="button"
        class="media-tab"
        :class="{ active: mediaKind === entry.value }"
        :aria-current="mediaKind === entry.value ? 'page' : undefined"
        @click="mediaKind = entry.value"
      >
        {{ t(entry.labelKey) }}
      </button>
    </nav>

    <p class="placeholder">{{ t('compression.comingSoon', { media: t(`compression.media.${mediaKind}`) }) }}</p>
    <p class="placeholder-mode">{{ t(`compression.mode.${mode}`) }}</p>
  </div>
</template>

<style scoped>
.compression-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-4);
  height: 100vh;
  overflow-y: auto;
  background: var(--surface-0);
}

.compression-header h1 {
  font-size: var(--fs-h3);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  margin: 0;
}

.compression-header p {
  margin: var(--space-1) 0 0;
  font-size: var(--fs-body-sm);
  color: var(--text-secondary);
}

.media-tabs {
  display: flex;
  gap: var(--space-1);
  padding: var(--space-1);
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-md);
  align-self: flex-start;
}

.media-tab {
  padding: var(--space-2) var(--space-3);
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--fs-label);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.media-tab:hover {
  background: var(--surface-3);
  color: var(--text-primary);
}

.media-tab.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.media-tab:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.placeholder,
.placeholder-mode {
  margin: 0;
  font-size: var(--fs-body-sm);
  color: var(--text-tertiary);
}
</style>
