<script setup lang="ts">
import { X } from '@lucide/vue'
import AppButton from './atoms/AppButton.vue'

// O cartao dos avisos no canto da janela (atualizacao pronta, modelos
// baixando). So' a aparencia: quem posiciona e' a pilha em App.vue, para dois
// avisos ao mesmo tempo ficarem um sobre o outro em vez de sobrepostos.

defineProps<{ visible: boolean; title: string; body?: string; closeLabel: string }>()
const emit = defineEmits<{ close: [] }>()
</script>

<template>
  <Transition name="toast-card">
    <div v-if="visible" class="toast-card" role="status">
      <div class="toast-icon"><slot name="icon" /></div>
      <div class="toast-text">
        <p class="toast-title">{{ title }}</p>
        <p v-if="body" class="toast-body">{{ body }}</p>
        <slot />
        <div v-if="$slots.actions" class="toast-actions"><slot name="actions" /></div>
      </div>
      <AppButton
        variant="ghost"
        size="sm"
        icon-only
        :title="closeLabel"
        class="toast-close"
        @click="emit('close')"
      >
        <template #icon><X :size="14" /></template>
      </AppButton>
    </div>
  </Transition>
</template>

<style scoped>
.toast-card {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2-5);
  width: 340px;
  max-width: calc(100vw - 2 * var(--space-4));
  padding: var(--space-3);
  background: var(--surface-1);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
}

.toast-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-primary) 12%, transparent);
  color: var(--color-primary);
}

.toast-text {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
  flex: 1;
}

.toast-title {
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.toast-body {
  font-size: var(--fs-caption);
  color: var(--text-secondary);
}

.toast-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-1-5);
}

.toast-close {
  flex-shrink: 0;
  margin: calc(-1 * var(--space-1)) calc(-1 * var(--space-1)) 0 0;
}

.toast-card-enter-active,
.toast-card-leave-active {
  transition:
    opacity 180ms ease,
    transform 180ms ease;
}

.toast-card-enter-from,
.toast-card-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
