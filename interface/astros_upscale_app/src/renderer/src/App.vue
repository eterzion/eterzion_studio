<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Loader2, ServerCrash } from '@lucide/vue'
import AppSidebar from './components/AppSidebar.vue'
import HomeView from './views/HomeView.vue'
import ImageEditorView from './views/ImageEditorView.vue'
import ModelsView from './views/ModelsView.vue'
import HistoryView from './views/HistoryView.vue'
import SettingsView from './views/SettingsView.vue'
import type { NavKey } from './types'
import { apiStatus, checkApiStatus } from './store/apiStatus'
import { settingsState, setTheme } from './store/settings'
import { hasNativeApi } from './api'

const active = ref<NavKey>('home')
const darkMode = computed(() => settingsState.theme === 'dark')

function navigate(key: NavKey): void {
  active.value = key
}

function toggleTheme(): void {
  setTheme(darkMode.value ? 'light' : 'dark')
}

onMounted(() => {
  if (hasNativeApi) checkApiStatus()
  if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
    Notification.requestPermission()
  }
})
</script>

<template>
  <div class="app-shell">
    <AppSidebar
      :active="active"
      :dark-mode="darkMode"
      @navigate="navigate"
      @toggle-theme="toggleTheme"
    />

    <div v-if="apiStatus.checking" class="api-status-view">
      <Loader2 :size="28" class="spin" />
      <p>Conectando ao servidor da API (astros_upscale_api)…</p>
    </div>
    <div v-else-if="apiStatus.error" class="api-status-view error">
      <ServerCrash :size="28" />
      <p class="api-error-title">Não foi possível conectar à API</p>
      <p class="api-error-detail">{{ apiStatus.error }}</p>
      <button class="retry-btn" type="button" @click="checkApiStatus">Tentar novamente</button>
    </div>

    <HomeView v-else-if="active === 'home'" @open-image="active = 'imagem'" />
    <ImageEditorView v-else-if="active === 'imagem'" @back="active = 'home'" />
    <ModelsView v-else-if="active === 'modelos'" />
    <HistoryView v-else-if="active === 'historico'" @open-image="active = 'imagem'" />
    <SettingsView v-else-if="active === 'configuracoes'" @navigate="navigate" />
    <div v-else class="placeholder-view">
      <p>Esta seção ainda não foi implementada nesta prévia de redesenho.</p>
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
  background: var(--surface-0);
}

.placeholder-view {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  font-size: var(--fs-label);
}

.api-status-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--fs-label);
  text-align: center;
  padding: var(--space-4);
}

.api-status-view.error {
  color: var(--color-danger);
}

.api-error-title {
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.api-error-detail {
  max-width: 480px;
  white-space: pre-wrap;
  font-size: var(--fs-caption);
  color: var(--text-secondary);
}

.retry-btn {
  margin-top: var(--space-2);
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  padding: 9px 18px;
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  cursor: pointer;
}

.spin {
  animation: spin 1s linear infinite;
  color: var(--color-primary);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
