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
        <div class="summary-icon"><Files :size="28" :stroke-width="1.75" /></div>
        <div class="summary-copy">
          <div class="summary-value">{{ fileCount }}</div>
          <div class="summary-label">Arquivos na fila</div>
        </div>
      </div>
      <div class="summary-track"><span /></div>
    </article>
    <article class="summary-card tone-green">
      <div class="summary-card-top">
        <div class="summary-icon"><HardDrive :size="28" :stroke-width="1.75" /></div>
        <div class="summary-copy">
          <div class="summary-value">{{ totalSizeLabel }}</div>
          <div class="summary-label">Tamanho total</div>
        </div>
      </div>
      <div class="summary-track"><span /></div>
    </article>
    <article class="summary-card tone-orange">
      <div class="summary-card-top">
        <div class="summary-icon"><Clock3 :size="28" :stroke-width="1.75" /></div>
        <div class="summary-copy">
          <div class="summary-value">{{ statusLabel }}</div>
          <div class="summary-label">Status atual</div>
        </div>
      </div>
      <div class="summary-track"><span /></div>
    </article>
    <article class="summary-card tone-purple">
      <div class="summary-card-top">
        <div class="summary-icon"><Sparkles :size="29" :stroke-width="1.75" /></div>
        <div class="summary-copy">
          <div class="summary-value quality-value">{{ qualityLabel }}</div>
          <div class="summary-label">Qualidade e detalhes</div>
        </div>
      </div>
      <div class="summary-track"><span /></div>
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
  --tone-dark: #084686;
  display: flex;
  min-width: 0;
  min-height: 120px;
  flex-direction: column;
  justify-content: space-between;
  padding: 16px 17px 18px;
  border: 1px solid #10263c;
  border-radius: 10px;
  background: linear-gradient(145deg, rgba(4, 16, 29, 0.96), rgba(3, 13, 24, 0.9));
}
.tone-green {
  --tone: #35dd31;
  --tone-dark: #08732c;
}
.tone-orange {
  --tone: #ff7417;
  --tone-dark: #b73c05;
}
.tone-purple {
  --tone: #bd30eb;
  --tone-dark: #7211bf;
}
.summary-card-top {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 14px;
}
.summary-icon {
  display: flex;
  width: 51px;
  height: 54px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  color: var(--tone);
  border-radius: 9px;
  background: color-mix(in srgb, var(--tone) 19%, #071221);
  filter: drop-shadow(0 0 8px color-mix(in srgb, var(--tone) 22%, transparent));
}
.summary-copy {
  min-width: 0;
}
.summary-value {
  overflow: hidden;
  color: #f8f8fa;
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
  color: #dce0e7;
  font-size: clamp(12px, 1.05vw, 15px);
  line-height: 1.15;
  white-space: nowrap;
}
.summary-track {
  height: 5px;
  overflow: hidden;
  border-radius: 999px;
  background: color-mix(in srgb, var(--tone-dark) 72%, #07121e);
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.4);
}
.summary-track span {
  display: block;
  width: 92%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(
    90deg,
    var(--tone),
    color-mix(in srgb, var(--tone) 72%, var(--tone-dark))
  );
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
