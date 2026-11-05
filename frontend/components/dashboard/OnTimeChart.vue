<script setup lang="ts">
import type { ContractSummary } from "~/types/api";
import { formatPercent } from "~/utils/format";

const props = defineProps<{ kpis: ContractSummary["kpis"] }>();

const parts = computed(() => {
  const { regular, atencao, vencido, onTimeBase } = props.kpis;
  if (!onTimeBase) return [];

  // Status exclusivos: cada contrato entra em uma única faixa. "Em
  // regularização" é um recorte transversal e fica fora da barra para não
  // duplicar contratos que continuam vencidos ou em atenção.
  return [
    { label: "Regulares", value: regular, color: "#609346" },
    { label: "Atenção", value: atencao, color: "#eaa239" },
    { label: "Vencidos pendentes", value: vencido, color: "#c0392b" },
  ].map((part) => ({ ...part, width: (part.value / onTimeBase) * 100 }));
});

const regularizationCount = computed(() => props.kpis.regularizationWithDate ?? 0);
</script>

<template>
  <section class="surface on-time-card">
    <div class="on-time-head">
      <div>
        <strong :class="{ bad: kpis.onTimePercent < 80 }">{{ formatPercent(kpis.onTimePercent) }} em dia</strong>
        <span>{{ kpis.onTime }} de {{ kpis.onTimeBase }} contratos ativos com data</span>
      </div>
      <small>Contratos finalizados ficam fora do cálculo</small>
    </div>
    <div class="on-time-track">
      <span v-for="part in parts" :key="part.label" :style="{ width: `${part.width}%`, background: part.color }" :title="`${part.label}: ${part.value}`">{{ part.width >= 8 ? part.value : "" }}</span>
    </div>
    <div class="on-time-legend">
      <span v-for="part in parts" :key="part.label"><i :style="{ background: part.color }" />{{ part.label }}: {{ part.value }}</span>
      <span v-if="regularizationCount" class="regularization-note"><i />Em regularização: {{ regularizationCount }} <small>(recorte)</small></span>
    </div>
  </section>
</template>

<style scoped>
.on-time-card {
  padding: 16px 18px;
  display: grid;
  gap: 10px;
}
.on-time-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}
.on-time-head strong {
  color: #4a7b36;
  font-size: 26px;
  font-weight: 850;
  margin-right: 10px;
}
.on-time-head strong.bad {
  color: #a76b11;
}
.on-time-head span {
  color: #4b5b70;
  font-size: 12px;
  font-weight: 700;
}
.on-time-head small {
  color: #8a97ab;
  font-size: 11px;
}
.on-time-track {
  display: flex;
  height: 22px;
  overflow: hidden;
  border-radius: 999px;
  background: #eef1f5;
}
.on-time-track span {
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 10.5px;
  font-weight: 800;
  transition: width 0.3s ease;
}
.on-time-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  color: #5f6e82;
  font-size: 11px;
}
.on-time-legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.on-time-legend i {
  width: 9px;
  height: 9px;
  border-radius: 999px;
}
.on-time-legend .regularization-note i {
  background: #397ac1;
}
.on-time-legend .regularization-note small {
  color: #8a97ab;
  font-size: 10px;
}
</style>
