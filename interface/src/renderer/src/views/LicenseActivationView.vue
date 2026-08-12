<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  KeyRound,
  Loader2,
  Copy,
  XCircle,
  RefreshCw,
  HelpCircle,
  Package,
  ArrowRight
} from '@lucide/vue'
import {
  licenseState,
  activateLicense,
  deactivateLicense,
  refreshLicenseStatus
} from '../store/license'

// T039: rendered by App.vue INSTEAD of the whole app shell (no sidebar)
// whenever isHardBlocked() is true — before the first successful check this
// session, or once a status is confirmed bad (not_activated/blocked). Never
// touches files already on disk (FR-059/SC-019), it only gates new work.

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

const STATUS_COPY: Record<string, { title: string; body: string }> = {
  not_activated: {
    title: 'Ative sua licença',
    body: 'Este produto ainda não foi ativado nesta instalação. Informe o ID da licença enviado por e-mail após a compra.'
  },
  blocked: {
    title: 'Licença bloqueada',
    body: 'Sua licença não está mais ativa, ou o período de uso offline expirou. Verifique o status da sua assinatura ou conecte-se à internet para revalidar.'
  },
  error: {
    title: 'Não foi possível verificar sua licença',
    body: 'Ocorreu um erro ao consultar o status da licença. Verifique sua conexão com a internet e tente novamente.'
  },
  checking: {
    title: 'Verificando sua licença…',
    body: 'Só um instante.'
  }
}

const copy = computed(() => STATUS_COPY[licenseState.status] ?? STATUS_COPY.error)
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
            :class="{ spin: licenseState.status === 'checking' }"
            class="license-icon"
          />
        </div>
        <h1>{{ copy.title }}</h1>
        <p class="license-body">{{ copy.body }}</p>
      </div>

      <template v-if="licenseState.status !== 'checking'">
        <hr class="divider" />

        <div class="field-group">
          <label class="field-label" for="activation-license-id">ID da licença</label>
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
            <button
              class="copy-btn"
              type="button"
              title="Copiar"
              :disabled="!licenseInput.trim()"
              @click="copyInput"
            >
              <Copy :size="14" />
            </button>
          </div>
          <p v-if="copied" class="copied-hint">Copiado!</p>
        </div>

        <div v-if="licenseState.status === 'error'" class="fetch-error-box">
          <XCircle :size="18" class="fetch-error-icon" />
          <div>
            <p class="fetch-error-title">Falha ao buscar informações</p>
            <p class="fetch-error-detail">
              {{
                licenseState.error ??
                'Não foi possível conectar aos nossos servidores. Verifique sua conexão e tente novamente.'
              }}
            </p>
          </div>
        </div>

        <div class="actions-group">
          <button
            v-if="isPrimaryActivate"
            class="primary-btn"
            type="button"
            :disabled="!licenseInput.trim()"
            @click="submit"
          >
            <ShieldCheck :size="16" /> Ativar
          </button>
          <button v-else class="primary-btn" type="button" @click="refreshLicenseStatus">
            <RefreshCw :size="16" /> Tentar novamente
          </button>

          <button class="secondary-btn" type="button" @click="openHelp">
            <HelpCircle :size="16" /> Precisa de ajuda?
          </button>
        </div>

        <hr class="divider" />

        <div class="release-row">
          <Package :size="18" class="release-icon" />
          <div class="release-text">
            <p class="release-title">Já ativou em outra instalação?</p>
            <p class="release-detail">Libere esta licença para utilizar aqui.</p>
          </div>
          <button class="release-link" type="button" @click="deactivateLicense">
            Liberar licença
            <ArrowRight :size="14" />
          </button>
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
  border: 1px solid var(--border-1, var(--surface-border-soft));
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
  border-radius: 50%;
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
  border-radius: 50%;
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
  border-radius: 50%;
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

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
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
  border: 1px solid var(--border-1, var(--surface-border-soft));
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

.copy-btn {
  flex-shrink: 0;
  background: transparent;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: 6px;
  border-radius: var(--radius-sm);
}

.copy-btn:hover:not(:disabled) {
  color: var(--text-primary);
  background: var(--surface-3);
}

.copy-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
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

.primary-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-sm);
  padding: 11px;
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  cursor: pointer;
}

.primary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.secondary-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  padding: 10px;
  font-size: var(--fs-label);
  font-weight: var(--fw-medium);
  cursor: pointer;
}

.secondary-btn:hover {
  background: var(--surface-2);
  color: var(--text-primary);
}

.release-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  text-align: left;
}

.release-icon {
  flex-shrink: 0;
  color: var(--text-tertiary);
}

.release-text {
  flex: 1;
  min-width: 0;
}

.release-title {
  margin: 0;
  font-size: var(--fs-body-sm);
  font-weight: var(--fw-medium);
  color: var(--text-primary);
}

.release-detail {
  margin: 0;
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
}

.release-link {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  color: var(--color-primary);
  font-size: var(--fs-body-sm);
  font-weight: var(--fw-medium);
  cursor: pointer;
}

.release-link:hover {
  text-decoration: underline;
}
</style>
