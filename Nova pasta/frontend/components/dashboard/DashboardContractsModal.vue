<script setup lang="ts">
import type { Contract } from "~/types/api";
import { dateBr, daysToEndLabel } from "~/utils/contracts";

/**
 * Popup de drilldown dos gráficos do Dashboard — mostra exatamente os contratos
 * que compõem o dado clicado (status, unidade, faixa de prazo ou mês).
 */
defineProps<{
  open: boolean;
  title: string;
  contracts: Contract[];
  loading?: boolean;
  error?: string;
}>();
const emit = defineEmits<{ close: [] }>();
</script>

<template>
  <AppModal :open="open" :title="title" wide @close="emit('close')">
    <div class="drilldown-modal">
      <p class="drilldown-count">
        <template v-if="loading">Carregando…</template>
        <template v-else>{{ contracts.length }} contrato{{ contracts.length === 1 ? "" : "s" }}</template>
      </p>
      <div v-if="loading" class="history-empty">Carregando contratos…</div>
      <div v-else-if="error" class="contracts-state error">{{ error }}</div>
      <div v-else-if="!contracts.length" class="history-empty">Nenhum contrato encontrado.</div>
      <div v-else class="table-scroll drilldown-table-scroll">
        <table class="admin-table">
          <thead>
            <tr>
              <th>Situação</th>
              <th>Contrato</th>
              <th>Fornecedor</th>
              <th>Unidade</th>
              <th>Vencimento</th>
              <th>Prazo</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in contracts" :key="item.id">
              <td><ContractStatusBadge :alert="item.alert" /></td>
              <td><strong>{{ item.contractNumber }}</strong></td>
              <td>{{ item.supplier }}</td>
              <td>{{ item.unit || "—" }}</td>
              <td>{{ dateBr(item.endDate) }}</td>
              <td>{{ daysToEndLabel(item.daysToEnd) }}</td>
              <td>
                <NuxtLink
                  class="btn small"
                  :to="{ path: '/dashboard/contratos', query: { contrato: item.id } }"
                  @click="emit('close')"
                >
                  Abrir
                </NuxtLink>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </AppModal>
</template>

<style scoped>
.drilldown-modal {
  display: grid;
  gap: 10px;
  min-width: min(100%, 760px);
}
.drilldown-count {
  color: #5f6e82;
  font-size: 12px;
  font-weight: 700;
}
.drilldown-table-scroll {
  max-height: min(60vh, 520px);
  overflow-y: auto;
}
@media (max-width: 768px) {
  .drilldown-modal {
    min-width: 0;
  }
}
</style>
