<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Info } from '@lucide/vue'
import AppSpinner from '../atoms/AppSpinner.vue'
import { formatBytesDecimal } from '../../utils/formatBytes'
import type { CompressionEstimate } from '../../services/compression'

// specs/008-compression-centre — T042: quanto vai pesar, e o quanto disso é chute.
//
// FR-019 exige que o número seja **declarado como estimativa**. A razão é
// concreta: um número que aparece do lado do arquivo, com duas casas e alinhado
// à direita, é lido como medição. Quando o resultado sai 15% maior, a pessoa não
// conclui "a estimativa errou" — conclui que o produto mentiu.
//
// Por isso três coisas aparecem sempre juntas: o número, a confiança, e as
// premissas. `assumptions` existe para a interface poder ser honesta sobre o que
// a estimativa não sabe; escondê-las devolveria o palpite com cara de medição.

const props = defineProps<{
  estimate: CompressionEstimate | null
  loading?: boolean
  /** Chave de razão, nunca frase. */
  error?: string | null
}>()

const { t, n } = useI18n()

const reduction = computed(() => {
  const razao = props.estimate?.reduction_ratio
  return razao == null ? null : Math.round(razao * 100)
})

/** O caso que não pode ser apresentado como economia: comprimir cresceu.
 *  Uma redução negativa formatada como "−12%" seria lida como ganho. */
const grew = computed(() => (props.estimate ? props.estimate.estimated_saving_bytes < 0 : false))
</script>

<template>
  <section class="estimate" :aria-label="t('compression.estimate.title')">
    <div v-if="loading" class="estimate-loading">
      <AppSpinner :size="14" />
      <span>{{ t('compression.estimate.loading') }}</span>
    </div>

    <p v-else-if="error" class="estimate-error">
      {{ t(`compression.refusal.${error}`) }}
    </p>

    <template v-else-if="estimate">
      <header class="estimate-header">
        <span class="estimate-label">{{ t('compression.estimate.title') }}</span>
        <span class="estimate-confidence">
          {{ t(`compression.estimate.confidence.${estimate.confidence}`) }}
        </span>
      </header>

      <div class="estimate-numbers">
        <div class="number">
          <span class="number-label">{{ t('compression.estimate.original') }}</span>
          <span class="number-value">{{ formatBytesDecimal(estimate.original_bytes) }}</span>
        </div>
        <div class="number">
          <span class="number-label">{{ t('compression.estimate.estimated') }}</span>
          <span class="number-value strong">
            {{
              estimate.estimated_bytes == null
                ? t('compression.estimate.unknown')
                : formatBytesDecimal(estimate.estimated_bytes)
            }}
          </span>
        </div>
        <div v-if="reduction !== null" class="number">
          <span class="number-label">
            {{ grew ? t('compression.estimate.growth') : t('compression.estimate.saving') }}
          </span>
          <span class="number-value" :class="{ warn: grew }">
            {{ n(Math.abs(reduction)) }}%
          </span>
        </div>
      </div>

      <p v-if="estimate.feasibility === 'below_floor'" class="estimate-warning">
        {{ t('compression.estimate.belowFloor') }}
      </p>
      <p v-else-if="grew" class="estimate-warning">
        {{ t('compression.estimate.wouldGrow') }}
      </p>

      <p class="estimate-disclaimer">
        <Info :size="12" />
        <span>{{ t('compression.estimate.disclaimer') }}</span>
      </p>

      <ul v-if="estimate.assumptions.length" class="estimate-assumptions">
        <li v-for="premissa in estimate.assumptions" :key="premissa">
          {{ t(`compression.estimate.assumption.${premissa}`) }}
        </li>
      </ul>
    </template>

    <p v-else class="estimate-empty">{{ t('compression.estimate.empty') }}</p>
  </section>
</template>

<style scoped>
.estimate {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
  padding: var(--space-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-md);
  background: var(--surface-2);
}

.estimate-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
}

.estimate-label {
  font-size: var(--fs-label);
  color: var(--text-primary);
  font-weight: var(--fw-medium);
}

.estimate-confidence {
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}

.estimate-numbers {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.number {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.number-label {
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}

.number-value {
  font-size: var(--fs-body-sm);
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.number-value.strong {
  color: var(--color-primary);
  font-weight: var(--fw-semibold);
}

.number-value.warn {
  color: var(--color-warning);
}

.estimate-warning {
  margin: 0;
  font-size: var(--fs-label-sm);
  color: var(--color-warning);
}

.estimate-disclaimer {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  margin: 0;
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}

.estimate-assumptions {
  margin: 0;
  padding-left: var(--space-3);
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}

.estimate-loading {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}

.estimate-error {
  margin: 0;
  font-size: var(--fs-label-sm);
  color: var(--color-warning);
}

.estimate-empty {
  margin: 0;
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}
</style>
