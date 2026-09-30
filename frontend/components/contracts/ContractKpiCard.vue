<script setup lang="ts">
defineProps<{ label: string; value: number; active?: boolean; tone?: string }>();
const emit = defineEmits<{ click: [] }>();
</script>
<template>
  <button type="button" class="contract-kpi" :class="[tone, { active }]" @click="emit('click')">
    <span>{{ label }}</span><strong>{{ value }}</strong>
  </button>
</template>
