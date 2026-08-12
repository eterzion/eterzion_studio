<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { KeyRound, ShieldCheck, ShieldAlert, ShieldQuestion, Loader2 } from '@lucide/vue'
import { licenseState, activateLicense, deactivateLicense } from '../store/license'

const open = ref(false)
const licenseInput = ref('')
const root = ref<HTMLElement | null>(null)

const meta = computed(() => {
  switch (licenseState.status) {
    case 'active':
      return { icon: ShieldCheck, label: 'Licença ativa', tone: 'success' }
    case 'offline_tolerance':
      return { icon: ShieldCheck, label: 'Ativa (offline)', tone: 'success' }
    case 'offline_expiring':
      return { icon: ShieldAlert, label: 'Verifique sua conexão', tone: 'warning' }
    case 'checking':
      return { icon: Loader2, label: 'Verificando…', tone: 'neutral' }
    case 'error':
      return { icon: ShieldAlert, label: 'Erro de licença', tone: 'danger' }
    case 'blocked':
      return { icon: ShieldAlert, label: 'Licença bloqueada', tone: 'danger' }
    case 'not_activated':
      return { icon: KeyRound, label: 'Não ativada', tone: 'warning' }
    default:
      return { icon: ShieldQuestion, label: 'Licenciamento', tone: 'neutral' }
  }
})

async function submit(): Promise<void> {
  if (!licenseInput.value.trim()) return
  await activateLicense(licenseInput.value.trim())
  if (licenseState.status === 'active') licenseInput.value = ''
}

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
      title="Licença"
      @click="open = !open"
    >
      <component :is="meta.icon" :size="14" :class="{ spin: licenseState.status === 'checking' }" />
      <span class="license-pill-label">{{ meta.label }}</span>
    </button>

    <div v-if="open" class="license-popover">
      <p class="popover-title">Licença</p>
      <p v-if="licenseState.installationsLimit" class="popover-detail">
        Instalações: {{ licenseState.installationsUsed }}/{{ licenseState.installationsLimit }}
      </p>
      <p v-if="licenseState.offlineDaysRemaining != null" class="popover-detail">
        Tolerância offline: {{ licenseState.offlineDaysRemaining }} dia(s) restante(s)
      </p>

      <template v-if="licenseState.status === 'active' || licenseState.status === 'offline_tolerance' || licenseState.status === 'offline_expiring'">
        <p class="popover-detail success">
          <ShieldCheck :size="13" /> Ativa nesta instalação
        </p>
        <button class="popover-btn danger" type="button" @click="deactivateLicense">
          Desativar nesta instalação
        </button>
      </template>

      <template v-else>
        <label class="popover-label" for="license-id-input">ID da licença</label>
        <input
          id="license-id-input"
          v-model="licenseInput"
          type="text"
          placeholder="lic_..."
          class="popover-input"
          :disabled="licenseState.status === 'checking'"
          @keydown.enter="submit"
        />
        <p class="popover-hint">Enviado por e-mail após a compra.</p>
        <p v-if="licenseState.error" class="popover-error">{{ licenseState.error }}</p>
        <button
          class="popover-btn primary"
          type="button"
          :disabled="!licenseInput.trim() || licenseState.status === 'checking'"
          @click="submit"
        >
          {{ licenseState.status === 'checking' ? 'Ativando…' : 'Ativar' }}
        </button>
      </template>
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
  gap: 6px;
  height: 34px;
  padding: 0 12px;
  border-radius: 999px;
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

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
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
  gap: 6px;
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

.popover-error {
  font-size: 11px;
  color: var(--color-danger);
}

.popover-btn {
  border: none;
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  font-size: var(--fs-caption);
  font-weight: var(--fw-semibold);
  cursor: pointer;
  margin-top: 4px;
}

.popover-btn.primary {
  background: var(--color-primary);
  color: #fff;
}

.popover-btn.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.popover-btn.danger {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}
</style>
