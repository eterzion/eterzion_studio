<script setup lang="ts">
defineProps<{
  modelValue: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()
</script>

<template>
  <button
    type="button"
    role="switch"
    :aria-checked="modelValue"
    class="switch"
    :class="{ on: modelValue }"
    :disabled="disabled"
    @click="emit('update:modelValue', !modelValue)"
  >
    <span class="knob" />
  </button>
</template>

<style scoped>
.switch {
  width: 36px;
  height: 21px;
  flex-shrink: 0;
  border-radius: var(--radius-full);
  border: none;
  background: var(--surface-3);
  position: relative;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.switch:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.switch.on {
  background: var(--color-primary);
}

.switch:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 17px;
  height: 17px;
  border-radius: var(--radius-sm);
  background: #fff;
  transition: transform var(--transition-fast);
}

.switch.on .knob {
  transform: translateX(15px);
}
</style>
