<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ExternalLink, FileCheck, FolderOpen } from '@lucide/vue'
import AppButton from './atoms/AppButton.vue'
import { api, hasNativeApi } from '../services/native'

// Onde o resultado foi gravado, igual em Imagem, Video e Audio. Antes a Imagem
// mostrava o caminho inteiro numa linha corrida ("Saved to: C:\Users\...")
// quebrando no meio de palavras, o Video so' dizia "Arquivo exportado." e o
// Audio so' tinha "Abrir pasta". O nome do arquivo e' o que a pessoa procura;
// a pasta vem embaixo, menor, com o caminho completo no title.

const props = defineProps<{ path: string }>()

const { t } = useI18n()

const partes = computed(() => {
  const corte = Math.max(props.path.lastIndexOf('/'), props.path.lastIndexOf('\\'))
  return { nome: props.path.slice(corte + 1), pasta: corte > 0 ? props.path.slice(0, corte) : '' }
})
</script>

<template>
  <section class="saved-card" :title="path">
    <div class="saved-head">
      <div class="saved-icon icon-chip"><FileCheck :size="16" /></div>
      <div class="saved-heading">
        <span class="saved-title">{{ t('savedResult.title') }}</span>
        <span class="saved-name">{{ partes.nome }}</span>
        <span v-if="partes.pasta" class="saved-folder">{{ partes.pasta }}</span>
      </div>
    </div>
    <div v-if="hasNativeApi" class="saved-actions">
      <AppButton variant="outline" size="sm" @click="api.openPath(path)">
        <template #icon><ExternalLink :size="14" /></template>
        {{ t('savedResult.open') }}
      </AppButton>
      <AppButton variant="outline" size="sm" @click="api.showItemInFolder(path)">
        <template #icon><FolderOpen :size="14" /></template>
        {{ t('savedResult.showInFolder') }}
      </AppButton>
    </div>
  </section>
</template>

<style scoped>
/* A mesma caixa do CollapsiblePanel, para ficar na mesma coluna sem destoar. */
.saved-card {
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  flex-shrink: 0;
}

.saved-head {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  min-width: 0;
}

.saved-icon {
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  flex-shrink: 0;
}

.saved-heading {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.saved-title {
  font-size: var(--fs-section-title);
  font-weight: var(--fw-semibold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.saved-name {
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

/* Uma linha, cortada no fim: a pasta e' contexto, nao o que se le primeiro. */
.saved-folder {
  font-size: 11px;
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.saved-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.saved-actions > :deep(button) {
  flex: 1;
}
</style>
