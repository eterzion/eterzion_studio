<script setup lang="ts">
/**
 * Tela de Componentes — o que está instalado, o que ocupa disco, o que dá para
 * remover.
 *
 * Existia a API inteira (`GET /components`, `/details`, install/update/delete)
 * e nenhuma tela a consumia: o usuário não tinha como saber o que o app tinha
 * baixado, nem como recuperar o espaço. Isso também travava tirar os modelos
 * embarcados do instalador — sem uma tela para reinstalá-los, removê-los do
 * pacote deixaria o app sem saída.
 *
 * Duas regras herdadas do backend valem aqui (FR-009/FR-063):
 *
 *  - a listagem NUNCA mostra identificador técnico. O `capability_label` da API
 *    vem em português fixo, então a tela usa as chaves de `credits.*`, que já
 *    estão nos onze idiomas e dizem a mesma coisa;
 *  - o detalhe técnico (nome do modelo, versão, licença, e a saída de pip
 *    quando uma instalação falha) só aparece sob demanda, em `/details`.
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  AudioLines,
  Download,
  Film,
  Image as ImageIcon,
  Loader2,
  Music2,
  Palette,
  RefreshCw,
  Trash2,
  TriangleAlert,
  Video
} from '@lucide/vue'

import TopBar from '../components/TopBar.vue'
import {
  downloadErrorCopy,
  getComponentDetails,
  installComponent,
  listComponents,
  uninstallComponent,
  updateComponent,
  type ComponentSummary
} from '../services/api'

const { t } = useI18n()

/** Ícone e cor por capacidade — os mesmos de `SettingsView.vue`, de propósito:
 *  quem viu "Melhoria de imagem — Foto" nos créditos reconhece a mesma linha
 *  aqui. `labelKey` aponta para `credits.*` para não duplicar seis strings em
 *  onze idiomas. */
const CAPABILITIES: Record<string, { labelKey: string; icon: unknown; tint: string }> = {
  photo: { labelKey: 'credits.imagePhoto', icon: ImageIcon, tint: '#3b82f6' },
  anime_image: { labelKey: 'credits.imageAnime', icon: Palette, tint: '#a855f7' },
  anime_video: { labelKey: 'credits.videoAnime', icon: Film, tint: '#f59e0b' },
  real_video: { labelKey: 'credits.videoReal', icon: Video, tint: '#ef4444' },
  speech: { labelKey: 'credits.audioSpeech', icon: AudioLines, tint: '#14b8a6' },
  music: { labelKey: 'credits.audioMusic', icon: Music2, tint: '#ec4899' }
}

const components = ref<ComponentSummary[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)
/** Erro por componente: o que a ação devolveu (422 de speech/music) ou o que
 *  `/details` reportou depois de uma instalação em segundo plano falhar. */
const itemError = ref<Record<string, string>>({})
/** Ação em voo, para desabilitar o botão sem travar a tela inteira. */
const busy = ref<Record<string, boolean>>({})
const confirmingRemoval = ref<string | null>(null)
let confirmTimer: ReturnType<typeof setTimeout> | undefined

const rows = computed(() =>
  components.value
    .filter((c) => c.id in CAPABILITIES)
    .map((c) => ({ ...c, meta: CAPABILITIES[c.id] }))
)

const totalInstalledMb = computed(() =>
  components.value.reduce((sum, c) => sum + (c.size_mb || 0), 0)
)

const anyInstalling = computed(() => components.value.some((c) => c.install_state === 'installing'))

async function refresh(): Promise<void> {
  try {
    const antes = new Map(components.value.map((c) => [c.id, c.install_state]))
    components.value = await listComponents()
    loadError.value = null

    // Uma instalação que sai de `installing` e volta para `not_installed`
    // falhou — o POST já tinha respondido 200 e a thread de fundo é que
    // quebrou. O motivo (saída do pip, disco cheio) só existe em /details,
    // que é onde o backend guarda o detalhe técnico.
    for (const c of components.value) {
      if (antes.get(c.id) === 'installing' && c.install_state === 'not_installed') {
        try {
          const detalhe = await getComponentDetails(c.id)
          if (detalhe.error) {
            // Falha de download vira a frase do motivo, na língua do app; o
            // texto do backend (só pt-BR) fica para o que não é download.
            const copy = downloadErrorCopy(detalhe.error_reason)
            itemError.value[c.id] = copy ? `${copy.message} ${copy.action}` : detalhe.error
          }
        } catch {
          itemError.value[c.id] = t('components.errors.installFailed')
        }
      }
    }
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : t('components.errors.loadFailed')
  } finally {
    loading.value = false
  }
}

/** O `POST /install` responde assim que dispara — o download roda em segundo
 *  plano e não reporta bytes. Sem barra de progresso honesta a fazer, a tela
 *  pergunta o estado de tempos em tempos, e só enquanto há o que esperar. */
let pollTimer: ReturnType<typeof setInterval> | undefined
watch(anyInstalling, (installing) => {
  if (installing && !pollTimer) {
    pollTimer = setInterval(refresh, 2000)
  } else if (!installing && pollTimer) {
    clearInterval(pollTimer)
    pollTimer = undefined
  }
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (confirmTimer) clearTimeout(confirmTimer)
})

async function agir(id: string, acao: 'install' | 'update' | 'remove'): Promise<void> {
  if (busy.value[id]) return
  busy.value[id] = true
  delete itemError.value[id]
  try {
    if (acao === 'install') await installComponent(id)
    else if (acao === 'update') await updateComponent(id)
    else await uninstallComponent(id)
    await refresh()
  } catch (error) {
    // Motivo conhecido vira frase na língua do app; o texto do backend (só
    // pt-BR) fica para o que ainda não tem motivo próprio.
    const reason = (error as { reason?: string | null } | null)?.reason
    itemError.value[id] =
      reason === 'not_available_in_app'
        ? t('components.errors.notAvailableInApp')
        : error instanceof Error
          ? error.message
          : t('components.errors.actionFailed')
  } finally {
    busy.value[id] = false
    confirmingRemoval.value = null
  }
}

/** Remover apaga arquivos e o próximo uso da capacidade baixa tudo de novo.
 *  Pede confirmação como o `clearHistory` das Configurações: o mesmo botão
 *  vira "tem certeza?" por alguns segundos, sem modal. */
function pedirRemocao(id: string): void {
  if (confirmingRemoval.value !== id) {
    confirmingRemoval.value = id
    if (confirmTimer) clearTimeout(confirmTimer)
    confirmTimer = setTimeout(() => (confirmingRemoval.value = null), 4000)
    return
  }
  void agir(id, 'remove')
}

function formatarTamanho(mb: number): string {
  if (!mb) return ''
  return mb >= 1024
    ? t('components.sizeGb', { size: (mb / 1024).toFixed(1) })
    : t('components.sizeMb', { size: Math.round(mb) })
}

void refresh()
</script>

<template>
  <div class="components-view">
    <TopBar :title="t('components.title')" />

    <div class="components-content">
      <section class="components-section">
        <header class="section-header">
          <p class="section-description">{{ t('components.description') }}</p>
          <span v-if="totalInstalledMb > 0" class="total-size">
            {{ t('components.totalOnDisk', { size: formatarTamanho(totalInstalledMb) }) }}
          </span>
        </header>

        <p v-if="loading" class="state-line">{{ t('components.loading') }}</p>

        <p v-else-if="loadError" class="state-line state-error">
          <TriangleAlert :size="15" />
          {{ loadError }}
          <button type="button" class="link-btn" @click="refresh()">
            {{ t('components.actions.retry') }}
          </button>
        </p>

        <ul v-else class="component-list">
          <li v-for="row in rows" :key="row.id" class="component-row">
            <div class="row-icon" :style="{ color: row.meta.tint }">
              <component :is="row.meta.icon" :size="18" />
            </div>

            <div class="row-main">
              <span class="row-label">{{ t(row.meta.labelKey) }}</span>
              <span class="row-state">
                <template v-if="row.install_state === 'installing'">
                  <Loader2 :size="13" class="spin" />
                  {{ t('components.state.installing') }}
                </template>
                <template v-else-if="row.install_state === 'update_available'">
                  {{ t('components.state.updateAvailable') }}
                  <span v-if="row.size_mb" class="row-size"
                    >· {{ formatarTamanho(row.size_mb) }}</span
                  >
                </template>
                <template v-else-if="row.install_state === 'installed'">
                  {{ t('components.state.installed') }}
                  <span v-if="row.size_mb" class="row-size"
                    >· {{ formatarTamanho(row.size_mb) }}</span
                  >
                </template>
                <template v-else>{{ t('components.state.notInstalled') }}</template>
              </span>
            </div>

            <div class="row-actions">
              <button
                v-if="row.install_state === 'not_installed'"
                type="button"
                class="row-btn"
                :disabled="busy[row.id]"
                @click="agir(row.id, 'install')"
              >
                <Download :size="14" />
                {{ t('components.actions.install') }}
              </button>

              <button
                v-if="row.install_state === 'update_available'"
                type="button"
                class="row-btn"
                :disabled="busy[row.id]"
                @click="agir(row.id, 'update')"
              >
                <RefreshCw :size="14" />
                {{ t('components.actions.update') }}
              </button>

              <button
                v-if="row.install_state === 'installed' || row.install_state === 'update_available'"
                type="button"
                class="row-btn row-btn-danger"
                :disabled="busy[row.id]"
                @click="pedirRemocao(row.id)"
              >
                <Trash2 :size="14" />
                {{
                  confirmingRemoval === row.id
                    ? t('components.actions.confirmRemove')
                    : t('components.actions.remove')
                }}
              </button>
            </div>

            <p v-if="itemError[row.id]" class="row-error">
              <TriangleAlert :size="14" />
              <span>{{ itemError[row.id] }}</span>
            </p>
          </li>
        </ul>
      </section>

      <p class="footnote">{{ t('components.footnote') }}</p>
    </div>
  </div>
</template>

<style scoped>
.components-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.components-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 860px;
  width: 100%;
}

.components-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* O titulo vem da TopBar; aqui fica so' a descricao. O cabecalho anterior
   repetia `components.title` e usava as classes de grupo da tela de
   Configuracoes, que sao `scoped` la' e nunca chegaram aqui -- o `.icon-chip`,
   esse sim global, esticava sozinho e virava uma barra. */
.section-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.section-description {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.total-size {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
}

.component-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.component-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-subtle, rgba(255, 255, 255, 0.06));
}

.component-row:last-child {
  border-bottom: none;
}

.row-icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: color-mix(in srgb, currentColor 12%, transparent);
}

.row-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.row-label {
  font-size: 13px;
  font-weight: 500;
}

.row-state {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--text-muted);
}

.row-size {
  color: var(--text-muted);
}

.row-actions {
  display: flex;
  gap: 6px;
}

.row-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 10px;
  font-size: 12px;
  border-radius: 6px;
  border: 1px solid var(--border, rgba(255, 255, 255, 0.12));
  background: transparent;
  color: inherit;
  cursor: pointer;
}

.row-btn:hover:not(:disabled) {
  background: var(--surface-hover, rgba(255, 255, 255, 0.06));
}

.row-btn:disabled {
  opacity: 0.5;
  cursor: default;
}

.row-btn-danger:hover:not(:disabled) {
  color: #ef4444;
  border-color: #ef4444;
}

/* O erro ocupa a linha inteira da grade: a saída de pip é longa e espremê-la
   numa coluna a tornaria ilegível justamente quando mais importa. */
.row-error {
  grid-column: 1 / -1;
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin: 4px 0 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: color-mix(in srgb, #ef4444 10%, transparent);
  color: #ef4444;
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.state-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 8px 0;
  font-size: 13px;
  color: var(--text-muted);
}

.state-error {
  color: #ef4444;
}

.link-btn {
  background: none;
  border: none;
  padding: 0;
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
  font-size: inherit;
}

.footnote {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spin {
    animation: none;
  }
}
</style>
