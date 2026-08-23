<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { FolderOpen } from '@lucide/vue'
import AppSelect, { type SelectOption } from '../AppSelect.vue'
import AppButton from '../atoms/AppButton.vue'
import SettingRow from '../SettingRow.vue'
import SettingSwitch from '../SettingSwitch.vue'
import { api, hasNativeApi } from '../../services/native'
import type { CompressionExport, ConflictPolicy } from '../../services/compression'

// specs/008-compression-centre — T047: para onde vai, com que nome, e o que
// fazer quando já existe algo lá.
//
// **O padrão é renomear** (FR-030), e a escolha é deliberada: sobrescrever por
// padrão apagaria um arquivo que a pessoa não mandou apagar, e o único aviso
// seria depois do fato. Renomear custa um arquivo a mais no disco; sobrescrever
// custa o arquivo. Os dois erros não são simétricos.
//
// **A pasta padrão é a da origem, e o nome padrão nunca colide com ela**
// (Princípio XV) — o sufixo do padrão de nome é o que garante isso quando
// ninguém escolhe destino.

const props = defineProps<{ modelValue: CompressionExport }>()
const emit = defineEmits<{ 'update:modelValue': [CompressionExport] }>()

const { t } = useI18n()

const conflictOptions = computed<SelectOption[]>(() => [
  { value: 'rename', label: t('compression.export.conflict.rename') },
  { value: 'overwrite', label: t('compression.export.conflict.overwrite') },
  { value: 'ask', label: t('compression.export.conflict.ask') }
])

const directoryLabel = computed(
  () => props.modelValue.directory || t('compression.export.sameFolder')
)

function patch(mudanca: Partial<CompressionExport>): void {
  emit('update:modelValue', { ...props.modelValue, ...mudanca })
}

async function chooseDirectory(): Promise<void> {
  if (!hasNativeApi) return
  const escolhido = await api.selectOutputFolder(props.modelValue.directory ?? undefined)
  // `null` é cancelar, e cancelar tem que deixar como estava — tratá-lo como
  // "voltar ao padrão" desfaria uma escolha que a pessoa fez antes.
  if (escolhido) patch({ directory: escolhido })
}
</script>

<template>
  <div class="export-panel">
    <SettingRow :label="t('compression.export.destination')">
      <AppButton variant="outline" size="sm" @click="chooseDirectory">
        <FolderOpen :size="14" />
        {{ t('compression.export.choose') }}
      </AppButton>
    </SettingRow>
    <p class="destination-path" :title="directoryLabel">{{ directoryLabel }}</p>

    <SettingRow
      :label="t('compression.export.pattern')"
      :description="t('compression.export.patternHint')"
    >
      <input
        class="pattern-input"
        type="text"
        :value="modelValue.naming_pattern ?? '{filename}_compressed'"
        :aria-label="t('compression.export.pattern')"
        @change="patch({ naming_pattern: ($event.target as HTMLInputElement).value })"
      />
    </SettingRow>

    <SettingRow :label="t('compression.export.onConflict')">
      <AppSelect
        :model-value="modelValue.conflict_policy ?? 'rename'"
        :options="conflictOptions"
        @update:model-value="patch({ conflict_policy: $event as ConflictPolicy })"
      />
    </SettingRow>

    <SettingRow
      :label="t('compression.export.applyToAll')"
      :description="t('compression.export.applyToAllHint')"
      :divided="false"
    >
      <SettingSwitch
        :model-value="modelValue.apply_to_all ?? false"
        @update:model-value="patch({ apply_to_all: $event })"
      />
    </SettingRow>
  </div>
</template>

<style scoped>
.export-panel {
  display: flex;
  flex-direction: column;
}

.destination-path {
  margin: 0 0 var(--space-2);
  font-size: var(--fs-label-sm);
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pattern-input {
  width: 180px;
  padding: var(--space-1) var(--space-1-5);
  border: 1px solid var(--surface-border-soft);
  border-radius: var(--radius-sm);
  background: var(--surface-2);
  color: var(--text-primary);
  font-size: var(--fs-label);
}

.pattern-input:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 1px;
}
</style>
