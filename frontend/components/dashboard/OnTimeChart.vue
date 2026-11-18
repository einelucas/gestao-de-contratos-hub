<script setup lang="ts">
import type { ApexAxisChartSeries, ApexOptions } from "apexcharts";
import VueApexCharts from "vue3-apexcharts";
import type { ContractAlert, ContractSummary } from "~/types/api";
import { formatNumber, formatPercent } from "~/utils/format";

interface OnTimePart {
  key: ContractAlert;
  label: string;
  value: number;
  color: string;
  share: number;
}

const props = defineProps<{ kpis: ContractSummary["kpis"] }>();

const emit = defineEmits<{
  select: [item: { key: ContractAlert; label: string }];
}>();

const parts = computed<OnTimePart[]>(() => {
  const { regular, atencao, vencido, onTimeBase } = props.kpis;
  if (!onTimeBase) return [];

  // Status exclusivos: cada contrato entra em uma única faixa. "Em
  // regularização" é um recorte transversal e fica fora da barra para não
  // duplicar contratos que continuam vencidos ou em atenção.
  return [
    { key: "Regular" as const, label: "Regulares", value: regular, color: "#609346" },
    { key: "Atencao" as const, label: "Atenção", value: atencao, color: "#eaa239" },
    { key: "Vencido" as const, label: "Vencidos pendentes", value: vencido, color: "#c0392b" },
  ].map((part) => ({ ...part, share: (part.value / onTimeBase) * 100 }));
});

const chartSeries = computed<ApexAxisChartSeries>(() =>
  parts.value.map((part) => ({
    name: part.label,
    data: [part.value],
  })),
);

function selectSegment(seriesIndex: number): void {
  const part = parts.value[seriesIndex];
  if (!part) return;
  emit("select", { key: part.key, label: part.label });
}

const chartOptions = computed<ApexOptions>(() => ({
  chart: {
    type: "bar",
    height: 112,
    stacked: true,
    stackType: "100%",
    parentHeightOffset: 0,
    fontFamily: "Manrope, sans-serif",
    foreColor: "#5f6e82",
    toolbar: { show: false },
    animations: {
      enabled: true,
      speed: 450,
      animateGradually: { enabled: false },
    },
    events: {
      dataPointSelection: (_event, _chartContext, config) => {
        if (!config) return;
        selectSegment(config.seriesIndex);
      },
    },
  },
  colors: parts.value.map((part) => part.color),
  plotOptions: {
    bar: {
      horizontal: true,
      barHeight: "28%",
      borderRadius: 7,
      borderRadiusApplication: "end",
      borderRadiusWhenStacked: "last",
      dataLabels: { hideOverflowingLabels: true },
    },
  },
  dataLabels: {
    enabled: true,
    formatter: (_percentage, options) => {
      const part = parts.value[options?.seriesIndex ?? -1];
      return part && part.share >= 8 ? formatNumber(part.value, 0) : "";
    },
    style: {
      fontSize: "10.5px",
      fontFamily: "Manrope, sans-serif",
      fontWeight: 800,
      colors: ["#ffffff"],
    },
    background: { enabled: false },
  },
  stroke: {
    show: false,
    width: 0,
  },
  fill: { opacity: 1 },
  states: {
    hover: { filter: { type: "lighten", value: 0.08 } },
    active: {
      allowMultipleDataPointsSelection: false,
      filter: { type: "lighten", value: 0.12 },
    },
  },
  xaxis: {
    categories: ["Contratos ativos com data"],
    min: 0,
    max: 100,
    labels: { show: false },
    axisBorder: { show: false },
    axisTicks: { show: false },
    tooltip: { enabled: false },
  },
  yaxis: { show: false },
  grid: {
    show: false,
    padding: { top: -18, right: 0, bottom: -18, left: 0 },
  },
  tooltip: {
    shared: false,
    intersect: true,
    theme: "light",
    style: { fontSize: "12px", fontFamily: "Manrope, sans-serif" },
    x: { show: false },
    y: {
      formatter: (value) => `${formatNumber(Number(value ?? 0), 0)} contratos`,
      title: { formatter: (seriesName) => `${seriesName}: ` },
    },
  },
  legend: {
    show: true,
    position: "bottom",
    horizontalAlign: "center",
    offsetY: 4,
    fontSize: "11px",
    fontWeight: 500,
    labels: { colors: "#5f6e82" },
    markers: { size: 5, shape: "circle", offsetX: -2 },
    itemMargin: { horizontal: 8, vertical: 2 },
    formatter: (seriesName, options) => {
      const part = parts.value[options?.seriesIndex ?? -1];
      return `${seriesName}: ${formatNumber(part?.value ?? 0, 0)}`;
    },
    onItemClick: { toggleDataSeries: true },
    onItemHover: { highlightDataSeries: true },
  },
}));
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

    <VueApexCharts
      v-if="parts.length"
      class="on-time-apex-chart"
      type="bar"
      height="112"
      :options="chartOptions"
      :series="chartSeries"
    />

  </section>
</template>

<style scoped>
.on-time-card {
  display: grid;
  gap: 2px;
  padding: 16px 18px 10px;
}

.on-time-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.on-time-head strong {
  margin-right: 10px;
  color: #4a7b36;
  font-size: 26px;
  font-weight: 850;
}

.on-time-head strong.bad {
  color: #a76b11;
}

.on-time-head span {
  color: #4b5b70;
  font-size: 12px;
  font-weight: 700;
}

.on-time-head > small {
  color: #8a97ab;
  font-size: 11px;
}

.on-time-apex-chart {
  min-height: 112px;
  margin: -2px 0 -5px;
}

.on-time-apex-chart :deep(.apexcharts-series),
.on-time-apex-chart :deep(.apexcharts-legend-series) {
  cursor: pointer;
}

.on-time-apex-chart :deep(g.apexcharts-series[seriesName="Regulares"] .apexcharts-bar-area) {
  clip-path: inset(0 round 7px 0 0 7px);
}

.on-time-apex-chart :deep(.apexcharts-tooltip) {
  border: 1px solid #c7d0dc;
  border-radius: 9px;
  box-shadow: 0 10px 24px rgb(15 23 42 / 20%);
}

@media (max-width: 700px) {
  .on-time-card {
    padding-inline: 14px;
  }

  .on-time-head strong {
    display: block;
    margin-bottom: 2px;
    font-size: 23px;
  }
}
</style>
