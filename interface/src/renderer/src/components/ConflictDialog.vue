<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { FileWarning } from '@lucide/vue'
import AppButton from './atoms/AppButton.vue'
import type { RespostaDeConflito } from '../composables/usePerguntaDeConflito'

// A mesma pergunta em todos os modos: o arquivo de destino ja' existe, e a
// pessoa escolheu "Perguntar". Vem antes de processar -- o backend recusou o
// pedido sem criar job (app/destino.py) --, entao "Cancelar" nao perde nada.

const props = defineProps<{
  /** O caminho que ja' existe; `null` fecha a caixa. */
  caminho: string | null
}>()

const emit = defineEmits<{ responder: [resposta: RespostaDeConflito] }>()

const { t } = useI18n()
const caixa = ref<HTMLElement | null>(null)

const partes = computed(() => {
  const caminho = props.caminho ?? ''
  const corte = Math.max(caminho.lastIndexOf('/'), caminho.lastIndexOf('\\'))
  return { nome: caminho.slice(corte + 1), pasta: corte > 0 ? caminho.slice(0, corte) : '' }
})

function aoTeclar(evento: KeyboardEvent): void {
  if (evento.key === 'Escape') emit('responder', null)
}

watch(
  () => props.caminho,
  async (aberta) => {
    if (aberta) {
      window.addEventListener('keydown', aoTeclar)
      // O foco vai para a opcao que nao apaga nada.
      await nextTick()
      caixa.value
        ?.querySelector<HTMLButtonElement>('[data-padrao] button, button[data-padrao]')
        ?.focus()
    } else {
      window.removeEventListener('keydown', aoTeclar)
    }
  },
  { immediate: true }
)

onBeforeUnmount(() => window.removeEventListener('keydown', aoTeclar))
</script>

<template>
  <Teleport to="body">
    <div v-if="caminho" class="conflict-backdrop" @click.self="emit('responder', null)">
      <div
        ref="caixa"
        class="conflict-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="conflict-dialog-title"
        aria-describedby="conflict-dialog-body"
      >
        <div class="conflict-head">
          <FileWarning :size="18" class="conflict-icon" />
          <h3 id="conflict-dialog-title">{{ t('destination.dialog.title') }}</h3>
        </div>
        <p id="conflict-dialog-body" class="conflict-body">
          <strong class="conflict-name">{{ partes.nome }}</strong>
          <span v-if="partes.pasta" class="conflict-folder">{{ partes.pasta }}</span>
        </p>

        <div class="conflict-options">
          <AppButton variant="primary" data-padrao @click="emit('responder', 'rename')">
            {{ t('destination.dialog.keepBoth') }}
          </AppButton>
          <p class="conflict-hint">{{ t('destination.dialog.keepBothHint') }}</p>
          <AppButton variant="outline" @click="emit('responder', 'overwrite')">
            {{ t('destination.dialog.replace') }}
          </AppButton>
          <p class="conflict-hint">{{ t('destination.dialog.replaceHint') }}</p>
        </div>

        <div class="conflict-foot">
          <AppButton variant="ghost" @click="emit('responder', null)">
            {{ t('destination.dialog.cancel') }}
          </AppButton>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.conflict-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 60;
}

.conflict-dialog {
  width: 400px;
  max-width: 92vw;
  background: var(--surface-1);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.conflict-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.conflict-head h3 {
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.conflict-icon {
  color: var(--color-warning);
  flex-shrink: 0;
}

.conflict-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.conflict-name {
  color: var(--text-primary);
  font-size: var(--fs-label-sm);
  overflow-wrap: anywhere;
}

.conflict-folder {
  color: var(--text-tertiary);
  font-size: var(--fs-caption);
  overflow-wrap: anywhere;
}

.conflict-options {
  display: flex;
  flex-direction: column;
}

.conflict-options > :deep(button) {
  width: 100%;
}

.conflict-hint {
  margin: var(--space-1) 0 var(--space-3);
  color: var(--text-tertiary);
  font-size: var(--fs-caption);
}

.conflict-foot {
  display: flex;
  justify-content: flex-end;
}
</style>
