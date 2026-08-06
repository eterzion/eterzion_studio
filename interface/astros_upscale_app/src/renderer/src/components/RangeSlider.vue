<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: number
    min?: number
    max?: number
    step?: number
    defaultValue?: number
    disabled?: boolean
  }>(),
  {
    min: 0,
    max: 100,
    step: 1,
    defaultValue: 0,
    disabled: false
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

const dragging = ref(false)

const percent = computed(() => ((props.modelValue - props.min) / (props.max - props.min)) * 100)
const defaultPercent = computed(
  () => ((props.defaultValue - props.min) / (props.max - props.min)) * 100
)

function onInput(e: Event): void {
  emit('update:modelValue', Number((e.target as HTMLInputElement).value))
}
</script>

<template>
  <div class="range-field" :class="{ disabled }">
    <div class="track-wrap">
      <div class="track">
        <div class="fill" :style="{ width: percent + '%' }" />
        <div
          class="default-marker"
          :style="{ left: defaultPercent + '%' }"
          :title="`Padrão: ${defaultValue}`"
        />
      </div>
      <input
        class="range-input"
        type="range"
        :min="min"
        :max="max"
        :step="step"
        :value="modelValue"
        :disabled="disabled"
        @input="onInput"
        @pointerdown="dragging = true"
        @pointerup="dragging = false"
      />
      <div v-if="dragging && !disabled" class="tooltip" :style="{ left: percent + '%' }">
        {{ modelValue }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.range-field {
  width: 100%;
}

.range-field.disabled {
  opacity: 0.6;
}

.range-field.disabled .range-input {
  cursor: not-allowed;
}

.track-wrap {
  position: relative;
  height: 20px;
  display: flex;
  align-items: center;
}

.track {
  position: absolute;
  left: 0;
  right: 0;
  height: 4px;
  border-radius: 999px;
  background: var(--surface-3);
}

.fill {
  height: 100%;
  border-radius: 999px;
  background: var(--color-primary);
}

.default-marker {
  position: absolute;
  top: 50%;
  width: 2px;
  height: 8px;
  background: var(--text-tertiary);
  transform: translate(-50%, -50%);
  border-radius: 1px;
}

.range-input {
  position: relative;
  width: 100%;
  margin: 0;
  appearance: none;
  background: transparent;
  cursor: pointer;
}

.range-input::-webkit-slider-thumb {
  appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #fff;
  border: 3px solid var(--color-primary);
  margin-top: 0;
  cursor: pointer;
}

.range-input::-moz-range-thumb {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #fff;
  border: 3px solid var(--color-primary);
  cursor: pointer;
}

.range-input::-webkit-slider-runnable-track {
  height: 4px;
  background: transparent;
}

.tooltip {
  position: absolute;
  bottom: 20px;
  transform: translateX(-50%);
  background: var(--surface-3);
  color: var(--text-primary);
  font-size: 11px;
  font-weight: var(--fw-semibold);
  padding: 2px 6px;
  border-radius: 4px;
  pointer-events: none;
  box-shadow: var(--shadow-sm);
  white-space: nowrap;
}
</style>
