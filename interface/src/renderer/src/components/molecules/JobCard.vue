<script setup lang="ts">
import { X } from '@lucide/vue'
import AppButton from '../atoms/AppButton.vue'

defineProps<{ fileName: string }>()
defineEmits<{ remove: [] }>()
</script>

<template>
  <div class="job-card">
    <div class="job-card-header">
      <span class="job-name">{{ fileName }}</span>
      <AppButton variant="ghost" icon-only title="Remover" @click="$emit('remove')">
        <template #icon><X :size="16" /></template>
      </AppButton>
    </div>
    <slot />
  </div>
</template>

<style scoped>
.job-card {
  background: var(--surface-1);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.job-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.job-name {
  font-weight: 600;
  font-size: var(--fs-label);
}
</style>
