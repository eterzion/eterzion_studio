<script setup lang="ts">
import { Clock3, Files, HardDrive, Sparkles } from '@lucide/vue'
defineProps<{
  fileCount: number
  totalSizeLabel: string
  statusLabel: string
  qualityLabel: string
}>()
</script>

<template>
  <div class="summary-grid">
    <article class="summary-card tone-blue">
      <div class="summary-card-top">
        <div class="summary-icon icon-chip"><Files :size="28" :stroke-width="1.75" /></div>
        <div class="summary-copy">
          <div class="summary-value">{{ fileCount }}</div>
          <div class="summary-label">Arquivos na fila</div>
        </div>
      </div>
    </article>
    <article class="summary-card tone-green">
      <div class="summary-card-top">
        <div class="summary-icon icon-chip"><HardDrive :size="28" :stroke-width="1.75" /></div>
        <div class="summary-copy">
          <div class="summary-value">{{ totalSizeLabel }}</div>
          <div class="summary-label">Tamanho total</div>
        </div>
      </div>
    </article>
    <article class="summary-card tone-orange">
      <div class="summary-card-top">
        <div class="summary-icon icon-chip"><Clock3 :size="28" :stroke-width="1.75" /></div>
        <div class="summary-copy">
          <div class="summary-value">{{ statusLabel }}</div>
          <div class="summary-label">Status atual</div>
        </div>
      </div>
    </article>
    <article class="summary-card tone-purple">
      <div class="summary-card-top">
        <div class="summary-icon icon-chip"><Sparkles :size="29" :stroke-width="1.75" /></div>
        <div class="summary-copy">
          <div class="summary-value quality-value">{{ qualityLabel }}</div>
          <div class="summary-label">Qualidade e detalhes</div>
        </div>
      </div>
    </article>
  </div>
</template>

<style scoped>
.summary-grid {
  display: grid;
  grid-template-columns: 1fr 0.98fr 0.94fr 1.13fr;
  gap: 14px;
}
.summary-card {
  --tone: #1688ff;
  display: flex;
  min-width: 0;
  flex-direction: column;
  justify-content: center;
  padding: 16px 17px;
  border: 1px solid var(--surface-border);
  border-radius: 10px;
  background: var(--surface-1);
}
.tone-green {
  --tone: #35dd31;
}
.tone-orange {
  --tone: #ff7417;
}
.tone-purple {
  --tone: #bd30eb;
}
.summary-card-top {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 14px;
}
.summary-icon {
  --chip-tone: var(--tone);
  width: 51px;
  height: 54px;
  border-radius: 9px;
}
.summary-copy {
  min-width: 0;
}
.summary-value {
  overflow: hidden;
  color: var(--text-primary);
  font-size: clamp(17px, 1.4vw, 20px);
  font-weight: 620;
  line-height: 1.2;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.quality-value {
  font-size: clamp(15px, 1.2vw, 18px);
}
.summary-label {
  margin-top: 7px;
  color: var(--text-secondary);
  font-size: clamp(12px, 1.05vw, 15px);
  line-height: 1.15;
  white-space: nowrap;
}
@media (max-width: 920px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 650px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
