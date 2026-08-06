<script setup lang="ts">
import { ref, type Component } from 'vue'
import { ChevronDown } from '@lucide/vue'

const props = withDefaults(
  defineProps<{
    title: string
    description?: string
    icon?: Component
    defaultOpen?: boolean
  }>(),
  { defaultOpen: true, description: undefined, icon: undefined }
)

const open = ref(props.defaultOpen)
</script>

<template>
  <section class="panel">
    <button
      class="panel-header"
      type="button"
      :aria-expanded="open"
      @click="open = !open"
    >
      <div v-if="icon" class="panel-icon"><component :is="icon" :size="16" /></div>
      <div class="panel-heading">
        <span class="panel-title">{{ title }}</span>
        <span v-if="description" class="panel-description">{{ description }}</span>
      </div>
      <ChevronDown :size="16" class="chevron" :class="{ collapsed: !open }" />
    </button>
    <div v-show="open" class="panel-body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.panel {
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-md);
  overflow: hidden;
  flex-shrink: 0;
  transition: border-color var(--transition-fast);
}

.panel-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3);
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
}

.panel-header:hover {
  background: var(--surface-3);
}

.panel-header:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: -2px;
}

.panel-icon {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.panel-heading {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.panel-title {
  font-size: var(--fs-section-title);
  font-weight: var(--fw-semibold);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.panel-description {
  font-size: 11px;
  font-weight: var(--fw-regular);
  text-transform: none;
  letter-spacing: normal;
  color: var(--text-tertiary);
  overflow-wrap: break-word;
}

.chevron {
  flex-shrink: 0;
  color: var(--text-tertiary);
  transition: transform var(--transition-fast);
}

.chevron.collapsed {
  transform: rotate(-90deg);
}

.panel-body {
  padding: 0 var(--space-3) var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  animation: panel-body-in 160ms ease;
}

@keyframes panel-body-in {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
