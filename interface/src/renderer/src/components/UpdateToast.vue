<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Download } from '@lucide/vue'
import AppButton from './atoms/AppButton.vue'
import ToastCard from './ToastCard.vue'
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
  <ToastCard
    :visible="updatesState.toastVisible"
    :title="t('updates.toast.title', { version: updatesState.version })"
    :body="t('updates.toast.body')"
    :close-label="t('updates.later')"
    @close="dismissToast"
  >
    <template #icon><Download :size="18" /></template>
    <template #actions>
      <AppButton variant="primary" size="sm" :loading="updatesState.installing" @click="restart">
        {{ t('updates.restartNow') }}
      </AppButton>
      <AppButton variant="ghost" size="sm" @click="dismissToast">
        {{ t('updates.later') }}
      </AppButton>
    </template>
  </ToastCard>
</template>
