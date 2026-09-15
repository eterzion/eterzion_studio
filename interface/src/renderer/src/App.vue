<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ServerCrash } from '@lucide/vue'
import AppSidebar from './components/AppSidebar.vue'
import AppButton from './components/atoms/AppButton.vue'
import AppSpinner from './components/atoms/AppSpinner.vue'
import HomeView from './views/HomeView.vue'
import ImageEditorView from './views/ImageEditorView.vue'
import HistoryView from './views/HistoryView.vue'
import SettingsView from './views/SettingsView.vue'
import VideoEditorView from './views/VideoEditorView.vue'
import AudioView from './views/AudioView.vue'
import LicenseActivationView from './views/LicenseActivationView.vue'
import CompressionView from './views/CompressionView.vue'
import ComponentsView from './views/ComponentsView.vue'
import UpdateToast from './components/UpdateToast.vue'
import ModelosIniciaisToast from './components/ModelosIniciaisToast.vue'
import type { NavKey } from './types'
import { apiStatus, checkApiStatus } from './store/apiStatus'
import { setTheme } from './store/settings'
import { initLicense, isHardBlocked, licenseState } from './store/license'
import { initUpdates } from './store/updates'
import { baixarModelosIniciais } from './store/modelosIniciais'
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
  // Mesmo com a tela de ativacao ocupando a janela: e' daqui que o processo
  // principal recebe a preferencia de procurar atualizacoes (ver updater.ts).
  void initUpdates()
})

// Os modelos que o instalador pediu ("baixar depois de ativar") so' podem
// descer com a licenca ativa -- o download pelo nosso servidor exige isso. So'
// 'active', e nao os estados de tolerancia offline: sem rede, o download
// falharia e so' serviria para mostrar um aviso de erro.
watch(
  () => licenseState.status,
  (status) => {
    if (status === 'active') void baixarModelosIniciais()
  },
  { immediate: true }
)

const { t } = useI18n()
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
        <p>{{ t('app.connecting') }}</p>
      </div>
      <div v-else-if="apiStatus.error" class="api-status-view error">
        <ServerCrash :size="28" />
        <p class="api-error-title">{{ t('app.apiErrorTitle') }}</p>
        <p class="api-error-detail">{{ apiStatus.error }}</p>
        <AppButton variant="primary" size="lg" @click="checkApiStatus">{{
          t('activation.retry')
        }}</AppButton>
      </div>

      <!-- Vídeo and Áudio keep their queues in component state, so switching
           tabs used to destroy every job on them. The Imagem screen never had
           the problem because its queue lives in store/jobs.ts — these two are
           cached instead, which is the smaller change and also preserves the
           panel each screen was showing. Everything else is deliberately NOT
           cached: Histórico and Configurações load their data on mount and
           would go stale. -->
      <KeepAlive v-else :include="['VideoEditorView', 'AudioView']">
        <HomeView v-if="active === 'home'" @navigate="navigate" />
        <ImageEditorView v-else-if="active === 'imagem'" @back="active = 'home'" />
        <HistoryView v-else-if="active === 'historico'" @open-image="active = 'imagem'" />
        <ComponentsView v-else-if="active === 'componentes'" />
        <SettingsView v-else-if="active === 'configuracoes'" />
        <VideoEditorView v-else-if="active === 'video'" @back="active = 'home'" />
        <AudioView v-else-if="active === 'audio'" @back="active = 'home'" />
        <CompressionView v-else-if="active === 'compressao'" @back="active = 'home'" />
        <div v-else class="placeholder-view">
          <p>{{ t('app.notImplemented') }}</p>
        </div>
      </KeepAlive>

      <!-- Os avisos do canto empilham aqui: dois ao mesmo tempo (modelos
           baixando e uma versao nova pronta) ficam um sobre o outro. -->
      <div class="toast-stack">
        <ModelosIniciaisToast @open-components="active = 'componentes'" />
        <UpdateToast @open-updates="active = 'configuracoes'" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.toast-stack {
  position: fixed;
  right: var(--space-4);
  bottom: var(--space-4);
  z-index: 100;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--space-2);
  /* A pilha cobre um canto da janela; so' os cartoes recebem clique. */
  pointer-events: none;
}

.toast-stack > * {
  pointer-events: auto;
}

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
