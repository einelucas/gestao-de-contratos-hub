<script setup lang="ts">
import type { Component } from "vue";

defineProps<{ label: string; value: number; active?: boolean; tone?: "default" | "good" | "bad"; icon: Component }>();
const emit = defineEmits<{ click: [] }>();
</script>
<template>
  <button type="button" class="metric-card contract-kpi has-icon" :class="[tone, { active }]" :aria-pressed="Boolean(active)" @click="emit('click')">
    <span class="metric-icon" aria-hidden="true"><component :is="icon" :size="17" /></span>
    <span class="label">{{ label }}</span><strong class="value">{{ value }}</strong>
  </button>
</template>
