<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { CompressionSettings } from '../../services/compression'
import type { CompressionMode, MediaKind } from '../../constants/compression'

// specs/008-compression-centre — T043: o resumo do que vai acontecer.
//
// Existe porque as configurações moram em painéis que se abrem e fecham, e no
// momento de apertar "Comprimir" metade delas está fora de vista. Um resumo é o
// que permite conferir sem reabrir três painéis.
//
// **Só mostra o que foi escolhido.** Listar todo campo com o seu padrão
// encheria o resumo de linhas que a pessoa não decidiu, e a que ela decidiu se
// perderia no meio. Um campo em `auto`/`original` não aparece — não porque seja
// menos importante, mas porque "automático" é a ausência de escolha, e a
// ausência não precisa ser conferida.

const props = defineProps<{
  settings: CompressionSettings
  mediaKind: MediaKind
  mode: CompressionMode
}>()

const { t } = useI18n()

const SENTINELS = new Set(['auto', 'original', 'keep', '', null, undefined])

/** Campos cujo valor é um rótulo traduzível, e não um número cru. */
const TRANSLATED = new Set(['metadata_policy', 'rate_mode', 'bitrate_mode'])

const rows = computed(() =>
  Object.entries(props.settings)
    .filter(([, valor]) => !SENTINELS.has(valor as string) && valor !== false)
    .map(([campo, valor]) => ({
      campo,
      label: t(`compression.summary.field.${campo}`),
      valor: format(campo, valor)
    }))
)

function format(campo: string, valor: unknown): string {
  if (typeof valor === 'boolean') return t('compression.summary.on')
  if (TRANSLATED.has(campo)) return t(`compression.image.metadata.${String(valor)}`)
  if (campo === 'output_format' || campo === 'container') return String(valor).toUpperCase()
  return String(valor)
}
</script>

<template>
  <section class="summary" :aria-label="t('compression.summary.title')">
    <header class="summary-header">
      <span class="summary-title">{{ t('compression.summary.title') }}</span>
      <span class="summary-mode">{{ t(`compression.mode.${mode}`) }}</span>
    </header>

    <dl v-if="rows.length" class="summary-rows">
      <div v-for="row in rows" :key="row.campo" class="summary-row">
        <dt>{{ row.label }}</dt>
        <dd>{{ row.valor }}</dd>
      </div>
    </dl>

    <!-- Nenhuma escolha feita é um estado legítimo, e dizê-lo é mais honesto que
         uma lista vazia que parece um erro de carregamento. -->
    <p v-else class="summary-empty">{{ t('compression.summary.defaults') }}</p>
  </section>
</template>

<style scoped>
.summary {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-md);
}

.summary-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
}

.summary-title {
  font-size: var(--fs-label);
  color: var(--text-primary);
  font-weight: var(--fw-medium);
}

.summary-mode {
  font-size: var(--fs-label-sm);
  color: var(--color-primary);
}

.summary-rows {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin: 0;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  gap: var(--space-2);
  font-size: var(--fs-label-sm);
}

.summary-row dt {
  color: var(--text-tertiary);
}

.summary-row dd {
  margin: 0;
  color: var(--text-secondary);
  text-align: right;
}

.summary-empty {
  margin: 0;
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}
</style>
