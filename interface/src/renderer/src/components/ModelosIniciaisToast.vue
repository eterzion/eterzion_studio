<script setup lang="ts">
import { computed, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { AlertTriangle, Check, Download } from '@lucide/vue'
import AppButton from './atoms/AppButton.vue'
import ProgressBar from './atoms/ProgressBar.vue'
import ToastCard from './ToastCard.vue'
import { fecharAvisoModelosIniciais, modelosIniciais } from '../store/modelosIniciais'

// O aviso do download que o instalador pediu (store/modelosIniciais.ts).
// Fica no canto e nao segura o app: fechar esconde o aviso, e o download
// continua. O progresso conta modelos, nao bytes -- e' o que a API informa.

const emit = defineEmits<{ openComponents: [] }>()
const { t } = useI18n()

const titulo = computed(() => {
  if (modelosIniciais.fase === 'pronto') return t('initialModels.ready')
  if (modelosIniciais.fase === 'erro') return t('initialModels.failed')
  return t('initialModels.downloading', {
    done: modelosIniciais.concluidos,
    total: modelosIniciais.total
  })
})

const corpo = computed(() => {
  if (modelosIniciais.fase === 'pronto') return t('initialModels.readyBody')
  if (modelosIniciais.fase === 'erro') return t('initialModels.failedBody')
  return t('initialModels.downloadingBody')
})

const percentual = computed(() =>
  modelosIniciais.total ? Math.round((modelosIniciais.concluidos / modelosIniciais.total) * 100) : 0
)

// "Pronto" nao pede nada de ninguem: some sozinho depois de lido. O erro fica
// ate' ser fechado, porque diz o que fazer.
let timer: ReturnType<typeof setTimeout> | undefined
watch(
  () => modelosIniciais.fase,
  (fase) => {
    if (timer) clearTimeout(timer)
    if (fase === 'pronto') timer = setTimeout(fecharAvisoModelosIniciais, 6000)
  }
)
onUnmounted(() => {
  if (timer) clearTimeout(timer)
})

function abrirComponentes(): void {
  fecharAvisoModelosIniciais()
  emit('openComponents')
}
</script>

<template>
  <ToastCard
    :visible="modelosIniciais.visivel && modelosIniciais.fase !== 'inativo'"
    :title="titulo"
    :body="corpo"
    :close-label="t('initialModels.close')"
    @close="fecharAvisoModelosIniciais"
  >
    <template #icon>
      <Check v-if="modelosIniciais.fase === 'pronto'" :size="18" />
      <AlertTriangle v-else-if="modelosIniciais.fase === 'erro'" :size="18" />
      <Download v-else :size="18" />
    </template>
    <ProgressBar v-if="modelosIniciais.fase === 'baixando'" :value="percentual" />
    <template v-if="modelosIniciais.fase === 'erro'" #actions>
      <AppButton variant="secondary" size="sm" @click="abrirComponentes">
        {{ t('initialModels.openComponents') }}
      </AppButton>
    </template>
  </ToastCard>
</template>
