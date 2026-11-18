<script setup lang="ts">
import { computed } from "vue";
import { VSkeletonLoader } from "vuetify/components";

/** Placeholder de carregamento padronizado com o Vuetify. */
const props = withDefaults(defineProps<{ lines?: number; rows?: number }>(), {
  lines: 0,
  rows: 0,
});
const lineType = computed(() => `text@${props.lines}`);
const rowType = computed(() => `table-row-divider@${props.rows}`);
</script>

<template>
  <div class="skeleton-block" aria-hidden="true">
    <VSkeletonLoader
      v-if="props.lines > 0"
      :type="lineType"
      class="skeleton-block--lines"
    />
    <VSkeletonLoader
      v-if="props.rows > 0"
      :type="rowType"
      class="skeleton-block--rows"
    />
  </div>
</template>

<style scoped>
.skeleton-block :deep(.v-skeleton-loader) { background: transparent; }
</style>
