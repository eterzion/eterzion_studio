<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: number
    min?: number
    max?: number
    step?: number
    defaultValue?: number
    disabled?: boolean
    /** Accessible name for the range input. SettingRow renders its label as
        plain text with no `for`, so without this every slider is an unnamed
        control to a screen reader (FR-010 in specs/007-video-editor-player).
        Optional so existing call sites are unaffected. */
    ariaLabel?: string
  }>(),
  {
    min: 0,
    max: 100,
    step: 1,
    defaultValue: 0,
    disabled: false
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: number]
}>()

const dragging = ref(false)

const percent = computed(() => ((props.modelValue - props.min) / (props.max - props.min)) * 100)
const defaultPercent = computed(
  () => ((props.defaultValue - props.min) / (props.max - props.min)) * 100
)

/** Where the native thumb's CENTRE actually sits, as a CSS length.
 *
 * A range input's thumb doesn't travel the full track width: it's inset by half
 * a thumb at each end, so its centre goes from `thumbSize/2` to
 * `trackWidth - thumbSize/2`. Anything we paint ourselves (the fill, the
 * default marker, the drag tooltip) has to follow that same curve — using a raw
 * `percent%` makes them line up only at 50% and drift by up to half a thumb at
 * the extremes, which is what made the knob look detached from the bar.
 *
 *   centre = p%·W + thumb·(0.5 − p/100)
 *
 * `--thumb` is defined in the CSS below so the size has a single source of truth.
 */
function thumbCentre(p: number): string {
  return `calc(${p}% + ${(0.5 - p / 100).toFixed(5)} * var(--thumb))`
}

function onInput(e: Event): void {
  emit('update:modelValue', Number((e.target as HTMLInputElement).value))
}
</script>

<template>
  <div class="range-field" :class="{ disabled }">
    <div class="track-wrap">
      <div class="track">
        <div class="fill" :style="{ width: thumbCentre(percent) }" />
        <div
          class="default-marker"
          :style="{ left: thumbCentre(defaultPercent) }"
          :title="`Padrão: ${defaultValue}`"
        />
      </div>
      <input
        class="range-input"
        type="range"
        :aria-label="ariaLabel"
        :min="min"
        :max="max"
        :step="step"
        :value="modelValue"
        :disabled="disabled"
        @input="onInput"
        @pointerdown="dragging = true"
        @pointerup="dragging = false"
      />
      <div v-if="dragging && !disabled" class="tooltip" :style="{ left: thumbCentre(percent) }">
        {{ modelValue }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.range-field {
  /* Rendered thumb diameter. Everything that must line up with the thumb (the
     fill/marker/tooltip positions computed in the script, the input height, the
     runnable track) derives from this single value, and the thumb rules below
     pin `box-sizing: border-box` so this stays the REAL painted size — the app
     has a global border-box reset, so a `width:14px; border:3px` thumb paints
     14px, not 20px, and assuming otherwise threw both axes off. */
  --thumb: 14px;
  width: 100%;
}

.range-field.disabled {
  opacity: 0.6;
}

.range-field.disabled .range-input {
  cursor: not-allowed;
}

.track-wrap {
  position: relative;
  height: var(--thumb);
  display: flex;
  align-items: center;
}

.track {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: 4px;
  border-radius: var(--radius-full);
  background: var(--surface-3);
  transform: translateY(-50%);
}

.fill {
  height: 100%;
  border-radius: var(--radius-full);
  background: var(--color-primary);
}

.default-marker {
  position: absolute;
  top: 50%;
  width: 2px;
  height: 8px;
  background: var(--text-tertiary);
  transform: translate(-50%, -50%);
  border-radius: 1px;
}

/* The input is sized to the THUMB, not to the 4px visual track — the track
   people see is the absolutely-positioned `.track` div behind it. With the
   runnable track also --thumb tall, the thumb exactly fills it and lands
   centred without any margin-top nudging (Chromium versions disagree on how a
   thumb taller than its track is aligned, so relying on that was fragile). */
.range-input {
  position: relative;
  width: 100%;
  height: var(--thumb);
  margin: 0;
  appearance: none;
  background: transparent;
  cursor: pointer;
}

.range-input::-webkit-slider-thumb {
  appearance: none;
  box-sizing: border-box;
  width: var(--thumb);
  height: var(--thumb);
  border-radius: var(--radius-sm);
  background: #fff;
  border: 3px solid var(--color-primary);
  /* No offset needed: the runnable track is exactly --thumb tall too. */
  margin-top: 0;
  cursor: pointer;
}

.range-input::-moz-range-thumb {
  appearance: none;
  box-sizing: border-box;
  width: var(--thumb);
  height: var(--thumb);
  border-radius: var(--radius-sm);
  background: #fff;
  border: 3px solid var(--color-primary);
  /* No offset needed: the runnable track is exactly --thumb tall too. */
  margin-top: 0;
  cursor: pointer;
}

.range-input::-webkit-slider-runnable-track {
  height: var(--thumb);
  background: transparent;
}

.tooltip {
  position: absolute;
  bottom: 20px;
  transform: translateX(-50%);
  background: var(--surface-3);
  color: var(--text-primary);
  font-size: 11px;
  font-weight: var(--fw-semibold);
  padding: 2px 6px;
  border-radius: 4px;
  pointer-events: none;
  box-shadow: var(--shadow-sm);
  white-space: nowrap;
}
</style>
