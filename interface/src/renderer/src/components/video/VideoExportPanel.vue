<script setup lang="ts">
import { computed, onMounted, ref, toRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { AlertTriangle, Download, FileOutput, FolderOpen, X } from '@lucide/vue'
import CollapsiblePanel from '../CollapsiblePanel.vue'
import SettingRow from '../SettingRow.vue'
import AppSelect from '../AppSelect.vue'
import AppButton from '../atoms/AppButton.vue'
import ProgressBar from '../atoms/ProgressBar.vue'
import SavedResultCard from '../SavedResultCard.vue'
import { videoExportChoices } from '../../store/exportChoices'
import {
  getVideoExportOptions,
  type ConflictMode,
  type VideoContainer,
  type VideoExportOptions
} from '../../services/api'
import { profileOptions } from '../../constants/processing'
import type { Profile } from '../../services/api'
import type { ProcessingState } from '../../composables/useVideoProcessing'

// T064/T072 (specs/007-video-editor-player) — FR-018, FR-027, FR-025.
//
// Availability comes from the backend, not from a hardcoded list. A container
// with no working encoder on this machine is disabled BEFORE it is chosen,
// rather than after an export fails — which is the whole point of FR-027 and
// the reason GET /video/export-options exists.

const props = defineProps<{
  state: ProcessingState | null
  /** Chosen in the view, which owns the native dialog. Held there rather than
      here so the button label reflects the real destination — a local ref would
      always have read "same folder" no matter what was picked. */
  directory: string | null
  /** Nome do video ativo, para o exemplo no campo de nome. */
  sourceName?: string | null
  disabled?: boolean
}>()

export interface VideoExportChoice {
  container: VideoContainer
  profile: Profile
  /** Sem extensao; `null` = o nome do original. */
  filename: string | null
  conflict: ConflictMode
}

const emit = defineEmits<{
  export: [payload: VideoExportChoice]
  cancel: []
  pickDirectory: []
}>()

const { t } = useI18n()

const profiles = computed(() => profileOptions())

const options = ref<VideoExportOptions | null>(null)
// Null until the options load, and again if they fail. Both cases mean the same
// thing to the template — nothing can be offered yet — so there is no separate
// error flag to fall out of sync with.
// As mesmas escolhas da tela (store/exportChoices.ts), para o painel mostrar o
// que esta' guardado ao voltar para o Video.
const escolhas = videoExportChoices()
const container = toRef(escolhas, 'container')
const profile = toRef(escolhas, 'profile')
// Nome e conflito com as regras da Imagem (app/destino.py): o nome do
// original, e o sufixo so' quando o destino cairia no proprio original.
const filename = ref<string | null>(null)
const conflict = toRef(escolhas, 'conflict')

// O nome digitado e' de um video; trocar de video volta ao nome do original.
watch(
  () => props.sourceName,
  () => (filename.value = null)
)

const conflictOptions = computed(() => [
  { value: 'rename', label: t('destination.conflict.rename') },
  { value: 'overwrite', label: t('destination.conflict.overwrite') },
  { value: 'ask', label: t('destination.conflict.ask') }
])

const namePlaceholder = computed(() =>
  props.sourceName ? `${props.sourceName.replace(/\.[^.]+$/, '')}.${container.value}` : ''
)

onMounted(async () => {
  try {
    options.value = await getVideoExportOptions()
    // Land on something usable rather than defaulting to mp4 and disabling the
    // button: on a machine with no hardware H.264 encoder, mp4 is exactly the
    // option that will not work.
    // So' quando o guardado nao serve aqui: voltar para a tela nao pode
    // desfazer a escolha da pessoa.
    const atual = options.value.containers.find((c) => c.value === container.value)
    const usable = options.value.containers.find((c) => c.available)
    if (!atual?.available && usable) container.value = usable.value
  } catch {
    options.value = null
  }
})

const containerOptions = computed(() =>
  (options.value?.containers ?? []).map((entry) => ({
    value: entry.value,
    label: entry.value.toUpperCase(),
    disabled: !entry.available,
    // A key, never an encoder name — Princípio V holds on this surface too.
    description: entry.available ? undefined : t('videoEditor.limits.noEncoderAvailable')
  }))
)

const nothingAvailable = computed(
  () => !!options.value && options.value.containers.every((c) => !c.available)
)

const running = computed(
  () =>
    props.state?.status === 'creating' ||
    props.state?.status === 'queued' ||
    props.state?.status === 'processing'
)

const refusalMessage = computed(() => {
  const refusal = props.state?.refusal
  if (!refusal) return null
  if (refusal.reason === 'ceiling_exceeded' && refusal.limitingFactor) {
    return t('videoEditor.limits.ceilingExceeded', {
      factor: t(`videoEditor.limits.factor_${refusal.limitingFactor}`)
    })
  }
  return t(`videoEditor.limits.${refusal.reason}`)
})
</script>

<template>
  <CollapsiblePanel
    :title="t('videoEditor.export.title')"
    :description="t('videoEditor.export.description')"
    :icon="FileOutput"
    open
  >
    <SettingRow :label="t('videoEditor.export.container')">
      <AppSelect
        v-model="container"
        :options="containerOptions"
        :disabled="disabled || running || nothingAvailable"
      />
    </SettingRow>

    <SettingRow :label="t('videoEditor.export.profile')">
      <AppSelect v-model="profile" :options="profiles" :disabled="disabled || running" />
    </SettingRow>

    <SettingRow :label="t('videoEditor.export.destination')">
      <AppButton
        variant="outline"
        size="sm"
        :disabled="disabled || running"
        @click="emit('pickDirectory')"
      >
        <template #icon><FolderOpen :size="14" /></template>
        {{ props.directory ?? t('videoEditor.export.sameFolder') }}
      </AppButton>
    </SettingRow>

    <SettingRow :label="t('destination.fileName')">
      <input
        class="name-input"
        type="text"
        :placeholder="namePlaceholder"
        :value="filename ?? ''"
        :disabled="disabled || running"
        :aria-label="t('destination.fileName')"
        @input="filename = ($event.target as HTMLInputElement).value.trim() || null"
      />
    </SettingRow>

    <SettingRow :label="t('destination.onConflict')">
      <AppSelect
        :model-value="conflict"
        :options="conflictOptions"
        :disabled="disabled || running"
        @update:model-value="conflict = $event as ConflictMode"
      />
    </SettingRow>

    <!-- FR-027, at the moment it helps: before choosing, not after failing. -->
    <p
      v-if="nothingAvailable"
      class="flex items-start gap-2 rounded border border-surface-border bg-surface-2 px-3 py-2 text-(length:--fs-caption) text-text-tertiary"
    >
      <AlertTriangle :size="14" class="mt-0.5 shrink-0" />
      {{ t('videoEditor.limits.noContainerAvailable') }}
    </p>
  </CollapsiblePanel>

  <!-- As acoes ficam abaixo de tudo, fora do painel, como o "Aplicar a todos"
       + "Processar" da Imagem. O slot recebe o "Aplicar a todos" da tela. -->
  <div class="export-actions">
    <slot name="before-actions" />

    <div v-if="running" class="flex flex-col gap-2">
      <ProgressBar :value="state?.progress ?? 0" />
      <div class="flex items-center justify-between gap-2">
        <span class="text-(length:--fs-caption) text-text-tertiary">
          {{ state?.stage ?? t('videoEditor.export.working') }}
        </span>
        <AppButton variant="ghost" size="sm" @click="emit('cancel')">
          <template #icon><X :size="14" /></template>
          {{ t('videoEditor.export.cancel') }}
        </AppButton>
      </div>
    </div>

    <AppButton
      v-else
      variant="primary"
      size="lg"
      class="w-full"
      :disabled="disabled || nothingAvailable"
      @click="emit('export', { container, profile, filename, conflict })"
    >
      <template #icon><Download :size="15" /></template>
      {{ t('videoEditor.export.start') }}
    </AppButton>

    <!-- FR-025: name the limiting factor. "Too big" tells a person nothing
         about what to change. -->
    <p
      v-if="refusalMessage"
      class="flex items-start gap-2 text-(length:--fs-caption) text-state-danger"
    >
      <AlertTriangle :size="14" class="mt-0.5 shrink-0" />
      {{ refusalMessage }}
    </p>

    <SavedResultCard
      v-else-if="state?.status === 'done' && state.outputPath"
      :path="state.outputPath"
    />
  </div>
</template>

<style scoped>
.export-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

/* O mesmo campo do padrao de nome da Compressao (CompressionExportPanel.vue). */
.name-input {
  width: min(180px, 100%);
  min-width: 0;
  padding: var(--space-1) var(--space-1-5);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text-primary);
  font-size: var(--fs-label);
}

.name-input:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}
</style>
