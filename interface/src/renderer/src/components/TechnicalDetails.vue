<script setup lang="ts">
import { ref } from 'vue'
import { ChevronDown, Copy, Check } from '@lucide/vue'
import AppButton from './atoms/AppButton.vue'

defineProps<{
  summary: string
  text: string
}>()

const open = ref(false)
const copied = ref(false)

async function copy(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    // clipboard permission denied — nothing else reasonable to do here
  }
}
</script>

<template>
  <div class="technical-details">
    <button class="details-toggle" type="button" @click="open = !open">
      <ChevronDown :size="12" class="chevron" :class="{ open }" />
      {{ summary }}
    </button>
    <div v-if="open" class="details-body">
      <pre class="details-text">{{ text }}</pre>
      <AppButton variant="secondary" size="sm" @click="copy(text)">
        <template #icon><component :is="copied ? Check : Copy" :size="12" /></template>
        {{ copied ? 'Copiado' : 'Copiar' }}
      </AppButton>
    </div>
  </div>
</template>

<style scoped>
.technical-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.details-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: var(--text-tertiary);
  font-size: 11px;
  cursor: pointer;
  padding: 0;
}

.chevron {
  transition: transform var(--transition-fast);
}

.chevron.open {
  transform: rotate(-180deg);
}

.details-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}

.details-text {
  margin: 0;
  max-height: 160px;
  overflow: auto;
  background: var(--surface-0);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  padding: var(--space-2);
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-secondary);
  white-space: pre-wrap;
  overflow-wrap: break-word;
  word-break: break-word;
}
</style>
