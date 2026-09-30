<script setup lang="ts">
import type { ContractAlert } from "~/types/api";
const props = defineProps<{ alert: ContractAlert; situation?: string }>();
const label = computed(() => props.alert === "Atencao" ? "Atenção" : props.alert === "SemData" ? "Sem data" : props.alert);
</script>
<template><span class="contract-status" :class="`status-${alert.toLowerCase()}`">{{ label }}</span></template>
