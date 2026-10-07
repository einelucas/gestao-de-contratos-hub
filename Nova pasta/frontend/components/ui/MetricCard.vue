<script setup lang="ts">
import type { Component } from "vue";

withDefaults(defineProps<{ label: string; value: string; detail?: string; tone?: "default" | "good" | "bad"; icon?: Component }>(), {
  detail: "",
  tone: "default",
  icon: undefined,
});
</script>

<template>
  <article class="metric-card" :class="[tone, { 'has-icon': icon }]">
    <span v-if="icon" class="metric-icon" aria-hidden="true"><component :is="icon" :size="17" /></span>
    <div class="label">{{ label }}</div>
    <div class="value">{{ value }}</div>
    <div v-if="detail" class="detail">{{ detail }}</div>
  </article>
</template>
