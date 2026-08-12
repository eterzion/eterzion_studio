<script setup lang="ts">
import { Loader2 } from '@lucide/vue'

withDefaults(defineProps<{ size?: number }>(), { size: 18 })
</script>

<template>
  <Loader2 :size="size" class="animate-spin" />
</template>
