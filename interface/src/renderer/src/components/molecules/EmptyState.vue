<script setup lang="ts">
import AppButton from '../atoms/AppButton.vue'

// The one shape an empty screen takes across the app: an icon, a title saying
// what is missing, an optional line saying what will appear here, and the single
// action that fills it. Everything below the title is optional, so a bare
// "nothing here yet" state costs one prop.
defineProps<{
  title: string
  description?: string
  actionLabel?: string
}>()

defineEmits<{ action: [] }>()
</script>

<template>
  <div class="empty-state">
    <div v-if="$slots.icon" class="empty-icon"><slot name="icon" /></div>
    <h2>{{ title }}</h2>
    <p v-if="description">{{ description }}</p>
    <AppButton
      v-if="actionLabel"
      variant="primary"
      size="lg"
      class="empty-action"
      @click="$emit('action')"
    >
      <template #icon><slot name="action-icon" /></template>
      {{ actionLabel }}
    </AppButton>
  </div>
</template>

<style scoped>
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-4);
  text-align: center;
  color: var(--text-tertiary);
}

.empty-icon {
  display: flex;
  color: var(--text-tertiary);
}

.empty-state h2 {
  margin: var(--space-2) 0 0;
  font-size: var(--fs-page-title);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.empty-state p {
  margin: 0;
  font-size: var(--fs-label);
}

.empty-action {
  margin-top: var(--space-2);
}
</style>
