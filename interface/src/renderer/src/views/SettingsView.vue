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
  ShieldCheck,
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
import NumberStepper from '../components/NumberStepper.vue'
import SettingSwitch from '../components/SettingSwitch.vue'
import SegmentedControl from '../components/SegmentedControl.vue'
import AppSelect from '../components/AppSelect.vue'
import RangeSlider from '../components/RangeSlider.vue'
import AppButton from '../components/atoms/AppButton.vue'
import { settingsState, setTheme, setLanguage } from '../store/settings'
import { SUPPORTED_LOCALES, detectSystemLocale, type SupportedLocale } from '../i18n'
import { clearHistory, historyState } from '../store/history'
import { listComponents } from '../services/api'
import { api, hasNativeApi } from '../services/native'

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
  capabilityKey: string
  work: string
  author: string
  license: string
  icon: unknown
  tint: string
}[] = [
  {
    capabilityKey: 'imagePhoto',
    work: '4xNomosWebPhoto_RealPLKSR',
    author: 'Philip Hofmann (Phhofm)',
    license: 'CC-BY-4.0',
    icon: ImageIcon,
    tint: '#3b82f6'
  },
  {
    capabilityKey: 'imageAnime',
    work: '2xHFA2kSPAN',
    author: 'Philip Hofmann (Phhofm)',
    license: 'CC-BY-4.0',
    icon: Palette,
    tint: '#a855f7'
  },
  {
    capabilityKey: 'videoAnime',
    work: 'Real-ESRGAN (realesr-animevideov3)',
    author: 'Xintao Wang',
    license: 'BSD-3-Clause',
    icon: Film,
    tint: '#f59e0b'
  },
  {
    capabilityKey: 'videoReal',
    work: '2xPublic_realplksr_dysample_layernorm_real',
    author: 'Philip Hofmann (Phhofm)',
    license: 'Apache-2.0',
    icon: Video,
    tint: '#ef4444'
  },
  {
    capabilityKey: 'audioSpeech',
    work: 'audiosronnx (LavaSR)',
    author: 'TigreGotico',
    license: 'Apache-2.0',
    icon: AudioLines,
    tint: '#14b8a6'
  },
  {
    capabilityKey: 'audioMusic',
    work: 'SonicMaster',
    author: 'AMAAI Lab',
    license: 'Apache-2.0',
    icon: Music2,
    tint: '#ec4899'
  },
  // Linha propria, e nao mais uma observacao "condicional" na da SonicMaster:
  // o VAE e' dependencia obrigatoria dela, sob outra licenca, e o credito a'
  // Stability AI e' obrigacao dessa licenca (docs/models/MODEL_LICENSES.md,
  // secao 3-bis, item 3). A observacao era a unica mencao a' Stability na
  // tela; tira-la sem esta linha apagaria uma atribuicao exigida.
  {
    capabilityKey: 'audioMusic',
    work: 'Stable Audio Open 1.0 (VAE)',
    author: 'Stability AI',
    license: 'Stability AI Community License',
    icon: Music2,
    tint: '#ec4899'
  },
  {
    capabilityKey: 'faceEnhance',
    work: 'YuNet',
    author: 'OpenCV / libfacedetection',
    license: 'MIT',
    icon: Scan,
    tint: '#22c55e'
  },
  {
    capabilityKey: 'media',
    work: 'FFmpeg',
    author: 'FFmpeg developers',
    license: 'LGPL v2.1+',
    icon: PlayCircle,
    tint: '#3b82f6'
  }
]

const LICENSE_TONES: Record<string, string> = {
  'CC-BY-4.0': '#3b82f6',
  'BSD-3-Clause': '#a855f7',
  'Apache-2.0': '#22c55e',
  MIT: '#94a3b8',
  'LGPL v2.1+': '#94a3b8',
  'Stability AI Community License': '#f59e0b'
}
function licenseTone(license: string): string {
  return LICENSE_TONES[license] ?? '#94a3b8'
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
    cacheMessage.value = t('settings.cacheRefreshed')
  } catch (error) {
    cacheMessage.value =
      error instanceof Error
        ? t('settings.cacheRefreshFailedWith', { error: error.message })
        : t('settings.cacheRefreshFailed')
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
      <div class="settings-column">
        <!-- ---------------------------- GERAL ---------------------------- -->
        <section class="settings-group">
          <div class="group-header">
            <div class="group-icon icon-chip"><Settings2 :size="18" /></div>
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
                <AppButton
                  variant="secondary"
                  icon-only
                  :disabled="!hasNativeApi"
                  @click="pickDefaultOutputFolder"
                >
                  <template #icon><FolderOpen :size="15" /></template>
                </AppButton>
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
            <div class="group-icon icon-chip"><Cpu :size="18" /></div>
            <div>
              <h2 class="group-title">{{ t('settings.processingTitle') }}</h2>
              <p class="group-description">{{ t('settings.processingDescription') }}</p>
            </div>
          </div>
          <div class="group-body">
            <SettingRow
              :label="t('settings.defaultScale')"
              :description="t('settings.defaultScaleDescription')"
            >
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
              :label="t('settings.keepAspect')"
              :description="t('settings.keepAspectDescription')"
            >
              <SettingSwitch v-model="settingsState.defaultLockAspectRatio" />
            </SettingRow>
            <SettingRow
              :label="t('settings.imageQuality')"
              :description="t('settings.imageQualityDescription')"
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
              :label="t('settings.concurrentJobs')"
              :description="t('settings.concurrentJobsDescription')"
            >
              <span class="fixed-value">1</span>
            </SettingRow>
          </div>
        </section>

        <!-- ---------------------------- HISTÓRICO ---------------------------- -->
        <section class="settings-group">
          <div class="group-header">
            <div class="group-icon icon-chip"><HistoryIcon :size="18" /></div>
            <div>
              <h2 class="group-title">{{ t('history.title') }}</h2>
              <p class="group-description">
                {{ t('history.storedCount', historyCount) }}
              </p>
            </div>
          </div>
          <div class="group-body">
            <SettingRow
              :label="t('history.limitSettingLabel')"
              :description="t('history.limitSettingDescription')"
            >
              <NumberStepper
                v-model="settingsState.historyLimit"
                compact
                :min="1"
                :max="5000"
                :aria-label="t('history.limitSettingLabel')"
              />
            </SettingRow>
            <SettingRow
              :label="t('settings.autoCleanup')"
              :description="t('settings.autoCleanupDescription')"
            >
              <SettingSwitch
                :model-value="settingsState.historyAutoCleanupDays !== null"
                @update:model-value="(v) => (settingsState.historyAutoCleanupDays = v ? 30 : null)"
              />
            </SettingRow>
            <SettingRow
              v-if="settingsState.historyAutoCleanupDays !== null"
              :label="t('settings.keepFor')"
              :description="t('settings.keepForDescription')"
            >
              <AppSelect
                :model-value="String(settingsState.historyAutoCleanupDays)"
                :options="[
                  { value: '7', label: t('settings.days', 7) },
                  { value: '30', label: t('settings.days', 30) },
                  { value: '90', label: t('settings.days', 90) }
                ]"
                @update:model-value="(v) => (settingsState.historyAutoCleanupDays = Number(v))"
              />
            </SettingRow>
            <SettingRow
              :label="t('settings.clearHistory')"
              :description="t('settings.clearHistoryDescription')"
            >
              <AppButton variant="danger" :disabled="!historyCount" @click="confirmClearHistory">
                <template #icon><Trash2 :size="14" /></template>
                {{ clearConfirm ? t('settings.confirmClear') : t('settings.clearHistoryAction') }}
              </AppButton>
            </SettingRow>
            <SettingRow
              :label="t('settings.clearCache')"
              :description="t('settings.clearCacheDescription')"
            >
              <div class="cache-row">
                <AppButton variant="secondary" @click="clearModelsCache">
                  <template #icon><RotateCcw :size="14" /></template>
                  {{ t('settings.clearCache') }}
                </AppButton>
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
            <div class="group-icon icon-chip"><LayoutGrid :size="18" /></div>
            <div>
              <h2 class="group-title">{{ t('settings.interfaceTitle') }}</h2>
              <p class="group-description">{{ t('settings.interfaceDescription') }}</p>
            </div>
          </div>
          <div class="group-body">
            <SettingRow
              :label="t('settings.showDescriptions')"
              :description="t('settings.showDescriptionsDescription')"
            >
              <SettingSwitch v-model="settingsState.showModelDescriptions" />
            </SettingRow>
            <SettingRow
              :label="t('settings.showCommercial')"
              :description="t('settings.showCommercialDescription')"
            >
              <SettingSwitch v-model="settingsState.showCommercialBadges" />
            </SettingRow>
            <SettingRow
              :label="t('settings.thumbnailSize')"
              :description="t('settings.thumbnailSizeDescription')"
            >
              <SegmentedControl
                v-model="settingsState.thumbnailSize"
                :options="[
                  { value: 'sm', label: t('settings.small') },
                  { value: 'md', label: t('settings.medium') },
                  { value: 'lg', label: t('settings.large') }
                ]"
              />
            </SettingRow>
            <SettingRow
              :label="t('settings.animations')"
              :description="t('settings.animationsDescription')"
            >
              <SettingSwitch v-model="settingsState.animationsEnabled" />
            </SettingRow>
            <SettingRow
              :label="t('settings.density')"
              :description="t('settings.densityDescription')"
            >
              <SegmentedControl
                v-model="settingsState.density"
                :options="[
                  { value: 'compact', label: t('settings.compact') },
                  { value: 'standard', label: t('settings.standard') },
                  { value: 'comfortable', label: t('settings.comfortable') }
                ]"
              />
            </SettingRow>
          </div>
        </section>

        <!-- ---------------------------- AVANÇADO ---------------------------- -->
        <section class="settings-group">
          <div class="group-header">
            <div class="group-icon icon-chip"><Wrench :size="18" /></div>
            <div>
              <h2 class="group-title">{{ t('settings.advancedTitle') }}</h2>
              <p class="group-description">{{ t('settings.advancedDescription') }}</p>
            </div>
          </div>
          <div class="group-body">
            <SettingRow :label="t('settings.appVersion')">
              <span class="fixed-value">{{ appVersion ?? '—' }}</span>
            </SettingRow>
            <SettingRow v-if="electronVersions" :label="t('settings.runtimeVersions')">
              <span class="fixed-value mono">
                Electron {{ electronVersions.electron }} · Chromium {{ electronVersions.chrome }} ·
                Node {{ electronVersions.node }}
              </span>
            </SettingRow>
          </div>
        </section>

        <section class="settings-group">
          <div class="group-header credits-header">
            <div class="group-icon icon-chip"><Award :size="18" /></div>
            <div class="credits-header-text">
              <h2 class="group-title">{{ t('settings.creditsTitle') }}</h2>
              <p class="group-description">{{ t('settings.creditsDescription') }}</p>
            </div>
          </div>
          <div class="group-body credits-body">
            <ul class="credits-list">
              <li v-for="credit in CREDITS" :key="credit.work">
                <div class="credit-row">
                  <div class="credit-icon icon-chip" :style="{ '--chip-tone': credit.tint }">
                    <component :is="credit.icon" :size="18" />
                  </div>
                  <div class="credit-main">
                    <div class="credit-title-row">
                      <span class="credit-name">{{ t(`credits.${credit.capabilityKey}`) }}</span>
                    </div>
                    <span class="credit-author">{{ credit.work }} — {{ credit.author }}</span>
                  </div>
                  <span
                    class="credit-license-badge"
                    :style="{
                      background: licenseTone(credit.license) + '22',
                      color: licenseTone(credit.license)
                    }"
                    >{{ credit.license }}</span
                  >
                </div>
              </li>
            </ul>
          </div>
          <div class="credits-footer">
            <ShieldCheck :size="18" class="credits-footer-icon" />
            <div class="credits-footer-text">
              <p>{{ t('settings.openSourceOnly') }}</p>
            </div>
          </div>
        </section>
      </div>
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

/* The scroller is the full-width element and the 860px column lives inside
   it, so the scrollbar sits at the window edge like every other scrollable
   surface — with `max-width` on the scroller itself the bar was pulled into
   the content column and ran flush against the header. */
.settings-content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--space-4);
}

.settings-column {
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

.credits-header {
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}
.credits-header-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
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
  border-bottom: 1px solid var(--surface-border);
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
  width: 38px;
  height: 38px;
  border-radius: var(--radius-md);
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
.credit-license-badge {
  flex-shrink: 0;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  white-space: nowrap;
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
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
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
  gap: var(--space-1-5);
  max-width: 320px;
}

.folder-picker-value {
  font-size: var(--fs-caption);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.licensing-url-input {
  width: 220px;
}

.link-btn {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  cursor: pointer;
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
</style>
