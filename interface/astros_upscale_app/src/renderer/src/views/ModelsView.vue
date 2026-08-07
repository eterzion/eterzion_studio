<script setup lang="ts">
import { computed, onMounted, ref, type Component } from 'vue'
import {
  Search,
  ExternalLink,
  TriangleAlert,
  Check,
  Cpu,
  Star,
  User,
  Tag,
  Layers,
  Shield,
  Globe,
  UserPlus,
  Lock,
  Link2,
  Calendar,
  Settings2,
  Sparkles,
  Zap,
  X as XIcon,
  Minus
} from '@lucide/vue'
import TopBar from '../components/TopBar.vue'
import LicenseBadge from '../components/LicenseBadge.vue'
import { getModels, type ModelInfo } from '../backend'
import { getModelLicense, type CommercialUse } from '../data/modelLicenses'
import { modelConfigState, saveDefaultModel, type SavedModelConfig } from '../store/modelConfig'
import { settingsState } from '../store/settings'

const models = ref<ModelInfo[]>([])
const defaultModelName = ref<string | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)
const search = ref('')
const selectedId = ref<string | null>(null)

type FilterKey =
  'all' | 'commercial' | 'not_commercial' | 'restricted' | 'recommended' | 'downloaded'
const activeFilter = ref<FilterKey>('all')
const filters: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'Todos' },
  { key: 'commercial', label: 'Comercial' },
  { key: 'not_commercial', label: 'Não comercial' },
  { key: 'restricted', label: 'Com restrições' },
  { key: 'recommended', label: 'Recomendados' },
  { key: 'downloaded', label: 'Já baixados' }
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
    case 'downloaded':
      return m.downloaded
    default:
      return true
  }
}

function formatBytes(bytes: number | null): string {
  if (bytes === null) return '—'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
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
const selectedLicense = computed(() =>
  selectedId.value ? getModelLicense(selectedId.value) : undefined
)
const isCurrentDefault = computed(() => modelConfigState.saved?.modelId === selectedId.value)
const isRecommended = computed(() => selectedId.value === defaultModelName.value)

/** Modification/redistribution read as permission grants (green/red); attribution
 * reads as an obligation when true (amber "Obrigatória"), not a green grant —
 * "allowed to require credit" isn't the same shape of fact as "allowed to modify". */
interface PermissionBadge {
  icon: Component
  label: string
  tone: 'success' | 'warning' | 'danger' | 'neutral'
}

function permissionBadge(
  value: boolean | 'unverified' | undefined,
  kind: 'grant' | 'obligation' = 'grant'
): PermissionBadge {
  if (value === true) {
    return kind === 'obligation'
      ? { icon: TriangleAlert, label: 'Obrigatória', tone: 'warning' }
      : { icon: Check, label: 'Permitido', tone: 'success' }
  }
  if (value === false) {
    return kind === 'obligation'
      ? { icon: Minus, label: 'Não exigida', tone: 'neutral' }
      : { icon: XIcon, label: 'Não permitido', tone: 'danger' }
  }
  return { icon: Minus, label: 'Não informado', tone: 'neutral' }
}

const modelInitial = computed(() => (selectedModel.value?.name?.[0] ?? '?').toUpperCase())

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
        Escolha o modelo padrão de upscale. Uso comercial é sempre indicado por status — nunca pelo
        nome técnico da licença — e vem de fontes oficiais (repositório, documentação ou model
        card).
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
          <input
            v-model="search"
            type="text"
            placeholder="Buscar por nome, organização ou finalidade…"
          />
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
              <p v-if="settingsState.showModelDescriptions" class="model-card-line2">
                {{ m.description }}
              </p>
              <div class="model-card-line3">
                <LicenseBadge
                  v-if="settingsState.showCommercialBadges && getModelLicense(m.name)"
                  :commercial-use="getModelLicense(m.name)!.commercialUse"
                  compact
                />
                <span v-if="m.name === defaultModelName" class="recommended-chip"
                  ><Star :size="10" /> Recomendado</span
                >
              </div>
              <div class="model-card-line4">
                <span>{{ m.category }}</span>
                <span>·</span>
                <span>Escala nativa {{ m.scale }}x</span>
                <span v-if="m.downloaded" class="downloaded-chip">· Baixado</span>
              </div>
            </button>
          </template>
          <p v-if="!filtered.length" class="empty-text">
            Nenhum modelo encontrado para esse filtro/busca.
          </p>
        </div>

        <aside v-if="selectedModel" class="detail-panel">
          <div class="detail-hero">
            <div class="detail-avatar" aria-hidden="true">{{ modelInitial }}</div>
            <div class="detail-hero-text">
              <h2>{{ selectedModel.name }}</h2>
              <p class="detail-subtitle">
                {{ selectedModel.category }} · nativa {{ selectedModel.scale }}x
                <span v-if="isRecommended" class="recommended-chip"
                  ><Star :size="10" /> Recomendado</span
                >
              </p>
              <div class="detail-tag-row">
                <span class="detail-tag"><Sparkles :size="11" /> {{ selectedModel.category }}</span>
                <span class="detail-tag"
                  ><Zap :size="11" /> {{ selectedModel.scale }}x Upscale</span
                >
              </div>
            </div>
            <LicenseBadge
              v-if="settingsState.showCommercialBadges && selectedLicense"
              class="detail-hero-badge"
              :commercial-use="selectedLicense.commercialUse"
            />
          </div>

          <div class="detail-rows">
            <div class="detail-row">
              <div class="detail-row-icon"><User :size="15" /></div>
              <div class="detail-row-body">
                <span class="detail-row-label">Organização</span>
                <span class="detail-row-value">{{ selectedLicense?.developer ?? '—' }}</span>
              </div>
            </div>

            <div class="detail-row">
              <div class="detail-row-icon"><Tag :size="15" /></div>
              <div class="detail-row-body">
                <span class="detail-row-label">Versão</span>
                <span class="detail-row-value">
                  {{ selectedModel.name }}
                  <span class="detail-note">(arquivo fixado por hash SHA-256)</span>
                </span>
              </div>
            </div>

            <div v-if="settingsState.showModelDescriptions" class="detail-row">
              <div class="detail-row-icon"><Sparkles :size="15" /></div>
              <div class="detail-row-body">
                <span class="detail-row-label">Finalidade</span>
                <span class="detail-row-value">{{ selectedModel.description }}</span>
              </div>
            </div>

            <div class="detail-row">
              <div class="detail-row-icon"><Layers :size="15" /></div>
              <div class="detail-row-body">
                <span class="detail-row-label">Categoria e escala</span>
                <span class="detail-row-value"
                  >{{ selectedModel.category }} · nativa {{ selectedModel.scale }}x</span
                >
              </div>
            </div>

            <div v-if="selectedModel.architecture" class="detail-row">
              <div class="detail-row-icon"><Settings2 :size="15" /></div>
              <div class="detail-row-body">
                <span class="detail-row-label">Arquitetura</span>
                <span class="detail-row-value">
                  {{ selectedModel.architecture }}
                  <span class="detail-note"
                    >(conforme documentado pelo repositório/model card oficial)</span
                  >
                </span>
              </div>
            </div>

            <div class="detail-row">
              <div class="detail-row-icon"><Cpu :size="15" /></div>
              <div class="detail-row-body">
                <span class="detail-row-label">Compatibilidade de execução</span>
                <span class="detail-row-value"
                  >CPU e GPU (via PyTorch/spandrel — sem restrição de hardware)</span
                >
              </div>
            </div>

            <div class="detail-row">
              <div class="detail-row-icon"><Layers :size="15" /></div>
              <div class="detail-row-body">
                <span class="detail-row-label">Arquivo do modelo</span>
                <span class="detail-row-value">
                  <template v-if="selectedModel.downloaded">
                    {{ formatBytes(selectedModel.size_bytes) }}
                    <span class="detail-note"
                      >baixado localmente ({{ selectedModel.file_count }} arquivo{{
                        selectedModel.file_count > 1 ? 's' : ''
                      }})</span
                    >
                  </template>
                  <template v-else>
                    <span class="detail-note"
                      >Ainda não baixado — baixado sob demanda no primeiro uso ({{
                        selectedModel.file_count
                      }}
                      arquivo{{ selectedModel.file_count > 1 ? 's' : '' }})</span
                    >
                  </template>
                </span>
              </div>
            </div>

            <div class="detail-row">
              <div class="detail-row-icon"><Shield :size="15" /></div>
              <div class="detail-row-body">
                <span class="detail-row-label">Modificação</span>
                <span
                  class="perm-badge"
                  :class="'tone-' + permissionBadge(selectedLicense?.modificationAllowed).tone"
                >
                  <component
                    :is="permissionBadge(selectedLicense?.modificationAllowed).icon"
                    :size="12"
                  />
                  {{ permissionBadge(selectedLicense?.modificationAllowed).label }}
                </span>
              </div>
            </div>

            <div class="detail-row">
              <div class="detail-row-icon"><Globe :size="15" /></div>
              <div class="detail-row-body">
                <span class="detail-row-label">Redistribuição</span>
                <span
                  class="perm-badge"
                  :class="'tone-' + permissionBadge(selectedLicense?.redistributionAllowed).tone"
                >
                  <component
                    :is="permissionBadge(selectedLicense?.redistributionAllowed).icon"
                    :size="12"
                  />
                  {{ permissionBadge(selectedLicense?.redistributionAllowed).label }}
                </span>
              </div>
            </div>

            <div class="detail-row">
              <div class="detail-row-icon"><UserPlus :size="15" /></div>
              <div class="detail-row-body">
                <span class="detail-row-label">Atribuição</span>
                <span
                  class="perm-badge"
                  :class="
                    'tone-' +
                    permissionBadge(selectedLicense?.attributionRequired, 'obligation').tone
                  "
                >
                  <component
                    :is="permissionBadge(selectedLicense?.attributionRequired, 'obligation').icon"
                    :size="12"
                  />
                  {{ permissionBadge(selectedLicense?.attributionRequired, 'obligation').label }}
                </span>
              </div>
            </div>

            <div v-if="selectedLicense?.restrictions.length" class="detail-row">
              <div class="detail-row-icon"><Lock :size="15" /></div>
              <div class="detail-row-body">
                <span class="detail-row-label">Restrições</span>
                <ul class="detail-inner-card restriction-list">
                  <li v-for="(r, i) in selectedLicense.restrictions" :key="i">{{ r }}</li>
                </ul>
              </div>
            </div>

            <div class="detail-row">
              <div class="detail-row-icon"><Link2 :size="15" /></div>
              <div class="detail-row-body">
                <span class="detail-row-label">Fonte consultada</span>
                <a
                  :href="selectedLicense?.sourceUrl"
                  target="_blank"
                  rel="noreferrer"
                  class="source-link"
                >
                  {{ selectedLicense?.sourceUrl }} <ExternalLink :size="12" />
                </a>
              </div>
            </div>

            <div class="detail-row">
              <div class="detail-row-icon"><Calendar :size="15" /></div>
              <div class="detail-row-body">
                <span class="detail-row-label">Última verificação</span>
                <span class="detail-row-value">{{ selectedLicense?.verifiedAt ?? '—' }}</span>
              </div>
            </div>
          </div>

          <p v-if="selectedLicense?.needsManualReview" class="review-warning">
            <TriangleAlert :size="14" /> {{ selectedLicense.needsManualReview }}
          </p>
          <p v-if="selectedLicense?.commercialUse === 'unverified'" class="review-warning">
            <TriangleAlert :size="14" /> Status de uso comercial não confirmado em fonte oficial —
            não use em produção comercial sem validar manualmente.
          </p>

          <button class="save-btn" type="button" :disabled="isCurrentDefault" @click="save">
            <Settings2 :size="16" />
            {{ isCurrentDefault ? 'Já é o modelo padrão' : 'Definir como modelo padrão' }}
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
  transition:
    background var(--transition-fast),
    color var(--transition-fast),
    border-color var(--transition-fast);
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
  background: linear-gradient(
    90deg,
    var(--surface-2) 25%,
    var(--surface-3) 37%,
    var(--surface-2) 63%
  );
  background-size: 400% 100%;
  animation: skeleton-shimmer 1.4s ease infinite;
}

.skeleton-detail {
  height: 480px;
  border-radius: var(--radius-lg);
  background: linear-gradient(
    90deg,
    var(--surface-2) 25%,
    var(--surface-3) 37%,
    var(--surface-2) 63%
  );
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
  transition:
    background var(--transition-fast),
    border-color var(--transition-fast),
    box-shadow var(--transition-fast);
}

.model-card:hover {
  background: var(--surface-3);
  box-shadow: var(--shadow-sm);
  transform: scale(1.01);
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
  flex-wrap: wrap;
  gap: 4px;
  font-size: 11px;
  color: var(--text-tertiary);
}

.downloaded-chip {
  color: var(--color-success);
  font-weight: var(--fw-medium);
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
  background: linear-gradient(180deg, var(--surface-1) 0%, var(--surface-2) 140%);
  border: 1px solid var(--surface-border);
  border-radius: 22px;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-height: calc(100vh - 260px);
  overflow-y: auto;
  box-shadow: var(--shadow-md);
  animation: detail-fade-in 220ms ease;
}

@keyframes detail-fade-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.detail-hero {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: var(--space-3);
}

.detail-avatar {
  flex-shrink: 0;
  width: 64px;
  height: 64px;
  border-radius: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  font-weight: var(--fw-semibold);
  color: #fff;
  background: linear-gradient(135deg, var(--color-primary), #0891b2);
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.08) inset,
    0 8px 20px -6px var(--color-primary-soft);
}

.detail-hero-text {
  flex: 1;
  min-width: 140px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.detail-hero-text h2 {
  font-size: 30px;
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  overflow-wrap: break-word;
  line-height: 1.15;
}

.detail-subtitle {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: var(--fs-label);
  color: var(--text-secondary);
}

.detail-tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 2px;
}

.detail-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: var(--fw-medium);
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 999px;
  padding: 3px 9px;
}

.detail-hero-badge {
  flex-shrink: 0;
}

.detail-rows {
  display: flex;
  flex-direction: column;
}

.detail-row {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--surface-border-soft);
  transition: background var(--transition-fast);
}

.detail-row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.detail-row:hover {
  background: rgba(255, 255, 255, 0.015);
}

.detail-row-icon {
  flex-shrink: 0;
  width: 34px;
  height: 34px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  background: var(--surface-3);
  border: 1px solid var(--surface-border-soft);
}

.detail-row-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-row-label {
  font-size: 11px;
  font-weight: var(--fw-semibold);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-tertiary);
}

.detail-row-value {
  font-size: var(--fs-value);
  font-weight: var(--fw-medium);
  color: var(--text-primary);
  overflow-wrap: break-word;
  word-break: break-word;
}

.detail-note {
  color: var(--text-tertiary);
  font-weight: var(--fw-regular);
  font-size: var(--fs-caption);
}

.detail-inner-card {
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-md);
  padding: var(--space-2) var(--space-3);
  font-size: var(--fs-caption);
  color: var(--text-secondary);
}

.restriction-list {
  padding-left: 16px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  list-style: disc;
}

.perm-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  width: fit-content;
  font-size: 12px;
  font-weight: var(--fw-semibold);
  border-radius: 999px;
  padding: 3px 10px;
  transition: transform var(--transition-fast);
}

.perm-badge:hover {
  transform: scale(1.03);
}

.perm-badge.tone-success {
  color: var(--color-success);
  background: var(--color-success-soft);
}

.perm-badge.tone-danger {
  color: var(--color-danger);
  background: var(--color-danger-soft);
}

.perm-badge.tone-warning {
  color: var(--color-warning);
  background: var(--color-warning-soft);
}

.perm-badge.tone-neutral {
  color: var(--text-tertiary);
  background: var(--surface-3);
}

.source-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
  color: var(--color-primary);
  overflow-wrap: anywhere;
  word-break: break-all;
  transition: color var(--transition-fast);
}

.source-link:hover {
  color: var(--color-primary-hover);
  text-decoration: underline;
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
  width: 100%;
  background: linear-gradient(135deg, var(--color-primary), #0891b2);
  color: #fff;
  border: none;
  border-radius: var(--radius-md);
  padding: 14px;
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  cursor: pointer;
  box-shadow: 0 6px 18px -6px var(--color-primary-soft);
  transition:
    transform var(--transition-fast),
    box-shadow var(--transition-fast),
    filter var(--transition-fast);
}

.save-btn:hover:not(:disabled) {
  filter: brightness(1.08);
  box-shadow: 0 8px 22px -4px var(--color-primary-soft);
  transform: translateY(-1px);
}

.save-btn:active:not(:disabled) {
  transform: translateY(0) scale(0.99);
}

.save-btn:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.save-btn:disabled {
  background: var(--surface-3);
  color: var(--text-tertiary);
  box-shadow: none;
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
