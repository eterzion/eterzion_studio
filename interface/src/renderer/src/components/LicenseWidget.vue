<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { KeyRound, ShieldCheck, ShieldAlert, ShieldQuestion, Loader2 } from '@lucide/vue'
import { licenseState, deactivateLicense } from '../store/license'
import AppButton from './atoms/AppButton.vue'

const { t } = useI18n()

const open = ref(false)
const root = ref<HTMLElement | null>(null)

const meta = computed(() => {
  switch (licenseState.status) {
    case 'active':
      return { icon: ShieldCheck, label: t('license.active'), tone: 'success' }
    case 'offline_tolerance':
      return { icon: ShieldCheck, label: t('license.activeOffline'), tone: 'success' }
    case 'offline_expiring':
      return { icon: ShieldAlert, label: t('license.checkConnection'), tone: 'warning' }
    case 'checking':
      return { icon: Loader2, label: t('license.checking'), tone: 'neutral' }
    case 'error':
      return { icon: ShieldAlert, label: t('license.error'), tone: 'danger' }
    case 'blocked':
      return { icon: ShieldAlert, label: t('license.blocked'), tone: 'danger' }
    case 'not_activated':
      return { icon: KeyRound, label: t('license.notActivated'), tone: 'warning' }
    case 'not_configured':
      return { icon: KeyRound, label: t('license.notConfigured'), tone: 'neutral' }
    default:
      return { icon: ShieldQuestion, label: t('license.generic'), tone: 'neutral' }
  }
})

function onDocClick(e: MouseEvent): void {
  if (open.value && root.value && !root.value.contains(e.target as Node)) open.value = false
}
onMounted(() => document.addEventListener('mousedown', onDocClick))
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick))
</script>

<template>
  <div ref="root" class="license-widget">
    <button
      class="license-pill"
      :class="'tone-' + meta.tone"
      type="button"
      :title="t('license.title')"
      @click="open = !open"
    >
      <component
        :is="meta.icon"
        :size="14"
        :class="{ 'animate-spin': licenseState.status === 'checking' }"
      />
      <span class="license-pill-label">{{ meta.label }}</span>
    </button>

    <div v-if="open" class="license-popover">
      <p class="popover-title">{{ t('license.title') }}</p>
      <!-- The state in words. Without it the popover can open showing nothing
           but its own title: installations, offline days and the deactivate
           button are all conditional, and none of them applies to, say, a
           licence that is simply not configured. -->
      <p class="popover-detail" :class="'tone-' + meta.tone">
        <component :is="meta.icon" :size="13" />
        {{ meta.label }}
      </p>
      <p v-if="licenseState.installationsLimit" class="popover-detail">
        {{
          t('license.installations', {
            used: licenseState.installationsUsed,
            limit: licenseState.installationsLimit
          })
        }}
      </p>
      <!-- Pluralised rather than "dia(s)": Russian needs three forms and
           Japanese none, and neither is expressible with a parenthesised s. -->
      <p v-if="licenseState.offlineDaysRemaining != null" class="popover-detail">
        {{ t('license.offlineDays', licenseState.offlineDaysRemaining) }}
      </p>

      <template
        v-if="
          licenseState.status === 'active' ||
          licenseState.status === 'offline_tolerance' ||
          licenseState.status === 'offline_expiring'
        "
      >
        <p class="popover-detail success">
          <ShieldCheck :size="13" /> {{ t('license.activeHere') }}
        </p>
        <AppButton variant="danger" class="mt-1" @click="deactivateLicense">
          {{ t('license.deactivate') }}
        </AppButton>
      </template>

      <!-- No activation form here. `not_activated` and `blocked` are hard
           blocks (isHardBlocked in store/license.ts): LicenseActivationView
           takes over the whole window, so this popover is unreachable in
           exactly the states a form would serve. What is left for it to say is
           whether the licence is working — and, when it is not, why. -->
      <p v-else-if="licenseState.error" class="popover-error">{{ licenseState.error }}</p>
    </div>
  </div>
</template>

<style scoped>
.license-widget {
  position: relative;
}

.license-pill {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
  height: 34px;
  padding: 0 12px;
  border-radius: var(--radius-full);
  border: 1px solid var(--surface-border-soft);
  background: var(--surface-1);
  color: var(--text-secondary);
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
  cursor: pointer;
  white-space: nowrap;
}

.license-pill:hover {
  background: var(--surface-2);
}

.tone-success {
  color: var(--color-success);
  border-color: var(--color-success-soft);
  background: var(--color-success-soft);
}

.tone-warning {
  color: var(--color-warning);
  border-color: var(--color-warning-soft);
  background: var(--color-warning-soft);
}

.tone-danger {
  color: var(--color-danger);
  border-color: var(--color-danger-soft);
  background: var(--color-danger-soft);
}

.license-popover {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 50;
  width: 260px;
  background: var(--surface-1);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}

.popover-title {
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.popover-text {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
}

.popover-detail {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: var(--fs-caption);
  color: var(--text-secondary);
}

.popover-detail.success {
  color: var(--color-success);
}

.popover-detail code {
  font-family: var(--font-mono);
  font-size: 11px;
}

.popover-label {
  font-size: 11px;
  font-weight: var(--fw-medium);
  color: var(--text-tertiary);
  margin-top: 4px;
}

.popover-input {
  background: var(--surface-2);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  padding: 7px 10px;
  font-size: var(--fs-caption);
  font-family: var(--font-mono);
}

.popover-hint {
  font-size: 11px;
  color: var(--text-tertiary);
}

.popover-detail.tone-success {
  color: var(--color-success);
}

.popover-detail.tone-warning {
  color: var(--color-warning);
}

.popover-detail.tone-danger {
  color: var(--color-danger);
}

.popover-error {
  font-size: 11px;
  color: var(--color-danger);
}
</style>
