<script setup lang="ts">
import { HelpCircle, SunMoon, ArrowLeft } from '@lucide/vue'

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
      <button v-if="showBack" class="icon-btn" type="button" @click="$emit('back')">
        <ArrowLeft :size="18" />
      </button>
      <h1 class="page-title">{{ title }}</h1>
    </div>

    <div class="topbar-right">
      <slot name="actions" />
      <button class="icon-btn" type="button" title="Ajuda"><HelpCircle :size="18" /></button>
      <button class="icon-btn" type="button" title="Tema"><SunMoon :size="18" /></button>
      <div class="avatar">A</div>
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

.icon-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  border: 1px solid var(--surface-border-soft);
  background: var(--surface-1);
  color: var(--text-secondary);
  cursor: pointer;
}

.icon-btn:hover {
  background: var(--surface-2);
  color: var(--text-primary);
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--color-primary), #8b5cf6);
  color: #fff;
  font-size: 13px;
  font-weight: var(--fw-semibold);
}
</style>
