<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Search, ExternalLink, TriangleAlert, Check, Cpu, Star } from '@lucide/vue'
import TopBar from '../components/TopBar.vue'
import LicenseBadge from '../components/LicenseBadge.vue'
import { getModels, type ModelInfo } from '../backend'
import { getModelLicense, type CommercialUse } from '../data/modelLicenses'
import { modelConfigState, saveDefaultModel, type SavedModelConfig } from '../store/modelConfig'

const models = ref<ModelInfo[]>([])
const defaultModelName = ref<string | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)
const search = ref('')
const selectedId = ref<string | null>(null)

type FilterKey = 'all' | 'commercial' | 'not_commercial' | 'restricted' | 'recommended'
const activeFilter = ref<FilterKey>('all')
const filters: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'Todos' },
  { key: 'commercial', label: 'Comercial' },
  { key: 'not_commercial', label: 'Não comercial' },
  { key: 'restricted', label: 'Com restrições' },
  { key: 'recommended', label: 'Recomendados' }
]

onMounted(async () => {
  try {
    const registry = await getModels()
    models.value = registry.models
    defaultModelName.value = registry.default_image_model
    selectedId.value = modelConfigState.saved?.modelId ?? registry.models[0]?.name ?? null
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : 'Falha ao carregar modelos da API.'
  } finally {
    loading.value = false
  }
})

function matchesFilter(m: ModelInfo): boolean {
  const license = getModelLicense(m.name)
  const commercial: CommercialUse = license?.commercialUse ?? 'unverified'
  switch (activeFilter.value) {
    case 'commercial':
      return commercial === 'allowed'
    case 'not_commercial':
      return commercial === 'not_allowed'
    case 'restricted':
      return commercial === 'restricted' || commercial === 'unverified'
    case 'recommended':
      return m.name === defaultModelName.value
    default:
      return true
  }
}

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  return models.value.filter((m) => {
    if (!matchesFilter(m)) return false
    if (!q) return true
    const license = getModelLicense(m.name)
    return (
      m.name.toLowerCase().includes(q) ||
      m.description.toLowerCase().includes(q) ||
      m.category.toLowerCase().includes(q) ||
      (license?.developer.toLowerCase().includes(q) ?? false)
    )
  })
})

const grouped = computed(() => {
  const groups = new Map<string, ModelInfo[]>()
  for (const m of filtered.value) {
    if (!groups.has(m.category)) groups.set(m.category, [])
    groups.get(m.category)!.push(m)
  }
  return groups
})

const selectedModel = computed(() => models.value.find((m) => m.name === selectedId.value))
const selectedLicense = computed(() => (selectedId.value ? getModelLicense(selectedId.value) : undefined))
const isCurrentDefault = computed(() => modelConfigState.saved?.modelId === selectedId.value)
const isRecommended = computed(() => selectedId.value === defaultModelName.value)

function permissionLabel(value: boolean | 'unverified' | undefined): string {
  if (value === true) return 'Sim'
  if (value === false) return 'Não'
  return 'Não verificado'
}

function save(): void {
  const model = selectedModel.value
  const license = selectedLicense.value
  if (!model || !license) return
  const config: SavedModelConfig = {
    modelId: model.name,
    modelName: model.name,
    modelVersion: model.name, // registry pins an exact weight file per name (sha256-checked) — no separate version string
    developer: license.developer,
    license: license.license,
    commercialUse: license.commercialUse,
    modificationAllowed: license.modificationAllowed,
    redistributionAllowed: license.redistributionAllowed,
    attributionRequired: license.attributionRequired,
    restrictions: license.restrictions,
    licenseSourceUrl: license.sourceUrl,
    licenseSourceKind: license.sourceKind,
    verifiedAt: license.verifiedAt,
    savedAt: new Date().toISOString()
  }
  saveDefaultModel(config)
}
</script>

<template>
  <div class="models-view">
    <TopBar title="Modelos" />

    <div class="models-content">
      <p class="page-hint">
        Escolha o modelo padrão de upscale. Uso comercial é sempre indicado por status — nunca pelo nome técnico da
        licença — e vem de fontes oficiais (repositório, documentação ou model card).
      </p>

      <div v-if="modelConfigState.saved" class="current-default">
        <Check :size="14" />
        <span>
          Padrão atual: <strong>{{ modelConfigState.saved.modelName }}</strong>
        </span>
        <LicenseBadge :commercial-use="modelConfigState.saved.commercialUse" compact />
      </div>

      <div class="toolbar">
        <div class="search-bar">
          <Search :size="16" />
          <input v-model="search" type="text" placeholder="Buscar por nome, organização ou finalidade…" />
        </div>

        <div class="filter-row" role="tablist" aria-label="Filtrar modelos">
          <button
            v-for="f in filters"
            :key="f.key"
            class="filter-chip"
            :class="{ active: activeFilter === f.key }"
            type="button"
            role="tab"
            :aria-selected="activeFilter === f.key"
            @click="activeFilter = f.key"
          >
            {{ f.label }}
          </button>
        </div>
      </div>

      <p v-if="loadError" class="banner-error"><TriangleAlert :size="14" /> {{ loadError }}</p>

      <div v-if="loading" class="models-layout">
        <div class="models-list">
          <div v-for="i in 6" :key="i" class="skeleton-card" aria-hidden="true" />
        </div>
        <div class="skeleton-detail" aria-hidden="true" />
      </div>

      <div v-else class="models-layout">
        <div class="models-list" role="listbox" aria-label="Lista de modelos">
          <template v-for="[category, list] in grouped" :key="category">
            <h3 class="category-title">{{ category }}</h3>
            <button
              v-for="m in list"
              :key="m.name"
              class="model-card"
              :class="{ active: m.name === selectedId }"
              type="button"
              role="option"
              :aria-selected="m.name === selectedId"
              @click="selectedId = m.name"
            >
              <div class="model-card-line1">
                <span class="model-name">{{ m.name }}</span>
                <span class="model-version">v.{{ m.scale }}x</span>
              </div>
              <p class="model-card-line2">{{ m.description }}</p>
              <div class="model-card-line3">
                <LicenseBadge
                  v-if="getModelLicense(m.name)"
                  :commercial-use="getModelLicense(m.name)!.commercialUse"
                  compact
                />
                <span v-if="m.name === defaultModelName" class="recommended-chip"><Star :size="10" /> Recomendado</span>
              </div>
              <div class="model-card-line4">
                <span>{{ m.category }}</span>
                <span>·</span>
                <span>Escala nativa {{ m.scale }}x</span>
              </div>
            </button>
          </template>
          <p v-if="!filtered.length" class="empty-text">Nenhum modelo encontrado para esse filtro/busca.</p>
        </div>

        <aside v-if="selectedModel" class="detail-panel">
          <div class="detail-header">
            <div>
              <h2>{{ selectedModel.name }}</h2>
              <span v-if="isRecommended" class="recommended-chip"><Star :size="10" /> Recomendado</span>
            </div>
            <LicenseBadge v-if="selectedLicense" :commercial-use="selectedLicense.commercialUse" />
          </div>

          <dl class="detail-grid">
            <div class="detail-row">
              <dt>Organização</dt>
              <dd>{{ selectedLicense?.developer ?? '—' }}</dd>
            </div>
            <div class="detail-row">
              <dt>Versão</dt>
              <dd>{{ selectedModel.name }} <span class="detail-note">(arquivo fixado por hash SHA-256)</span></dd>
            </div>
            <div class="detail-row">
              <dt>Finalidade</dt>
              <dd>{{ selectedModel.description }}</dd>
            </div>
            <div class="detail-row">
              <dt>Categoria e escala</dt>
              <dd>{{ selectedModel.category }} · nativa {{ selectedModel.scale }}x</dd>
            </div>
            <div class="detail-row">
              <dt>Requisitos de hardware</dt>
              <dd>Não especificado pelo desenvolvedor na fonte oficial — não inferido.</dd>
            </div>
            <div class="detail-row">
              <dt>Modificação permitida</dt>
              <dd>{{ permissionLabel(selectedLicense?.modificationAllowed) }}</dd>
            </div>
            <div class="detail-row">
              <dt>Redistribuição permitida</dt>
              <dd>{{ permissionLabel(selectedLicense?.redistributionAllowed) }}</dd>
            </div>
            <div class="detail-row">
              <dt>Exige atribuição</dt>
              <dd>{{ permissionLabel(selectedLicense?.attributionRequired) }}</dd>
            </div>
            <div v-if="selectedLicense?.restrictions.length" class="detail-row">
              <dt>Restrições</dt>
              <dd>
                <ul class="restriction-list">
                  <li v-for="(r, i) in selectedLicense.restrictions" :key="i">{{ r }}</li>
                </ul>
              </dd>
            </div>
            <div class="detail-row">
              <dt>Fonte consultada</dt>
              <dd>
                <a :href="selectedLicense?.sourceUrl" target="_blank" rel="noreferrer" class="source-link">
                  {{ selectedLicense?.sourceUrl }} <ExternalLink :size="12" />
                </a>
              </dd>
            </div>
            <div class="detail-row">
              <dt>Última verificação</dt>
              <dd>{{ selectedLicense?.verifiedAt ?? '—' }}</dd>
            </div>
          </dl>

          <p v-if="selectedLicense?.needsManualReview" class="review-warning">
            <TriangleAlert :size="14" /> {{ selectedLicense.needsManualReview }}
          </p>
          <p v-if="selectedLicense?.commercialUse === 'unverified'" class="review-warning">
            <TriangleAlert :size="14" /> Status de uso comercial não confirmado em fonte oficial — não use em
            produção comercial sem validar manualmente.
          </p>

          <button class="save-btn" type="button" :disabled="isCurrentDefault" @click="save">
            <Cpu :size="15" /> {{ isCurrentDefault ? 'Já é o modelo padrão' : 'Definir como modelo padrão' }}
          </button>
        </aside>
      </div>
    </div>
  </div>
</template>

<style scoped>
.models-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  flex: 1;
  min-width: 0;
}

.models-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.page-hint {
  font-size: var(--fs-caption);
  color: var(--text-secondary);
  max-width: 720px;
}

.current-default {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--fs-caption);
  color: var(--color-success);
  background: var(--color-success-soft);
  border: 1px solid var(--color-success);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  width: fit-content;
}

.toolbar {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.search-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface-2);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  color: var(--text-tertiary);
  max-width: 420px;
  transition: border-color var(--transition-fast);
}

.search-bar:focus-within {
  border-color: var(--color-primary);
}

.search-bar input {
  flex: 1;
  min-width: 0;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: var(--fs-label);
}

.search-bar input:focus {
  outline: none;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.filter-chip {
  border: 1px solid var(--surface-border);
  background: var(--surface-2);
  color: var(--text-secondary);
  border-radius: 999px;
  padding: 6px 14px;
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast);
}

.filter-chip:hover {
  background: var(--surface-3);
}

.filter-chip.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
  border-color: var(--color-primary);
}

.filter-chip:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}

.banner-error {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-danger);
  font-size: var(--fs-caption);
}

.models-layout {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: var(--space-4);
  align-items: start;
  min-height: 0;
}

.models-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: calc(100vh - 260px);
  overflow-y: auto;
  padding-right: 4px;
}

.skeleton-card {
  height: 96px;
  border-radius: var(--radius-md);
  background: linear-gradient(90deg, var(--surface-2) 25%, var(--surface-3) 37%, var(--surface-2) 63%);
  background-size: 400% 100%;
  animation: skeleton-shimmer 1.4s ease infinite;
}

.skeleton-detail {
  height: 480px;
  border-radius: var(--radius-lg);
  background: linear-gradient(90deg, var(--surface-2) 25%, var(--surface-3) 37%, var(--surface-2) 63%);
  background-size: 400% 100%;
  animation: skeleton-shimmer 1.4s ease infinite;
}

@keyframes skeleton-shimmer {
  0% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0 50%;
  }
}

.category-title {
  font-size: 11px;
  font-weight: var(--fw-semibold);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-tertiary);
  margin-top: var(--space-2);
}

.category-title:first-child {
  margin-top: 0;
}

.model-card {
  display: flex;
  flex-direction: column;
  gap: 5px;
  text-align: left;
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  cursor: pointer;
  transition: background var(--transition-fast), border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.model-card:hover {
  background: var(--surface-3);
  box-shadow: var(--shadow-sm);
}

.model-card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}

.model-card.active {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  box-shadow: var(--shadow-sm);
}

.model-card-line1 {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
}

.model-name {
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-version {
  font-size: 11px;
  font-weight: var(--fw-semibold);
  color: var(--text-tertiary);
  flex-shrink: 0;
  font-family: var(--font-mono);
}

.model-card-line2 {
  font-size: var(--fs-caption);
  color: var(--text-secondary);
  overflow-wrap: break-word;
}

.model-card-line3 {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.model-card-line4 {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-tertiary);
}

.recommended-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  font-weight: var(--fw-semibold);
  color: #a78bfa;
  background: rgba(167, 139, 250, 0.14);
  border: 1px solid rgba(167, 139, 250, 0.4);
  padding: 2px 7px;
  border-radius: 999px;
}

.empty-text {
  font-size: var(--fs-label);
  color: var(--text-tertiary);
  padding: var(--space-4);
  text-align: center;
}

.detail-panel {
  position: sticky;
  top: 0;
  background: var(--surface-1);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  max-height: calc(100vh - 260px);
  overflow-y: auto;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.detail-header h2 {
  font-size: var(--fs-page-title);
  color: var(--text-primary);
  overflow-wrap: break-word;
  min-width: 0;
}

.detail-grid {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.detail-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--surface-border-soft);
}

.detail-row dt {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--text-tertiary);
}

.detail-row dd {
  font-size: var(--fs-caption);
  color: var(--text-primary);
  overflow-wrap: break-word;
  word-break: break-word;
}

.detail-note {
  color: var(--text-tertiary);
}

.restriction-list {
  padding-left: 16px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.source-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--color-primary);
  overflow-wrap: anywhere;
  word-break: break-all;
}

.review-warning {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: var(--fs-caption);
  color: var(--color-warning);
  background: var(--color-warning-soft);
  border: 1px solid var(--color-warning);
  border-radius: var(--radius-sm);
  padding: var(--space-2);
}

.save-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  padding: 10px;
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.save-btn:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.save-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (max-width: 1000px) {
  .models-layout {
    grid-template-columns: 1fr;
  }

  .detail-panel {
    position: static;
    max-height: none;
  }

  .models-list {
    max-height: none;
  }
}
</style>
