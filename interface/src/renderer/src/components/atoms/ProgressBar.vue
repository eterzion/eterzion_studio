<script setup lang="ts">
// The single progress track for the app. `tone` exists because a queued job
// shows an empty neutral track while a running one fills with the module's
// accent — same bar, two meanings.
withDefaults(
  defineProps<{
    value: number
    tone?: 'primary' | 'neutral' | 'success' | 'danger'
  }>(),
  { tone: 'primary' }
)
</script>

<template>
  <div
    class="progress-track"
    role="progressbar"
    :aria-valuenow="Math.round(value)"
    aria-valuemin="0"
    aria-valuemax="100"
  >
    <div class="progress-fill" :class="`tone-${tone}`" :style="{ width: `${value}%` }" />
  </div>
</template>

<style scoped>
.progress-track {
  width: 100%;
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--surface-3);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width 200ms ease;
}

.tone-primary {
  background: var(--color-primary);
}
.tone-neutral {
  background: var(--text-tertiary);
}
.tone-success {
  background: var(--color-success);
}
.tone-danger {
  background: var(--color-danger);
}
</style>
