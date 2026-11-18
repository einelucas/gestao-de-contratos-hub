<script setup lang="ts">
import { VProgressLinear, VSkeletonLoader } from "vuetify/components";

withDefaults(defineProps<{
  label?: string;
  type?: string;
}>(), {
  label: "Carregando conteúdo",
  type: "heading, paragraph, table-heading, table-row-divider@5",
});
</script>

<template>
  <div class="content-loading" role="status" aria-live="polite" aria-busy="true" :aria-label="label">
    <VProgressLinear color="primary" height="3" indeterminate />
    <VSkeletonLoader :type="type" aria-hidden="true" />
  </div>
</template>

<style scoped>
.content-loading {
  width: 100%;
  min-height: 12rem;
  overflow: hidden;
  border-radius: 0.75rem;
  background: rgb(var(--v-theme-surface));
}

.content-loading :deep(.v-skeleton-loader) {
  padding: 1rem 0;
  background: transparent;
}
</style>
