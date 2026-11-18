<script setup lang="ts">
import { VProgressCircular } from "vuetify/components";

/** Indicador indeterminado compacto, no mesmo padrão do Painel de Equipamentos. */
const props = withDefaults(defineProps<{ size?: "sm" | "md"; label?: string }>(), {
  size: "md",
  label: undefined,
});
</script>

<template>
  <span
    class="loading-spinner"
    role="status"
    aria-live="polite"
    :aria-label="props.label || 'Carregando'"
  >
    <VProgressCircular
      indeterminate
      color="currentColor"
      :size="props.size === 'sm' ? 14 : 28"
      :width="props.size === 'sm' ? 2 : 3"
      aria-hidden="true"
    />
    <span v-if="props.label" class="loading-spinner-label" aria-hidden="true">{{ props.label }}</span>
  </span>
</template>

<style scoped>
.loading-spinner { display: inline-flex; align-items: center; gap: 8px; color: #748197; }
</style>
