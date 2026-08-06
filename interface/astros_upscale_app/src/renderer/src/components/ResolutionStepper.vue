<script setup lang="ts">
import { ref } from 'vue'
import { Minus, Plus } from '@lucide/vue'

const props = withDefaults(
  defineProps<{
    modelValue: number
    label: string
    min?: number
    max?: number
    step?: number
    disabled?: boolean
  }>(),
  { min: 1, max: 32000, step: 1, disabled: false }
)

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

function clamp(value: number): number {
  return Math.min(props.max, Math.max(props.min, value))
}

function setValue(value: number): void {
  emit('update:modelValue', clamp(value))
}

function onInput(raw: string): void {
  const n = Number(raw)
  if (!Number.isNaN(n)) setValue(n)
}

// Press-and-hold: a small delay, then accelerating repeats — standard native-stepper feel.
let holdTimeout: ReturnType<typeof setTimeout> | undefined
let holdInterval: ReturnType<typeof setInterval> | undefined
let repeats = 0

function startHold(direction: 1 | -1): void {
  setValue(props.modelValue + direction * props.step)
  repeats = 0
  holdTimeout = setTimeout(() => {
    holdInterval = setInterval(() => {
      repeats++
      const accelerated = props.step * (repeats > 10 ? 5 : 1)
      setValue(props.modelValue + direction * accelerated)
    }, 80)
  }, 400)
}

function stopHold(): void {
  clearTimeout(holdTimeout)
  clearInterval(holdInterval)
}

const focused = ref(false)
</script>

<template>
  <div class="stepper-field">
    <label class="stepper-label">{{ label }}</label>
    <div class="stepper" :class="{ disabled, focused }">
      <button
        class="step-btn"
        type="button"
        :disabled="disabled || modelValue <= min"
        aria-label="Diminuir"
        @pointerdown="startHold(-1)"
        @pointerup="stopHold"
        @pointerleave="stopHold"
      >
        <Minus :size="14" />
      </button>
      <input
        class="step-value"
        type="number"
        :value="modelValue"
        :min="min"
        :max="max"
        :disabled="disabled"
        @input="onInput(($event.target as HTMLInputElement).value)"
        @focus="focused = true"
        @blur="focused = false"
      />
      <button
        class="step-btn"
        type="button"
        :disabled="disabled || modelValue >= max"
        aria-label="Aumentar"
        @pointerdown="startHold(1)"
        @pointerup="stopHold"
        @pointerleave="stopHold"
      >
        <Plus :size="14" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.stepper-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.stepper-label {
  font-size: 11px;
  color: var(--text-tertiary);
}

.stepper {
  display: flex;
  align-items: center;
  background: var(--surface-3);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-sm);
  overflow: hidden;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.stepper.focused {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 2px var(--color-primary-soft);
}

.stepper.disabled {
  opacity: 0.55;
}

.step-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 34px;
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast), transform 80ms ease;
}

.step-btn:hover:not(:disabled) {
  background: var(--surface-2);
  color: var(--color-primary);
}

.step-btn:active:not(:disabled) {
  transform: scale(0.9);
}

.step-btn:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.step-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.step-value {
  width: 0;
  flex: 1;
  min-width: 0;
  background: transparent;
  border: none;
  border-left: 1px solid var(--surface-border-soft);
  border-right: 1px solid var(--surface-border-soft);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  text-align: center;
  padding: 0 2px;
  -moz-appearance: textfield;
}

.step-value::-webkit-inner-spin-button,
.step-value::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.step-value:focus {
  outline: none;
}

</style>
