<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import SettingSwitch from '../SettingSwitch.vue'
import SettingRow from '../SettingRow.vue'
import type { SizeTarget, SizeUnit } from '../../services/compression'

// specs/008-compression-centre — T041: "quero que caiba em 8 MB".
//
// **KB, MB e GB decimais** (1 MB = 1 000 000 bytes), como o sistema operacional
// e o site que impõe o limite contam. Usar potências de 1024 aqui faria "8 MB"
// significar uma coisa na tela e outra no lugar para onde o arquivo vai — e o
// upload seria recusado por 5%.
//
// A busca pelo alvo **não** dispara a cada dígito: digitar "80" passa por "8",
// e resolver o alvo em "8" custaria uma busca inteira por um número que a pessoa
// nem terminou de escrever. Confirmar é o gesto que dispara.

const props = defineProps<{ modelValue: SizeTarget | null; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [SizeTarget | null] }>()

const { t } = useI18n()

const UNITS: SizeUnit[] = ['KB', 'MB', 'GB']

const enabled = ref(props.modelValue !== null)
const value = ref(props.modelValue?.value ?? 8)
const unit = ref<SizeUnit>(props.modelValue?.unit ?? 'MB')

// Vindo de fora (um preset com alvo, por exemplo), os controles acompanham.
watch(
  () => props.modelValue,
  (novo) => {
    enabled.value = novo !== null
    if (novo) {
      value.value = novo.value
      unit.value = novo.unit
    }
  }
)

const valid = computed(() => Number.isFinite(value.value) && value.value > 0)

function commit(): void {
  if (!enabled.value) {
    emit('update:modelValue', null)
    return
  }
  if (!valid.value) return
  emit('update:modelValue', { value: value.value, unit: unit.value })
}

function toggle(ligado: boolean): void {
  enabled.value = ligado
  commit()
}
</script>

<template>
  <SettingRow :label="t('compression.target.label')" :divided="!enabled">
    <SettingSwitch :model-value="enabled" :disabled="disabled" @update:model-value="toggle" />
  </SettingRow>

  <SettingRow v-if="enabled" :label="t('compression.target.size')">
    <div class="target-input">
      <input
        v-model.number="value"
        type="number"
        min="0.1"
        step="0.1"
        class="target-value"
        :aria-label="t('compression.target.size')"
        :disabled="disabled"
        @change="commit"
        @keyup.enter="commit"
      />
      <select
        v-model="unit"
        class="target-unit"
        :aria-label="t('compression.target.unit')"
        :disabled="disabled"
        @change="commit"
      >
        <option v-for="u in UNITS" :key="u" :value="u">{{ u }}</option>
      </select>
    </div>
  </SettingRow>
  <p v-if="enabled" class="target-hint">{{ t('compression.target.hint') }}</p>
</template>

<style scoped>
.target-input {
  display: inline-flex;
  gap: var(--space-1);
}

.target-value,
.target-unit {
  padding: var(--space-1) var(--space-1-5);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text-primary);
  font-size: var(--fs-label);
}

.target-value {
  width: 72px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.target-value:focus-visible,
.target-unit:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}

.target-hint {
  margin: 0 0 var(--space-2);
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
}
</style>
