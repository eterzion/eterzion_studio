<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { KeyRound, ShieldCheck, ShieldAlert, ShieldQuestion, Loader2 } from '@lucide/vue'
import { licenseState, deactivateLicense } from '../store/license'
import AppButton from './atoms/AppButton.vue'
import ProgressBar from './atoms/ProgressBar.vue'

const { t } = useI18n()

const open = ref(false)
// Desativar libera a instalacao e devolve o app a' tela de ativacao: e' a unica
// acao daqui que deixa o app inutilizavel. Por isso o clique so' pede
// confirmacao, e a confirmacao some quando o popover fecha -- reabrir nunca
// encontra o passo final ja' armado.
const confirming = ref(false)
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

const canDeactivate = computed(
  () =>
    licenseState.status === 'active' ||
    licenseState.status === 'offline_tolerance' ||
    licenseState.status === 'offline_expiring'
)

const installationsPercent = computed(() =>
  licenseState.installationsLimit
    ? Math.min(100, (licenseState.installationsUsed / licenseState.installationsLimit) * 100)
    : 0
)

watch(open, (isOpen) => {
  if (!isOpen) confirming.value = false
})

function confirmDeactivate(): void {
  confirming.value = false
  open.value = false
  void deactivateLicense()
}

function onDocClick(e: MouseEvent): void {
  if (open.value && root.value && !root.value.contains(e.target as Node)) open.value = false
}
function onKeydown(e: KeyboardEvent): void {
  if (open.value && e.key === 'Escape') open.value = false
}
onMounted(() => {
  document.addEventListener('mousedown', onDocClick)
  document.addEventListener('keydown', onKeydown)
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onDocClick)
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div ref="root" class="license-widget">
    <button
      class="license-pill"
      :class="'tone-' + meta.tone"
      type="button"
      :title="t('license.title')"
      :aria-expanded="open"
      @click="open = !open"
    >
      <component
        :is="meta.icon"
        :size="14"
        :class="{ 'animate-spin': licenseState.status === 'checking' }"
      />
      <span class="license-pill-label">{{ meta.label }}</span>
    </button>

    <div v-if="open" class="license-popover" role="dialog" :aria-label="t('license.title')">
      <p class="popover-title">{{ t('license.title') }}</p>

      <!-- O estado em palavras, em destaque. Sem ele o popover poderia abrir
           mostrando so' o titulo: instalacoes, dias offline e o botao de
           desativar sao todos condicionais, e nenhum vale para, digamos, uma
           licenca que simplesmente nao esta' configurada. -->
      <div class="status-box" :class="'tone-' + meta.tone">
        <component
          :is="meta.icon"
          :size="16"
          :class="{ 'animate-spin': licenseState.status === 'checking' }"
        />
        <span>{{ meta.label }}</span>
      </div>

      <!-- Qual licenca esta' ativa aqui: o final da chave e o e-mail da compra.
           So' aparecem quando o servidor de licencas respondeu nesta sessao. -->
      <dl v-if="licenseState.licenseLast4 || licenseState.email" class="license-facts">
        <template v-if="licenseState.licenseLast4">
          <dt>{{ t('license.keyLabel') }}</dt>
          <dd class="license-key">••••{{ licenseState.licenseLast4 }}</dd>
        </template>
        <template v-if="licenseState.email">
          <dt>{{ t('license.emailLabel') }}</dt>
          <dd :title="licenseState.email">{{ licenseState.email }}</dd>
        </template>
      </dl>

      <div v-if="licenseState.installationsLimit" class="popover-section">
        <div class="section-row">
          <span class="section-label">{{ t('license.installationsLabel') }}</span>
          <span class="section-value">
            {{
              t('license.installationsOf', {
                used: licenseState.installationsUsed,
                limit: licenseState.installationsLimit
              })
            }}
          </span>
        </div>
        <ProgressBar :value="installationsPercent" tone="neutral" />
      </div>

      <!-- Pluralizado em vez de "dia(s)": o russo precisa de tres formas e o
           japones de nenhuma, e nenhum dos dois cabe num "s" entre parenteses. -->
      <p v-if="licenseState.offlineDaysRemaining != null" class="popover-detail">
        {{ t('license.offlineDays', licenseState.offlineDaysRemaining) }}
      </p>

      <div v-if="canDeactivate" class="popover-section deactivate">
        <template v-if="!confirming">
          <p class="popover-hint">{{ t('license.deactivateHint') }}</p>
          <AppButton variant="outline" size="sm" @click="confirming = true">
            {{ t('license.deactivate') }}
          </AppButton>
        </template>
        <template v-else>
          <p class="popover-warning">{{ t('license.deactivateConfirm') }}</p>
          <div class="confirm-actions">
            <AppButton variant="ghost" size="sm" @click="confirming = false">
              {{ t('license.cancel') }}
            </AppButton>
            <AppButton variant="danger" size="sm" @click="confirmDeactivate">
              {{ t('license.deactivateConfirmAction') }}
            </AppButton>
          </div>
        </template>
      </div>

      <!-- Sem formulario de ativacao aqui. `not_activated` e `blocked` sao
           bloqueios totais (isHardBlocked em store/license.ts): a
           LicenseActivationView ocupa a janela inteira, entao este popover e'
           inalcancavel justamente nos estados que um formulario serviria. O que
           sobra para ele dizer e' se a licenca esta' funcionando -- e, quando
           nao esta', por que. -->
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
  padding: 0 var(--space-2-5);
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
  top: calc(100% + var(--space-2));
  right: 0;
  z-index: 50;
  width: 300px;
  background: var(--surface-1);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-2-5);
}

.popover-title {
  font-size: var(--fs-label);
  font-weight: var(--fw-semibold);
  color: var(--text-primary);
}

.status-box {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-2-5);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text-secondary);
  font-size: var(--fs-label);
  font-weight: var(--fw-medium);
}

/* O tom do estado, repetido com mais especificidade: `.status-box` vem depois
   de `.tone-*` e, com a mesma especificidade, apagava a cor -- o bloco saia
   cinza com "Licenca ativa". */
.status-box.tone-success {
  color: var(--color-success);
  border-color: var(--color-success-soft);
  background: var(--color-success-soft);
}

.status-box.tone-warning {
  color: var(--color-warning);
  border-color: var(--color-warning-soft);
  background: var(--color-warning-soft);
}

.status-box.tone-danger {
  color: var(--color-danger);
  border-color: var(--color-danger-soft);
  background: var(--color-danger-soft);
}

.license-facts {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--space-1-5) var(--space-3);
  font-size: var(--fs-caption);
}

.license-facts dt {
  color: var(--text-tertiary);
}

.license-facts dd {
  min-width: 0;
  overflow: hidden;
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
  font-weight: var(--fw-medium);
}

.license-key {
  font-family: var(--font-mono);
  letter-spacing: 0.04em;
}

.popover-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}

.section-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-2);
}

.section-label {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
}

.section-value {
  font-size: var(--fs-caption);
  font-weight: var(--fw-medium);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.popover-detail {
  font-size: var(--fs-caption);
  color: var(--text-secondary);
}

.deactivate {
  padding-top: var(--space-2-5);
  border-top: 1px solid var(--surface-border-soft);
}

.popover-hint {
  font-size: var(--fs-caption);
  color: var(--text-tertiary);
}

.popover-warning {
  font-size: var(--fs-caption);
  color: var(--color-danger);
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}

.popover-error {
  font-size: var(--fs-caption);
  color: var(--color-danger);
}
</style>
