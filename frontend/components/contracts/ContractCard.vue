<script setup lang="ts">
import { AlarmClock, Building2, CalendarDays, FileText } from "lucide-vue-next";
import type { Contract } from "~/types/api";
import { dateBr, money, overdueDays, overdueLabel } from "~/utils/contracts";
const props = defineProps<{ contract: Contract; list?: boolean }>();
const emit = defineEmits<{ select: [contract: Contract] }>();
const lateDays = computed(() => overdueDays(props.contract));
</script>
<template>
  <button type="button" class="contract-card" :class="{ 'is-list': list }" @click="emit('select', contract)">
    <div class="contract-card-head">
      <div><span class="contract-number">Contrato {{ contract.contractNumber }}</span><h3>{{ contract.supplier }}</h3></div>
      <ContractStatusBadge :alert="contract.alert" :situation="contract.situation" />
    </div>
    <p class="contract-service">{{ contract.serviceDescription || 'Prestação não informada' }}</p>
    <div class="contract-card-meta">
      <span><Building2 class="size-4" />{{ contract.unit || 'Sem unidade' }}</span>
      <span><CalendarDays class="size-4" />{{ dateBr(contract.endDate) }}</span>
      <span><FileText class="size-4" />{{ money(contract.totalValue) }}</span>
      <span v-if="lateDays !== null" class="contract-overdue"><AlarmClock class="size-4" />{{ overdueLabel(lateDays) }}</span>
    </div>
  </button>
</template>
