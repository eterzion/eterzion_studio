<script setup lang="ts">
import { ArrowLeft } from '@lucide/vue'
import LicenseWidget from './LicenseWidget.vue'
import AppButton from './atoms/AppButton.vue'

withDefaults(
  defineProps<{
    title: string
    showBack?: boolean
  }>(),
  { showBack: false }
)

defineEmits<{
  back: []
}>()
</script>

<template>
  <header class="topbar">
    <div class="topbar-left">
      <AppButton v-if="showBack" variant="secondary" icon-only size="lg" @click="$emit('back')">
        <template #icon><ArrowLeft :size="18" /></template>
      </AppButton>
      <h1 class="page-title">{{ title }}</h1>
    </div>

    <div class="topbar-right">
      <slot name="actions" />
      <LicenseWidget />
    </div>
  </header>
</template>

<style scoped>
.topbar {
  height: 60px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--space-4);
  border-bottom: 1px solid var(--surface-border-soft);
  background: var(--surface-0);
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.page-title {
  font-size: var(--fs-page-title);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--color-primary), #8b5cf6);
  color: var(--on-primary);
  font-size: 13px;
  font-weight: var(--fw-semibold);
}
</style>
