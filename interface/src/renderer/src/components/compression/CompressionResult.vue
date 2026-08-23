<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { FolderOpen, TrendingUp } from '@lucide/vue'
import AppButton from '../atoms/AppButton.vue'
import { formatBytesDecimal } from '../../utils/formatBytes'

// specs/008-compression-centre — T046: o que de fato saiu.
//
// **Estes números são medidos, nunca a estimativa repetida** (FR-022). Mostrar
// a previsão aqui seria a mentira mais fácil de cometer nesta tela: ela já está
// calculada, tem o formato certo, e ninguém perceberia — até o arquivo no disco
// não bater com o que a tela afirma.
//
// `grew` é campo vindo do backend e não conta local (FR-023). Uma redução
// negativa apresentada como economia é o tipo de defeito que passa por
// formatação: "-8%" alinhado onde sempre esteve o ganho é lido como ganho.

export interface CompressionResultData {
  outputPath: string
  originalBytes: number
  outputSizeBytes: number
  savingBytes: number
  reductionRatio: number | null
  grew: boolean
  elapsedSeconds: number
}

const props = defineProps<{ result: CompressionResultData }>()
const emit = defineEmits<{ reveal: [string] }>()

const { t, n } = useI18n()

const percent = computed(() => {
  const razao = props.result.reductionRatio
  return razao == null ? null : Math.abs(Math.round(razao * 100))
})
</script>

<template>
  <section class="result" :class="{ grew: result.grew }" :aria-label="t('compression.result.title')">
    <header class="result-header">
      <span class="result-title">{{ t('compression.result.title') }}</span>
      <span class="result-time">
        {{ t('compression.result.elapsed', { seconds: n(result.elapsedSeconds) }) }}
      </span>
    </header>

    <p class="result-sizes">
      <span>{{ formatBytesDecimal(result.originalBytes) }}</span>
      <span class="arrow">→</span>
      <span class="final">{{ formatBytesDecimal(result.outputSizeBytes) }}</span>
    </p>

    <p v-if="result.grew" class="result-grew">
      <TrendingUp :size="13" />
      <span>
        {{
          t('compression.result.grewBy', {
            size: formatBytesDecimal(Math.abs(result.savingBytes))
          })
        }}
      </span>
    </p>
    <p v-else-if="percent !== null" class="result-saving">
      {{
        t('compression.result.saved', {
          size: formatBytesDecimal(result.savingBytes),
          percent: n(percent)
        })
      }}
    </p>

    <AppButton variant="secondary" size="sm" @click="emit('reveal', result.outputPath)">
      <FolderOpen :size="14" />
      {{ t('compression.result.reveal') }}
    </AppButton>
  </section>
</template>

<style scoped>
.result {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1-5);
  padding: var(--space-2);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-md);
  background: var(--color-primary-soft);
}

.result.grew {
  border-color: var(--color-warning);
  background: transparent;
}

.result-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
  width: 100%;
}

.result-title {
  font-size: var(--fs-label);
  font-weight: var(--fw-medium);
  color: var(--text-primary);
}

.result-time {
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.result-sizes {
  display: flex;
  align-items: baseline;
  gap: var(--space-1);
  margin: 0;
  font-size: var(--fs-body-sm);
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.arrow {
  color: var(--text-tertiary);
}

.final {
  color: var(--text-primary);
  font-weight: var(--fw-semibold);
}

.result-saving {
  margin: 0;
  font-size: var(--fs-label-sm);
  color: var(--color-primary);
}

.result-grew {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 0;
  font-size: var(--fs-label-sm);
  color: var(--color-warning);
}
</style>
