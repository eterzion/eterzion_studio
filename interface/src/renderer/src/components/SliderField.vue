<script setup lang="ts">
import RangeSlider from './RangeSlider.vue'

// O campo de intensidade como o editor de imagem o desenha: rótulo à esquerda,
// valor à direita, controle abaixo, explicação embaixo. Extraído para cá porque
// a tela de vídeo passou a precisar do mesmo, e a segunda cópia de um padrão é
// onde ele começa a divergir.
//
// O valor ao lado do rótulo não é enfeite: sem ele, um controle contínuo só
// pode ser descrito por aproximação — "mais ou menos no meio" — e a pessoa não
// consegue repetir num outro arquivo o que acabou de escolher.

withDefaults(
  defineProps<{
    label: string
    modelValue: number
    min?: number
    max?: number
    step?: number
    defaultValue?: number
    /** Quantas casas mostrar. Brilho anda de 0,01 e precisa de duas; a
     *  intensidade de um efeito anda de 1 e não precisa de nenhuma. */
    decimals?: number
    /** Sufixo da unidade, quando ela existe — graus no matiz. */
    unit?: string
    hint?: string
    ariaLabel?: string
    disabled?: boolean
  }>(),
  { decimals: 0, min: 0, max: 100, step: 1 }
)

defineEmits<{ 'update:modelValue': [value: number] }>()
</script>

<template>
  <div class="slider-field" :class="{ disabled }">
    <div class="slider-head">
      <span class="field-label">{{ label }}</span>
      <span class="slider-value">{{ modelValue.toFixed(decimals) }}{{ unit ?? '' }}</span>
    </div>
    <RangeSlider
      :model-value="modelValue"
      :min="min"
      :max="max"
      :step="step"
      :default-value="defaultValue"
      :aria-label="ariaLabel ?? label"
      :disabled="disabled"
      @update:model-value="$emit('update:modelValue', $event)"
    />
    <p v-if="hint" class="field-hint">{{ hint }}</p>
  </div>
</template>

<style scoped>
.slider-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
  padding: var(--space-1-5) 0 var(--space-3);
}

.slider-field.disabled {
  opacity: 0.55;
}

.slider-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.field-label {
  font-size: var(--fs-label);
  font-weight: var(--fw-medium);
  color: var(--text-primary);
}

.slider-value {
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.field-hint {
  /* Colado no controle que explica: com o respiro do painel, ficava equidistante
     dos dois e não pertencia a nenhum. */
  margin-top: calc(var(--space-1) * -1);
  font-size: 11px;
  line-height: 1.35;
  color: var(--text-tertiary);
}
</style>
