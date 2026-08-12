<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Settings2,
  Cpu,
  History as HistoryIcon,
  LayoutGrid,
  Wrench,
  FolderOpen,
  Trash2,
  RotateCcw,
  Check,
  Award,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Info,
  ShieldCheck,
  Scale,
  Image as ImageIcon,
  Palette,
  Film,
  Video,
  AudioLines,
  Music2,
  Scan,
  PlayCircle
} from '@lucide/vue'
import TopBar from '../components/TopBar.vue'
import SettingRow from '../components/SettingRow.vue'
import SettingSwitch from '../components/SettingSwitch.vue'
import SegmentedControl from '../components/SegmentedControl.vue'
import AppSelect from '../components/AppSelect.vue'
import RangeSlider from '../components/RangeSlider.vue'
import { settingsState, setTheme, setAccentColor, setLanguage } from '../store/settings'
import { ACCENT_COLORS, type AccentColor } from '../theme'
import { SUPPORTED_LOCALES, detectSystemLocale, type SupportedLocale } from '../i18n'
import { clearHistory, historyState } from '../store/history'
import { listComponents } from '../backend'
import { api, hasNativeApi } from '../api'

const { t } = useI18n()

const detectedLocaleLabel = computed(
  () => SUPPORTED_LOCALES.find((l) => l.value === detectSystemLocale())?.label ?? ''
)
const languageOptions = computed(() => [
  { value: 'auto', label: `${t('settings.general.theme.auto')} (${detectedLocaleLabel.value})` },
  ...SUPPORTED_LOCALES.map((l) => ({ value: l.value as string, label: l.label }))
])

// T073/FR-045/SC-012 — real attribution for every component this build
// actually ships, sourced from docs/models/MODEL_LICENSES.md (the legal
// source of truth) and app/core/license_registry.py (its backend
// projection). Static here because it's a fixed disclosure obligation of
// already-approved licenses, not something the API resolves per request.
// `work` cites the actual published model/work being attributed (required by
// CC-BY-4.0/Apache-2.0 NOTICE terms) — never an internal routing identifier;
// `capability` is the same human-facing label used everywhere else in the
// product (FR-009/FR-063), always listed first.
// icon/tint are purely presentational (match the capability icons used
// elsewhere, e.g. ComponentsView.vue) — never derived from or exposing an
// internal engine_ref (FR-009/FR-063).
const CREDITS: {
  capability: string
  work: string
  author: string
  license: string
  note?: string
  icon: unknown
  tint: string
}[] = [
  {
    capability: 'Melhoria de imagem — Foto',
    work: '4xNomosWebPhoto_RealPLKSR',
    author: 'Philip Hofmann (Phhofm)',
    license: 'CC-BY-4.0',
    icon: ImageIcon,
    tint: '#3b82f6'
  },
  {
    capability: 'Melhoria de imagem — Anime/Ilustração',
    work: '2xHFA2kSPAN',
    author: 'Philip Hofmann (Phhofm)',
    license: 'CC-BY-4.0',
    icon: Palette,
    tint: '#a855f7'
  },
  {
    capability: 'Melhoria de vídeo — Anime/Animação',
    work: 'Real-ESRGAN (realesr-animevideov3)',
    author: 'Xintao Wang',
    license: 'BSD-3-Clause',
    icon: Film,
    tint: '#f59e0b'
  },
  {
    capability: 'Melhoria de vídeo — Filmagem real',
    work: '2xPublic_realplksr_dysample_layernorm_real',
    author: 'Philip Hofmann (Phhofm)',
    license: 'Apache-2.0',
    icon: Video,
    tint: '#ef4444'
  },
  {
    capability: 'Melhoria de áudio — Voz',
    work: 'audiosronnx',
    author: 'TigreGotico',
    license: 'Apache-2.0',
    icon: AudioLines,
    tint: '#14b8a6'
  },
  {
    capability: 'Melhoria de áudio — Música',
    work: 'SonicMaster',
    author: 'AMAAI Lab',
    license: 'Apache-2.0',
    note: 'Apache-2.0 — condicional (depende do VAE do Stable Audio Open, ver MODEL_LICENSES.md §3-bis)',
    icon: Music2,
    tint: '#ec4899'
  },
  {
    capability: 'Realce de rosto (imagem)',
    work: 'YuNet',
    author: 'OpenCV / libfacedetection',
    license: 'MIT',
    icon: Scan,
    tint: '#22c55e'
  },
  {
    capability: 'Processamento de mídia',
    work: 'FFmpeg',
    author: 'FFmpeg developers',
    license: 'LGPL v2.1+',
    note: '(build de distribuição)',
    icon: PlayCircle,
    tint: '#3b82f6'
  }
]

const LICENSE_TONES: Record<string, string> = {
  'CC-BY-4.0': '#3b82f6',
  'BSD-3-Clause': '#a855f7',
  'Apache-2.0': '#22c55e',
  MIT: '#94a3b8',
  'LGPL v2.1+': '#94a3b8'
}
function licenseTone(license: string): string {
  return LICENSE_TONES[license] ?? '#94a3b8'
}

const expandedCredit = ref<string | null>(null)
function toggleCredit(work: string): void {
  expandedCredit.value = expandedCredit.value === work ? null : work
}

async function openDocsFile(relativePath: string): Promise<void> {
  if (!hasNativeApi) return
  try {
    const { repoRoot } = await api.getAppPaths()
    await api.openPath(`${repoRoot}/${relativePath}`)
  } catch {
    // best-effort — no toast infra here, and a missing/unreachable doc file
    // shouldn't block the rest of the page.
  }
}

const clearConfirm = ref(false)
function confirmClearHistory(): void {
  if (!clearConfirm.value) {
    clearConfirm.value = true
    setTimeout(() => (clearConfirm.value = false), 4000)
    return
  }
  clearHistory()
  clearConfirm.value = false
}

const cacheMessage = ref<string | null>(null)
async function clearModelsCache(): Promise<void> {
  try {
    await listComponents()
    cacheMessage.value = 'Cache de componentes atualizado a partir da API.'
  } catch (error) {
    cacheMessage.value =
      error instanceof Error ? `Falha ao atualizar: ${error.message}` : 'Falha ao atualizar cache.'
  }
  setTimeout(() => (cacheMessage.value = null), 4000)
}

async function pickDefaultOutputFolder(): Promise<void> {
  if (!hasNativeApi) return
  const folder = await api.selectOutputFolder(settingsState.defaultOutputFolder ?? undefined)
  if (folder) settingsState.defaultOutputFolder = folder
}

const appVersion = ref<string | null>(null)
const electronVersions = (
  window as unknown as { electron?: { process?: { versions?: Record<string, string> } } }
).electron?.process?.versions

async function loadDiagnostics(): Promise<void> {
  if (!hasNativeApi) return
  try {
    appVersion.value = await api.getAppVersion()
  } catch {
    // diagnostics are informational only — a failure here shouldn't block the page
  }
}
loadDiagnostics()

const historyCount = computed(() => historyState.entries.length)

const outputFolderLabel = computed(
  () => settingsState.defaultOutputFolder ?? t('settings.general.outputFolder.same')
)
</script>

<template>
  <div class="settings-view">
    <TopBar :title="t('settings.title')" />

    <div class="settings-content">
      <!-- ---------------------------- GERAL ---------------------------- -->
      <section class="settings-group">
        <div class="group-header">
          <div class="group-icon"><Settings2 :size="18" /></div>
          <div>
            <h2 class="group-title">{{ t('settings.general.title') }}</h2>
            <p class="group-description">{{ t('settings.general.description') }}</p>
          </div>
        </div>
        <div class="group-body">
          <SettingRow
            :label="t('settings.general.language.label')"
            :description="t('settings.general.language.description')"
          >
            <AppSelect
              :model-value="settingsState.language"
              :options="languageOptions"
              @update:model-value="(v) => setLanguage(v as SupportedLocale | 'auto')"
            />
          </SettingRow>
          <SettingRow
            :label="t('settings.general.theme.label')"
            :description="t('settings.general.theme.description')"
          >
            <SegmentedControl
              :model-value="settingsState.theme"
              :options="[
                { value: 'light', label: t('settings.general.theme.light') },
                { value: 'dark', label: t('settings.general.theme.dark') },
                { value: 'auto', label: t('settings.general.theme.auto') }
              ]"
              @update:model-value="(v) => setTheme(v as 'dark' | 'light' | 'auto')"
            />
          </SettingRow>
          <SettingRow
            :label="t('settings.general.accent.label')"
            :description="t('settings.general.accent.description')"
          >
            <div
              class="accent-swatches"
              role="radiogroup"
              :aria-label="t('settings.general.accent.label')"
            >
              <button
                v-for="accent in ACCENT_COLORS"
                :key="accent.value"
                type="button"
                class="accent-swatch"
                :class="[
                  `swatch-${accent.value}`,
                  { active: settingsState.accentColor === accent.value }
                ]"
                role="radio"
                :aria-checked="settingsState.accentColor === accent.value"
                :title="accent.label"
                @click="setAccentColor(accent.value as AccentColor)"
              >
                <Check v-if="settingsState.accentColor === accent.value" :size="13" />
              </button>
            </div>
          </SettingRow>
          <SettingRow
            :label="t('settings.general.autoUpdate.label')"
            :description="t('settings.general.autoUpdate.description')"
          >
            <SettingSwitch v-model="settingsState.autoCheckUpdates" disabled />
          </SettingRow>
          <SettingRow
            :label="t('settings.general.outputFolder.label')"
            :description="t('settings.general.outputFolder.description')"
          >
            <div class="folder-picker">
              <span class="folder-picker-value" :title="outputFolderLabel">{{
                outputFolderLabel
              }}</span>
              <button
                class="icon-btn"
                type="button"
                :disabled="!hasNativeApi"
                @click="pickDefaultOutputFolder"
              >
                <FolderOpen :size="15" />
              </button>
            </div>
          </SettingRow>
          <SettingRow
            :label="t('settings.general.exportFormat.label')"
            :description="t('settings.general.exportFormat.description')"
          >
            <AppSelect
              v-model="settingsState.defaultExportFormat"
              :options="[
                { value: 'png', label: '.png' },
                { value: 'jpg', label: '.jpg' },
                { value: 'webp', label: '.webp' }
              ]"
            />
          </SettingRow>
        </div>
      </section>

      <!-- ---------------------------- PROCESSAMENTO ---------------------------- -->
      <section class="settings-group">
        <div class="group-header">
          <div class="group-icon"><Cpu :size="18" /></div>
          <div>
            <h2 class="group-title">Processamento</h2>
            <p class="group-description">Padrões usados ao configurar uma nova imagem</p>
          </div>
        </div>
        <div class="group-body">
          <SettingRow label="Escala padrão" description="Fator pré-selecionado para novas imagens">
            <SegmentedControl
              :model-value="String(settingsState.defaultScalePreset)"
              :options="[
                { value: '2', label: '2x' },
                { value: '4', label: '4x' }
              ]"
              @update:model-value="(v) => (settingsState.defaultScalePreset = Number(v) as 2 | 4)"
            />
          </SettingRow>
          <SettingRow
            label="Manter proporção automaticamente"
            description="Trava largura/altura no modo customizado"
          >
            <SettingSwitch v-model="settingsState.defaultLockAspectRatio" />
          </SettingRow>
          <SettingRow
            label="Qualidade da imagem"
            description="Padrão para exportação em .jpg/.webp"
          >
            <div class="quality-control">
              <RangeSlider
                v-model="settingsState.defaultQuality"
                :min="1"
                :max="100"
                :default-value="90"
              />
              <span class="quality-value">{{ settingsState.defaultQuality }}</span>
            </div>
          </SettingRow>
          <SettingRow
            label="Tarefas simultâneas"
            description="Fixo em 1 pela arquitetura atual do processamento (fila serial, um worker)"
          >
            <span class="fixed-value">1</span>
          </SettingRow>
        </div>
      </section>

      <!-- ---------------------------- HISTÓRICO ---------------------------- -->
      <section class="settings-group">
        <div class="group-header">
          <div class="group-icon"><HistoryIcon :size="18" /></div>
          <div>
            <h2 class="group-title">Histórico</h2>
            <p class="group-description">
              {{ historyCount }} registro{{ historyCount === 1 ? '' : 's' }} salvos localmente
            </p>
          </div>
        </div>
        <div class="group-body">
          <SettingRow
            label="Limite máximo de registros"
            description="Os mais antigos são removidos ao ultrapassar"
          >
            <input
              v-model.number="settingsState.historyLimit"
              type="number"
              min="1"
              max="5000"
              class="number-input"
            />
          </SettingRow>
          <SettingRow
            label="Limpeza automática"
            description="Remove registros mais antigos que o período abaixo"
          >
            <SettingSwitch
              :model-value="settingsState.historyAutoCleanupDays !== null"
              @update:model-value="(v) => (settingsState.historyAutoCleanupDays = v ? 30 : null)"
            />
          </SettingRow>
          <SettingRow
            v-if="settingsState.historyAutoCleanupDays !== null"
            label="Manter por"
            description="Dias antes da remoção automática"
          >
            <AppSelect
              :model-value="String(settingsState.historyAutoCleanupDays)"
              :options="[
                { value: '7', label: '7 dias' },
                { value: '30', label: '30 dias' },
                { value: '90', label: '90 dias' }
              ]"
              @update:model-value="(v) => (settingsState.historyAutoCleanupDays = Number(v))"
            />
          </SettingRow>
          <SettingRow
            label="Limpar histórico manualmente"
            description="Remove todos os registros salvos — não afeta os arquivos exportados"
          >
            <button
              class="danger-btn"
              type="button"
              :disabled="!historyCount"
              @click="confirmClearHistory"
            >
              <Trash2 :size="14" /> {{ clearConfirm ? 'Confirmar exclusão' : 'Limpar histórico' }}
            </button>
          </SettingRow>
          <SettingRow label="Limpar cache" description="Recarrega a lista de modelos direto da API">
            <div class="cache-row">
              <button class="secondary-btn" type="button" @click="clearModelsCache">
                <RotateCcw :size="14" /> Limpar cache
              </button>
              <span v-if="cacheMessage" class="cache-message"
                ><Check :size="12" /> {{ cacheMessage }}</span
              >
            </div>
          </SettingRow>
        </div>
      </section>

      <!-- ---------------------------- INTERFACE ---------------------------- -->
      <section class="settings-group">
        <div class="group-header">
          <div class="group-icon"><LayoutGrid :size="18" /></div>
          <div>
            <h2 class="group-title">Interface</h2>
            <p class="group-description">Personalize a exibição de informações e densidade</p>
          </div>
        </div>
        <div class="group-body">
          <SettingRow
            label="Mostrar descrições dos modelos"
            description="Exibe a finalidade resumida nos cards da aba Modelos"
          >
            <SettingSwitch v-model="settingsState.showModelDescriptions" />
          </SettingRow>
          <SettingRow
            label="Mostrar indicadores de uso comercial"
            description="Badge de licença nos modelos"
          >
            <SettingSwitch v-model="settingsState.showCommercialBadges" />
          </SettingRow>
          <SettingRow label="Tamanho das miniaturas" description="Fila, editor e histórico">
            <SegmentedControl
              v-model="settingsState.thumbnailSize"
              :options="[
                { value: 'sm', label: 'Pequenas' },
                { value: 'md', label: 'Médias' },
                { value: 'lg', label: 'Grandes' }
              ]"
            />
          </SettingRow>
          <SettingRow
            label="Ativar animações"
            description="Transições e microanimações da interface"
          >
            <SettingSwitch v-model="settingsState.animationsEnabled" />
          </SettingRow>
          <SettingRow label="Densidade da interface" description="Espaçamento entre elementos">
            <SegmentedControl
              v-model="settingsState.density"
              :options="[
                { value: 'compact', label: 'Compacta' },
                { value: 'standard', label: 'Padrão' },
                { value: 'comfortable', label: 'Confortável' }
              ]"
            />
          </SettingRow>
        </div>
      </section>

      <!-- ---------------------------- AVANÇADO ---------------------------- -->
      <section class="settings-group">
        <div class="group-header">
          <div class="group-icon"><Wrench :size="18" /></div>
          <div>
            <h2 class="group-title">Avançado</h2>
            <p class="group-description">Diagnóstico e informações técnicas</p>
          </div>
        </div>
        <div class="group-body">
          <SettingRow label="Versão do aplicativo">
            <span class="fixed-value">{{ appVersion ?? '—' }}</span>
          </SettingRow>
          <SettingRow v-if="electronVersions" label="Versões do runtime">
            <span class="fixed-value mono">
              Electron {{ electronVersions.electron }} · Chromium {{ electronVersions.chrome }} ·
              Node {{ electronVersions.node }}
            </span>
          </SettingRow>
        </div>
      </section>

      <section class="settings-group">
        <div class="group-header credits-header">
          <div class="group-icon credits-icon"><Award :size="18" /></div>
          <div class="credits-header-text">
            <h2 class="group-title">Créditos</h2>
            <p class="group-description">Atribuição obrigatória dos componentes usados.</p>
            <button
              class="credits-doc-link"
              type="button"
              :disabled="!hasNativeApi"
              @click="openDocsFile('docs/models/MODEL_LICENSES.md')"
            >
              Saiba mais em docs/models/MODEL_LICENSES.md <ExternalLink :size="12" />
            </button>
          </div>
          <button
            class="btn-outline credits-doc-btn"
            type="button"
            :disabled="!hasNativeApi"
            @click="openDocsFile('docs/models/MODEL_LICENSES.md')"
          >
            <ExternalLink :size="14" /> Ver documentação <ChevronRight :size="14" />
          </button>
        </div>
        <div class="group-body credits-body">
          <ul class="credits-list">
            <li v-for="credit in CREDITS" :key="credit.work">
              <div class="credit-row">
                <div class="credit-icon" :style="{ background: credit.tint + '22', color: credit.tint }">
                  <component :is="credit.icon" :size="18" />
                </div>
                <div class="credit-main">
                  <div class="credit-title-row">
                    <span class="credit-name">{{ credit.capability }}</span>
                  </div>
                  <span class="credit-author">{{ credit.work }} — {{ credit.author }}</span>
                  <p v-if="credit.note" class="credit-note">
                    <Info :size="12" /> {{ credit.note }}
                  </p>
                </div>
                <span
                  class="credit-license-badge"
                  :style="{
                    background: licenseTone(credit.license) + '22',
                    color: licenseTone(credit.license)
                  }"
                  >{{ credit.license }}</span
                >
                <button
                  class="credit-expand-btn"
                  type="button"
                  :title="expandedCredit === credit.work ? 'Recolher' : 'Detalhes'"
                  @click="toggleCredit(credit.work)"
                >
                  <component :is="expandedCredit === credit.work ? ChevronDown : ChevronRight" :size="16" />
                </button>
              </div>
              <p v-if="expandedCredit === credit.work" class="credit-detail">
                Distribuído sob licença {{ credit.license }}. Consulte
                docs/models/MODEL_LICENSES.md para o texto completo da licença e demais
                condições de uso.
              </p>
            </li>
          </ul>
        </div>
        <div class="credits-footer">
          <ShieldCheck :size="18" class="credits-footer-icon" />
          <div class="credits-footer-text">
            <p>Utilizamos apenas componentes de código aberto com licenças compatíveis.</p>
            <p>Em caso de dúvidas, consulte a documentação completa.</p>
          </div>
          <button
            class="btn-outline"
            type="button"
            :disabled="!hasNativeApi"
            @click="openDocsFile('docs/models/MODEL_LICENSES.md')"
          >
            <Scale :size="14" /> Sobre licenças <ExternalLink :size="12" />
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  flex: 1;
  min-width: 0;
}

.settings-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  width: 100%;
  max-width: 860px;
  margin: 0 auto;
}

.settings-group {
  background: var(--surface-1);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-lg);
}

.btn-outline {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--surface-2);
  border: 1px solid var(--surface-border);
  color: var(--text-primary);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  cursor: pointer;
  white-space: nowrap;
}
.btn-outline:hover:not(:disabled) {
  background: var(--surface-3);
}
.btn-outline:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.credits-header {
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}
.credits-icon {
  background: #14b8a622;
  color: #14b8a6;
}
.credits-header-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.credits-doc-link {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  padding: 0;
  margin-top: 2px;
  color: var(--color-primary);
  font-size: var(--fs-caption);
  cursor: pointer;
}
.credits-doc-link:hover:not(:disabled) {
  text-decoration: underline;
}
.credits-doc-link:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.credits-doc-btn {
  flex-shrink: 0;
}

.credits-body {
  padding: var(--space-3);
}
.credits-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.credits-list li {
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--border-1);
}
.credits-list li:last-child {
  border-bottom: none;
}
.credit-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}
.credit-icon {
  flex-shrink: 0;
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}
.credit-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.credit-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.credit-name {
  font-weight: 600;
  font-size: var(--fs-body-sm);
  color: var(--text-primary);
}
.credit-author {
  color: var(--text-secondary);
  font-size: var(--fs-body-sm);
}
.credit-note {
  display: flex;
  align-items: center;
  gap: 5px;
  margin: 2px 0 0;
  color: var(--text-tertiary);
  font-size: var(--fs-caption);
}
.credit-license-badge {
  flex-shrink: 0;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  white-space: nowrap;
}
.credit-expand-btn {
  flex-shrink: 0;
  width: 26px;
  height: 26px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  border-radius: var(--radius-sm);
}
.credit-expand-btn:hover {
  background: var(--surface-2);
  color: var(--text-primary);
}
.credit-detail {
  margin: var(--space-2) 0 0 50px;
  color: var(--text-secondary);
  font-size: var(--fs-caption);
}

.credits-footer {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  border-top: 1px solid var(--surface-border-soft);
  background: var(--surface-2);
  border-radius: 0 0 var(--radius-lg) var(--radius-lg);
}
.credits-footer-icon {
  flex-shrink: 0;
  color: var(--color-primary);
}
.credits-footer-text {
  flex: 1;
  min-width: 0;
}
.credits-footer-text p {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--text-secondary);
}

.group-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4);
  border-bottom: 1px solid var(--surface-border-soft);
  background: var(--surface-2);
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}

.group-icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.group-title {
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.group-description {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
  margin-top: 1px;
}

.group-body {
  padding: 0 var(--space-4);
}

.folder-picker {
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: 320px;
}

.folder-picker-value {
  font-size: var(--fs-caption);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.icon-btn {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  border: 1px solid var(--surface-border);
  background: var(--surface-3);
  color: var(--text-secondary);
  cursor: pointer;
}

.icon-btn:hover:not(:disabled) {
  color: var(--text-primary);
  background: var(--surface-2);
}

.icon-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.quality-control {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 180px;
}

.quality-value {
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
  font-family: var(--font-mono);
  width: 28px;
  text-align: right;
}

.fixed-value {
  font-size: var(--fs-caption);
  color: var(--text-secondary);
}

.fixed-value.mono {
  font-family: var(--font-mono);
  font-size: 11px;
}

.fixed-value.truncate {
  display: inline-block;
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}

.number-input {
  width: 90px;
  background: var(--surface-3);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  padding: 7px 10px;
  font-size: var(--fs-label);
  font-family: var(--font-mono);
}

.licensing-url-input {
  width: 220px;
}

.link-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  cursor: pointer;
}

.danger-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--color-danger-soft);
  border: 1px solid var(--color-danger);
  color: var(--color-danger);
  border-radius: var(--radius-sm);
  padding: 7px 12px;
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  cursor: pointer;
}

.danger-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.secondary-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--surface-3);
  border: 1px solid var(--surface-border);
  color: var(--text-primary);
  border-radius: var(--radius-sm);
  padding: 7px 12px;
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  cursor: pointer;
}

.secondary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.cache-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.cache-message {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-success);
}

.accent-swatches {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.accent-swatch {
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  border-radius: 50%;
  border: 2px solid transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  cursor: pointer;
  transition:
    transform var(--transition-fast),
    border-color var(--transition-fast);
}

.accent-swatch:hover {
  transform: scale(1.08);
}

.accent-swatch:focus-visible {
  outline: 2px solid var(--text-primary);
  outline-offset: 2px;
}

.accent-swatch.active {
  border-color: var(--text-primary);
}

.swatch-cyan {
  background: #06b6d4;
}
.swatch-blue {
  background: #3b82f6;
}
.swatch-purple {
  background: #8b5cf6;
}
.swatch-green {
  background: #22c55e;
}
.swatch-red {
  background: #ef4444;
}
.swatch-orange {
  background: #f97316;
}
.swatch-pink {
  background: #ec4899;
}
.swatch-gray {
  background: #64748b;
}
</style>
