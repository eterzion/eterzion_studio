<script setup lang="ts">
import { ref } from 'vue'
import { ShieldAlert, ShieldCheck, KeyRound, Loader2 } from '@lucide/vue'
import { licenseState, activateLicense, deactivateLicense } from '../store/license'

// T039: rendered by App.vue INSTEAD of a media/processing screen whenever
// licenseState isn't usable (blocked/not_activated/checking/error) — never
// touches files already on disk (FR-059/SC-019), it only gates new work.

const licenseInput = ref('')

async function submit(): Promise<void> {
  if (!licenseInput.value.trim()) return
  await activateLicense(licenseInput.value.trim())
  if (licenseState.status === 'active') licenseInput.value = ''
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
    body: 'Ocorreu um erro ao consultar o status da licença. Verifique sua conexão e tente novamente.'
  },
  checking: {
    title: 'Verificando sua licença…',
    body: 'Só um instante.'
  }
}
</script>

<template>
  <div class="license-block">
    <div class="license-card">
      <component
        :is="licenseState.status === 'checking' ? Loader2 : licenseState.status === 'not_activated' ? KeyRound : ShieldAlert"
        :size="36"
        :class="{ spin: licenseState.status === 'checking' }"
        class="license-icon"
      />
      <h1>{{ (STATUS_COPY[licenseState.status] ?? STATUS_COPY.error).title }}</h1>
      <p class="license-body">{{ (STATUS_COPY[licenseState.status] ?? STATUS_COPY.error).body }}</p>

      <template v-if="licenseState.status !== 'checking'">
        <label class="field-label" for="activation-license-id">ID da licença</label>
        <input
          id="activation-license-id"
          v-model="licenseInput"
          type="text"
          placeholder="lic_..."
          class="license-input"
          @keydown.enter="submit"
        />
        <p v-if="licenseState.error" class="license-error">{{ licenseState.error }}</p>
        <button
          class="primary-btn"
          type="button"
          :disabled="!licenseInput.trim()"
          @click="submit"
        >
          <ShieldCheck :size="16" /> Ativar
        </button>
        <button class="link-btn" type="button" @click="deactivateLicense">
          Já ativou em outra instalação? Libere a vaga por aqui
        </button>
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
  flex: 1;
  min-width: 0;
  padding: var(--space-4);
}
.license-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  max-width: 380px;
  text-align: center;
  background: var(--surface-1);
  border: 1px solid var(--border-1);
  border-radius: var(--radius-md);
  padding: var(--space-6);
}
.license-icon {
  color: var(--color-warning, var(--text-secondary));
  margin-bottom: var(--space-2);
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
  font-size: var(--fs-h3, 1.25rem);
  margin: 0;
}
.license-body {
  color: var(--text-secondary);
  font-size: var(--fs-body-sm);
}
.field-label {
  align-self: flex-start;
  font-size: var(--fs-label);
  color: var(--text-secondary);
  margin-top: var(--space-3);
}
.license-input {
  width: 100%;
  background: var(--surface-2);
  border: 1px solid var(--border-1);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  padding: 8px 10px;
  font-family: var(--font-mono);
}
.license-error {
  color: var(--color-danger);
  font-size: var(--fs-body-sm);
}
.link-btn {
  background: none;
  border: none;
  color: var(--text-tertiary);
  font-size: var(--fs-caption);
  cursor: pointer;
  margin-top: var(--space-2);
}
</style>
