<script setup lang="ts">
import type { ContractAlert } from "~/types/api";
const props = defineProps<{ alert: ContractAlert; situation?: string }>();
const label = computed(() => props.alert === "Regularizacao" ? "Em regularização" : props.alert === "Atencao" ? "Atenção" : props.alert === "SemData" ? "Sem data" : props.alert);
</script>
<template><span class="contract-status" :class="`status-${alert.toLowerCase()}`">{{ label }}</span></template>

<style scoped>.status-regularizacao { background: #e7f0ff; color: #245fa9; border: 1px solid #bad1f3; }</style>
