<script setup lang="ts">
import type { ContractAlert } from "~/types/api";
const props = defineProps<{ alert: ContractAlert; situation?: string }>();
// "Sem data" não é mais exibido como status: contratos sem vigência aparecem
// sem badge, e novos cadastros passam a exigir as datas.
const label = computed(() => {
  if (props.alert === "SemData") return "";
  if (props.alert === "Regularizacao") return "Em regularização";
  if (props.alert === "Atencao") return "Atenção";
  return props.alert;
});
</script>
<template><span v-if="label" class="contract-status" :class="`status-${alert.toLowerCase()}`">{{ label }}</span></template>

<style scoped>.status-regularizacao { background: #e7f0ff; color: #245fa9; border: 1px solid #bad1f3; }</style>
