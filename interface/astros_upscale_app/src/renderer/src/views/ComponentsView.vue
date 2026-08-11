<script setup lang="ts">
import { onMounted, ref } from 'vue'
import TopBar from '../components/TopBar.vue'
import {
  Download,
  RefreshCw,
  Trash2,
  Info,
  Loader2,
  AlertCircle
} from '@lucide/vue'
import {
  listComponents,
  getComponentDetails,
  installComponent,
  updateComponent,
  deleteComponent,
  type ComponentSummary,
  type ComponentDetails
} from '../backend'

// T069/T070 — replaces ModelsView.vue. Capability-first, install/update/
// remove only (FR-064, no selection affordance) — technical_name/version/
// provenance/license only ever appear in the opt-in details panel
// (FR-065/FR-066), never in the main list (FR-009/FR-063).
const components = ref<ComponentSummary[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)
const busyId = ref<string | null>(null)
const actionError = ref<string | null>(null)
const expandedId = ref<string | null>(null)
const details = ref<Record<string, ComponentDetails>>({})
const detailsLoading = ref<string | null>(null)

async function refresh(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    components.value = await listComponents()
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : 'Falha ao carregar componentes.'
  } finally {
    loading.value = false
  }
}

onMounted(refresh)

async function toggleDetails(component: ComponentSummary): Promise<void> {
  if (expandedId.value === component.id) {
    expandedId.value = null
    return
  }
  expandedId.value = component.id
  if (details.value[component.id]) return
  detailsLoading.value = component.id
  try {
    details.value[component.id] = await getComponentDetails(component.id)
  } catch {
    // Details are opt-in extra info — a failure here just leaves the panel
    // without them, it doesn't block install/update/remove.
  } finally {
    detailsLoading.value = null
  }
}

async function runAction(component: ComponentSummary, action: 'install' | 'update' | 'delete'): Promise<void> {
  busyId.value = component.id
  actionError.value = null
  try {
    const fn = action === 'install' ? installComponent : action === 'update' ? updateComponent : deleteComponent
    const updated = await fn(component.id)
    const index = components.value.findIndex((c) => c.id === component.id)
    if (index !== -1) components.value[index] = updated
    delete details.value[component.id] // stale after a state change — refetch on next expand
  } catch (error) {
    actionError.value = error instanceof Error ? error.message : 'Falha na operação.'
  } finally {
    busyId.value = null
  }
}

function stateLabel(state: ComponentSummary['install_state']): string {
  return (
    { not_installed: 'Não instalado', installing: 'Instalando…', installed: 'Instalado', update_available: 'Atualização disponível' }[
      state
    ] ?? state
  )
}
</script>

<template>
  <div class="components-view">
    <TopBar title="Componentes">
      <template #actions>
        <button class="btn-outline" type="button" @click="refresh">
          <RefreshCw :size="15" /> Atualizar
        </button>
      </template>
    </TopBar>

    <div class="components-content">
      <p class="hint">
        Cada capacidade tem exatamente uma implementação instalável — instale, atualize ou remova;
        não há escolha de modelo (FR-063/FR-064).
      </p>
      <p v-if="loadError" class="banner-error"><AlertCircle :size="14" /> {{ loadError }}</p>
      <p v-if="actionError" class="banner-error"><AlertCircle :size="14" /> {{ actionError }}</p>

      <div v-if="loading" class="status-row">
        <Loader2 :size="18" class="spin" /> Carregando…
      </div>

      <div v-else class="component-list">
        <div v-for="component in components" :key="component.id" class="component-card">
          <div class="component-row">
            <div class="component-main">
              <span class="capability-label">{{ component.capability_label }}</span>
              <span class="install-state" :class="component.install_state">{{ stateLabel(component.install_state) }}</span>
              <span v-if="component.size_mb > 0" class="size">{{ component.size_mb }} MB</span>
            </div>
            <div class="component-actions">
              <button
                class="icon-btn"
                type="button"
                title="Detalhes técnicos"
                @click="toggleDetails(component)"
              >
                <Info :size="16" />
              </button>
              <button
                v-if="component.install_state === 'not_installed'"
                class="btn-outline small"
                type="button"
                :disabled="busyId === component.id"
                @click="runAction(component, 'install')"
              >
                <Download :size="14" /> Instalar
              </button>
              <button
                v-if="component.install_state === 'update_available'"
                class="btn-outline small"
                type="button"
                :disabled="busyId === component.id"
                @click="runAction(component, 'update')"
              >
                <RefreshCw :size="14" /> Atualizar
              </button>
              <button
                v-if="component.install_state === 'installed' || component.install_state === 'update_available'"
                class="btn-outline small danger"
                type="button"
                :disabled="busyId === component.id"
                @click="runAction(component, 'delete')"
              >
                <Trash2 :size="14" /> Remover
              </button>
              <Loader2 v-if="busyId === component.id" :size="16" class="spin" />
            </div>
          </div>

          <div v-if="expandedId === component.id" class="details-panel">
            <Loader2 v-if="detailsLoading === component.id" :size="16" class="spin" />
            <dl v-else-if="details[component.id]" class="details-grid">
              <dt>Nome técnico</dt>
              <dd>{{ details[component.id].technical_name }}</dd>
              <dt>Versão</dt>
              <dd>{{ details[component.id].version }}</dd>
              <dt>Origem</dt>
              <dd class="provenance">{{ details[component.id].provenance }}</dd>
              <dt>Licença</dt>
              <dd>{{ details[component.id].license }}</dd>
            </dl>
            <p v-else class="hint">Não foi possível carregar os detalhes técnicos.</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.components-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  flex: 1;
  min-width: 0;
}
.components-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.hint {
  color: var(--text-secondary);
  font-size: var(--fs-body-sm);
}
.banner-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-danger);
  font-size: var(--fs-body-sm);
}
.status-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-secondary);
}
.component-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.component-card {
  background: var(--surface-1);
  border: 1px solid var(--border-1);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.component-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.component-main {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.capability-label {
  font-weight: 600;
  font-size: var(--fs-label);
}
.install-state {
  font-size: var(--fs-caption);
  color: var(--text-secondary);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  background: var(--surface-2);
}
.install-state.installed {
  color: var(--color-success, var(--text-primary));
}
.install-state.update_available {
  color: var(--color-warning, var(--text-primary));
}
.size {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
}
.component-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.btn-outline.small {
  padding: 4px 10px;
  font-size: var(--fs-body-sm);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.btn-outline.small.danger {
  color: var(--color-danger);
  border-color: var(--color-danger);
}
.details-panel {
  border-top: 1px solid var(--border-1);
  padding-top: var(--space-2);
}
.details-grid {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: var(--space-1) var(--space-3);
  margin: 0;
  font-size: var(--fs-body-sm);
}
.details-grid dt {
  color: var(--text-secondary);
}
.details-grid dd {
  margin: 0;
  color: var(--text-primary);
}
.provenance {
  word-break: break-all;
}
.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
