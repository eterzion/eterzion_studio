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
  Bug,
  Check,
  ExternalLink
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
import { modelConfigState } from '../store/modelConfig'
import { clearHistory, historyState } from '../store/history'
import { initLicense } from '../store/license'
import { getModels } from '../backend'
import { api, hasNativeApi } from '../api'

function reloadLicense(): void {
  initLicense()
}

const { t } = useI18n()

const detectedLocaleLabel = computed(
  () => SUPPORTED_LOCALES.find((l) => l.value === detectSystemLocale())?.label ?? ''
)
const languageOptions = computed(() => [
  { value: 'auto', label: `${t('settings.general.theme.auto')} (${detectedLocaleLabel.value})` },
  ...SUPPORTED_LOCALES.map((l) => ({ value: l.value as string, label: l.label }))
])

const emit = defineEmits<{
  navigate: [key: 'modelos']
}>()

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
    await getModels()
    cacheMessage.value = 'Cache de modelos atualizado a partir da API.'
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
const appPaths = ref<{ documents: string; repoRoot: string; apiBaseUrl: string } | null>(null)
const electronVersions = (
  window as unknown as { electron?: { process?: { versions?: Record<string, string> } } }
).electron?.process?.versions

async function loadDiagnostics(): Promise<void> {
  if (!hasNativeApi) return
  try {
    appVersion.value = await api.getAppVersion()
    appPaths.value = await api.getAppPaths()
  } catch {
    // diagnostics are informational only — a failure here shouldn't block the page
  }
}
loadDiagnostics()

async function openDevTools(): Promise<void> {
  if (!hasNativeApi) return
  await api.openDevTools()
}

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
          <SettingRow label="Modelo padrão" description="Definido na aba Modelos">
            <button class="link-btn" type="button" @click="emit('navigate', 'modelos')">
              {{ modelConfigState.saved?.modelName ?? 'Nenhum definido' }}
              <ExternalLink :size="12" />
            </button>
          </SettingRow>
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
          <SettingRow label="Servidor da API">
            <span class="fixed-value mono">{{ appPaths?.apiBaseUrl ?? '—' }}</span>
          </SettingRow>
          <SettingRow
            label="Servidor de licenciamento"
            description="Endereço do interface/astros_licensing_service — vazio desativa o módulo de licença"
          >
            <input
              v-model="settingsState.licensingServiceUrl"
              type="text"
              placeholder="http://127.0.0.1:8766"
              class="number-input licensing-url-input"
              @change="reloadLicense"
            />
          </SettingRow>
          <SettingRow label="Pasta do repositório">
            <span class="fixed-value mono truncate" :title="appPaths?.repoRoot">{{
              appPaths?.repoRoot ?? '—'
            }}</span>
          </SettingRow>
          <SettingRow
            label="Opções de depuração"
            description="Abre o DevTools do Chromium para inspecionar a interface"
          >
            <button
              class="secondary-btn"
              type="button"
              :disabled="!hasNativeApi"
              @click="openDevTools"
            >
              <Bug :size="14" /> Abrir DevTools
            </button>
          </SettingRow>
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
  max-width: 860px;
}

.settings-group {
  background: var(--surface-1);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-lg);
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
