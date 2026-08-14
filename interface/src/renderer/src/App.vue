<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ServerCrash } from '@lucide/vue'
import AppSidebar from './components/AppSidebar.vue'
import AppButton from './components/atoms/AppButton.vue'
import AppSpinner from './components/atoms/AppSpinner.vue'
import HomeView from './views/HomeView.vue'
import ImageEditorView from './views/ImageEditorView.vue'
import HistoryView from './views/HistoryView.vue'
import SettingsView from './views/SettingsView.vue'
import VideoView from './views/VideoView.vue'
import AudioView from './views/AudioView.vue'
import LicenseActivationView from './views/LicenseActivationView.vue'
import type { NavKey } from './types'
import { apiStatus, checkApiStatus } from './store/apiStatus'
import { setTheme } from './store/settings'
import { initLicense, isHardBlocked, licenseState } from './store/license'
import { currentResolvedTheme } from './theme'
import { hasNativeApi } from './services/native'

const active = ref<NavKey>('home')
const darkMode = computed(() => currentResolvedTheme.value === 'dark')

// Full takeover (no sidebar, LicenseActivationView only) before the first
// successful check this session ('not_activated'/'blocked'/never-verified
// 'checking'/'error'). Once a check has succeeded once, a later 'error'
// (server unreachable) degrades to an inline badge/banner per-view instead —
// see isHardBlocked's doc comment in store/license.ts.
const hardBlocked = computed(() => isHardBlocked(licenseState.status, licenseState.everUsable))

function navigate(key: NavKey): void {
  active.value = key
}

function toggleTheme(): void {
  // A quick toggle always sets an explicit mode — "Automático" (follow
  // Windows) stays available in Configurações, but flipping this switch is a
  // deliberate manual override of whatever it was resolving to.
  setTheme(darkMode.value ? 'light' : 'dark')
}

onMounted(() => {
  if (hasNativeApi) checkApiStatus()
  if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
    Notification.requestPermission()
  }
  initLicense()
})
</script>

<template>
  <div class="app-shell">
    <LicenseActivationView v-if="hardBlocked" />
    <template v-else>
      <AppSidebar
        :active="active"
        :dark-mode="darkMode"
        @navigate="navigate"
        @toggle-theme="toggleTheme"
      />

      <div v-if="apiStatus.checking" class="api-status-view">
        <AppSpinner :size="28" class="text-accent" />
        <p>Conectando ao servidor da API (astros_upscale_api)…</p>
      </div>
      <div v-else-if="apiStatus.error" class="api-status-view error">
        <ServerCrash :size="28" />
        <p class="api-error-title">Não foi possível conectar à API</p>
        <p class="api-error-detail">{{ apiStatus.error }}</p>
        <AppButton variant="primary" size="lg" @click="checkApiStatus">Tentar novamente</AppButton>
      </div>

      <HomeView v-else-if="active === 'home'" @navigate="navigate" />
      <ImageEditorView v-else-if="active === 'imagem'" @back="active = 'home'" />
      <HistoryView v-else-if="active === 'historico'" @open-image="active = 'imagem'" />
      <SettingsView v-else-if="active === 'configuracoes'" />
      <VideoView v-else-if="active === 'video'" @back="active = 'home'" />
      <AudioView v-else-if="active === 'audio'" @back="active = 'home'" />
      <div v-else class="placeholder-view">
        <p>Esta seção ainda não foi implementada nesta prévia de redesenho.</p>
      </div>
    </template>
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
</style>
