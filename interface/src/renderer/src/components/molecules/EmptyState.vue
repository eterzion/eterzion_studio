<script setup lang="ts">
import AppButton from '../atoms/AppButton.vue'

// research.md Audit (a): the 4 byte-identical empty states have no standalone icon above
// the message — the icon lives inside the action button (e.g. an Upload icon), via the
// `icon` slot below.
defineProps<{
  message: string
  actionLabel?: string
}>()

defineEmits<{ action: [] }>()
</script>

<template>
  <div class="empty-state">
    <p>{{ message }}</p>
    <AppButton v-if="actionLabel" variant="primary" size="lg" @click="$emit('action')">
      <template #icon><slot name="icon" /></template>
      {{ actionLabel }}
    </AppButton>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-6);
  color: var(--text-secondary);
}
</style>
