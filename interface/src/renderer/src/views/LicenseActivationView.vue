<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  KeyRound,
  Loader2,
  Copy,
  XCircle,
  RefreshCw,
  HelpCircle
} from '@lucide/vue'
import { licenseState, activateLicense, refreshLicenseStatus } from '../store/license'
import AppButton from '../components/atoms/AppButton.vue'

// T039: rendered by App.vue INSTEAD of the whole app shell (no sidebar)
// whenever isHardBlocked() is true — before the first successful check this
// session, or once a status is confirmed bad (not_activated/blocked). Never
// touches files already on disk (FR-059/SC-019), it only gates new work.

const { t } = useI18n()

const licenseInput = ref('')
const copied = ref(false)

async function submit(): Promise<void> {
  if (!licenseInput.value.trim()) return
  await activateLicense(licenseInput.value.trim())
  if (licenseState.status === 'active') licenseInput.value = ''
}

async function copyInput(): Promise<void> {
  if (!licenseInput.value.trim()) return
  await navigator.clipboard.writeText(licenseInput.value.trim())
  copied.value = true
  setTimeout(() => (copied.value = false), 1500)
}

function openHelp(): void {
  // main/index.ts's setWindowOpenHandler routes this to shell.openExternal.
  window.open('https://example.com/astros-upscale/help', '_blank')
}

// Inside the computed rather than in a const map beside it: a const is built
// once at import and would keep whichever language was active then. This screen
// in particular can be the first thing shown, before anything else has run.
const COPY_KEYS: Record<string, string> = {
  not_activated: 'notActivated',
  blocked: 'blocked',
  error: 'error',
  checking: 'checking'
}

const copy = computed(() => {
  const key = COPY_KEYS[licenseState.status] ?? 'error'
  return { title: t(`activation.${key}Title`), body: t(`activation.${key}Body`) }
})
const icon = computed(() => {
  if (licenseState.status === 'checking') return Loader2
  if (licenseState.status === 'not_activated') return KeyRound
  if (licenseState.status === 'error') return ShieldAlert
  return ShieldQuestion
})
const isPrimaryActivate = computed(() => licenseState.status === 'not_activated')
</script>

<template>
  <div class="license-block">
    <div class="license-card">
      <div class="header-group">
        <div class="icon-badge" :class="'tone-' + licenseState.status">
          <span class="badge-particle p1" /><span class="badge-particle p2" /><span
            class="badge-particle p3"
          />
          <component
            :is="icon"
            :size="36"
            :class="{ 'animate-spin': licenseState.status === 'checking' }"
            class="license-icon"
          />
        </div>
        <h1>{{ copy.title }}</h1>
        <p class="license-body">{{ copy.body }}</p>
      </div>

      <template v-if="licenseState.status !== 'checking'">
        <hr class="divider" />

        <div class="field-group">
          <label class="field-label" for="activation-license-id">{{ t('license.idLabel') }}</label>
          <div class="input-wrap">
            <KeyRound :size="15" class="input-icon" />
            <input
              id="activation-license-id"
              v-model="licenseInput"
              type="text"
              placeholder="lic_..."
              class="license-input"
              @keydown.enter="submit"
            />
            <AppButton
              variant="ghost"
              icon-only
              size="sm"
              :title="t('activation.copy')"
              :disabled="!licenseInput.trim()"
              @click="copyInput"
            >
              <template #icon><Copy :size="14" /></template>
            </AppButton>
          </div>
          <p v-if="copied" class="copied-hint">{{ t('activation.copied') }}</p>
        </div>

        <div v-if="licenseState.status === 'error'" class="fetch-error-box">
          <XCircle :size="18" class="fetch-error-icon" />
          <div>
            <p class="fetch-error-title">{{ t('activation.fetchErrorTitle') }}</p>
            <p class="fetch-error-detail">
              {{ licenseState.error ?? t('activation.fetchErrorDetail') }}
            </p>
          </div>
        </div>

        <div class="actions-group">
          <AppButton
            v-if="isPrimaryActivate"
            variant="primary"
            size="lg"
            class="w-full"
            :disabled="!licenseInput.trim()"
            @click="submit"
          >
            <template #icon><ShieldCheck :size="16" /></template>
            {{ t('license.activate') }}
          </AppButton>
          <AppButton
            v-else
            variant="primary"
            size="lg"
            class="w-full"
            @click="refreshLicenseStatus"
          >
            <template #icon><RefreshCw :size="16" /></template>
            {{ t('activation.retry') }}
          </AppButton>

          <AppButton variant="ghost" size="lg" class="w-full" @click="openHelp">
            <template #icon><HelpCircle :size="16" /></template>
            {{ t('activation.needHelp') }}
          </AppButton>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.license-block {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  width: 100vw;
  padding: var(--space-4);
  background: var(--surface-0);
}

.license-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  max-width: 460px;
  text-align: center;
  padding: var(--space-4);
  background: var(--surface-1);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-lg, 16px);
  padding: var(--space-6) var(--space-5);
}

.header-group {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  margin-bottom: 28px;
}

.icon-badge {
  position: relative;
  width: 96px;
  height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-sm);
  background: radial-gradient(
    circle,
    var(--color-warning-soft, rgba(245, 158, 11, 0.15)) 0%,
    transparent 70%
  );
}

.icon-badge::before {
  content: '';
  position: absolute;
  inset: 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-warning-soft, rgba(245, 158, 11, 0.3));
}

.icon-badge.tone-not_activated {
  background: radial-gradient(circle, var(--color-primary-soft) 0%, transparent 70%);
}

.icon-badge.tone-not_activated::before {
  border-color: var(--color-primary-soft);
}

.license-icon {
  color: var(--color-warning, var(--text-secondary));
  z-index: 1;
}

.icon-badge.tone-not_activated .license-icon {
  color: var(--color-primary);
}

.badge-particle {
  position: absolute;
  width: 4px;
  height: 4px;
  border-radius: var(--radius-sm);
  background: var(--color-warning, var(--text-tertiary));
  opacity: 0.5;
}

.badge-particle.p1 {
  top: 6px;
  right: 14px;
}

.badge-particle.p2 {
  bottom: 10px;
  left: 4px;
  width: 3px;
  height: 3px;
}

.badge-particle.p3 {
  top: 30px;
  right: -2px;
  width: 3px;
  height: 3px;
}

h1 {
  font-size: var(--fs-h3, 1.4rem);
  margin: 0;
  color: var(--text-primary);
}

.license-body {
  color: var(--text-secondary);
  font-size: var(--fs-body-sm);
  max-width: 380px;
}

.divider {
  width: 100%;
  border: none;
  border-top: 1px solid var(--surface-border-soft);
  margin: 0 0 24px;
}

.field-group {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 20px;
}

.field-label {
  align-self: flex-start;
  font-size: var(--fs-label);
  color: var(--text-secondary);
}

.input-wrap {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface-2);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  padding: 0 10px;
}

.input-icon {
  flex-shrink: 0;
  color: var(--text-tertiary);
}

.license-input {
  flex: 1;
  min-width: 0;
  background: transparent;
  border: none;
  color: var(--text-primary);
  padding: 10px 0;
  font-family: var(--font-mono);
  outline: none;
}

.copied-hint {
  align-self: flex-end;
  font-size: 11px;
  color: var(--color-success);
  margin: 0;
}

.fetch-error-box {
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  text-align: left;
  background: var(--color-danger-soft);
  border: 1px solid var(--color-danger-soft);
  border-radius: var(--radius-sm);
  padding: var(--space-3);
  margin-bottom: 20px;
}

.fetch-error-icon {
  flex-shrink: 0;
  color: var(--color-danger);
  margin-top: 2px;
}

.fetch-error-title {
  margin: 0;
  font-weight: var(--fw-semibold);
  color: var(--color-danger);
  font-size: var(--fs-body-sm);
}

.fetch-error-detail {
  margin: 2px 0 0;
  color: var(--text-secondary);
  font-size: var(--fs-caption);
}

.actions-group {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 28px;
}
</style>
