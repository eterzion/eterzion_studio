<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Download, X } from '@lucide/vue'
import AppButton from './atoms/AppButton.vue'
import { dismissToast, requestRestart, requestUpdatesFocus, updatesState } from '../store/updates'

// Aparece uma vez por versao, quando ela termina de baixar (store/updates.ts).
// Nao interrompe: fica no canto, e fechar nao perde nada -- a versao continua
// pronta, o selo da barra lateral continua avisando e ela instala ao fechar o app.

const emit = defineEmits<{ openUpdates: [] }>()

const { t } = useI18n()

async function restart(): Promise<void> {
  // Com processamento em andamento, a confirmacao mora na secao Atualizacoes:
  // leva ate' la' em vez de reiniciar.
  if ((await requestRestart()) === 'confirm') {
    dismissToast()
    requestUpdatesFocus()
    emit('openUpdates')
  }
}
</script>

<template>
  <Transition name="update-toast">
    <div v-if="updatesState.toastVisible" class="update-toast" role="status">
      <div class="toast-icon"><Download :size="18" /></div>
      <div class="toast-text">
        <p class="toast-title">
          {{ t('updates.toast.title', { version: updatesState.version }) }}
        </p>
        <p class="toast-body">{{ t('updates.toast.body') }}</p>
        <div class="toast-actions">
          <AppButton
            variant="primary"
            size="sm"
            :loading="updatesState.installing"
            @click="restart"
          >
            {{ t('updates.restartNow') }}
          </AppButton>
          <AppButton variant="ghost" size="sm" @click="dismissToast">
            {{ t('updates.later') }}
          </AppButton>
        </div>
      </div>
      <AppButton
        variant="ghost"
        size="sm"
        icon-only
        :title="t('updates.later')"
        class="toast-close"
        @click="dismissToast"
      >
        <template #icon><X :size="14" /></template>
      </AppButton>
    </div>
  </Transition>
</template>

<style scoped>
.update-toast {
  position: fixed;
  right: var(--space-4);
  bottom: var(--space-4);
  z-index: 100;
  display: flex;
  align-items: flex-start;
  gap: var(--space-2-5);
  width: 340px;
  max-width: calc(100vw - 2 * var(--space-4));
  padding: var(--space-3);
  background: var(--surface-1);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
}

.toast-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-primary) 12%, transparent);
  color: var(--color-primary);
}

.toast-text {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
  flex: 1;
}

.toast-title {
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.toast-body {
  font-size: var(--fs-caption);
  color: var(--text-secondary);
}

.toast-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-1-5);
}

.toast-close {
  flex-shrink: 0;
  margin: calc(-1 * var(--space-1)) calc(-1 * var(--space-1)) 0 0;
}

.update-toast-enter-active,
.update-toast-leave-active {
  transition:
    opacity 180ms ease,
    transform 180ms ease;
}

.update-toast-enter-from,
.update-toast-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
