<script setup lang="ts">
defineProps<{
  label: string
  description?: string
}>()
</script>

<template>
  <div class="setting-row">
    <div class="setting-text">
      <span class="setting-label">{{ label }}</span>
      <span v-if="description" class="setting-description">{{ description }}</span>
    </div>
    <div class="setting-control">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--surface-border-soft);
  flex-wrap: wrap;
}

.setting-row:last-child {
  border-bottom: none;
}

.setting-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 200px;
  flex: 1;
}

.setting-label {
  font-size: var(--fs-label);
  font-weight: var(--fw-medium);
  color: var(--text-primary);
}

.setting-description {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
  overflow-wrap: break-word;
}

.setting-control {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  min-width: 0;
  max-width: 100%;
}
</style>
