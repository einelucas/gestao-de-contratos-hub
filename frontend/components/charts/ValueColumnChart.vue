<script setup lang="ts">
import type { ApexAxisChartSeries, ApexOptions } from "apexcharts";
import VueApexCharts from "vue3-apexcharts";

interface ValuePoint {
  label: string;
  value: number | null;
}

const props = defineProps<{
  points: ValuePoint[];
}>();

const compactCurrency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  maximumFractionDigits: 1,
});

const fullCurrency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function fromThousands(value: number): number {
  return value * 1000;
}

function formatCompactValue(value: number): string {
  return compactCurrency.format(fromThousands(value));
}

const chartSeries = computed<ApexAxisChartSeries>(() => [
  {
    name: "Valor contratado",
    data: props.points.map((point) => point.value ?? 0),
  },
]);

const chartOptions = computed<ApexOptions>(() => ({
  chart: {
    type: "bar",
    height: 460,
    fontFamily: "Manrope, sans-serif",
    foreColor: "#596579",
    toolbar: { show: true },
    zoom: { enabled: true },
    animations: {
      enabled: true,
      speed: 500,
      animateGradually: { enabled: true, delay: 45 },
    },
  },
  colors: ["#304f7e"],
  plotOptions: {
    bar: {
      horizontal: false,
      columnWidth: "52%",
      borderRadius: 7,
      borderRadiusApplication: "end",
      dataLabels: { position: "top" },
    },
  },
  dataLabels: {
    enabled: true,
    offsetY: -18,
    formatter: (value) => formatCompactValue(Number(value)),
    style: {
      fontSize: "11px",
      fontFamily: "Manrope, sans-serif",
      fontWeight: 750,
      colors: ["#253c59"],
    },
    background: { enabled: false },
  },
  stroke: {
    show: true,
    width: 1,
    colors: ["#ffffff"],
  },
  fill: { opacity: 1 },
  states: {
    hover: { filter: { type: "darken", value: 0.22 } },
    active: { filter: { type: "darken", value: 0.3 } },
  },
  xaxis: {
    categories: props.points.map((point) => point.label),
    labels: {
      trim: true,
      hideOverlappingLabels: true,
      style: { colors: "#596579", fontSize: "11px", fontWeight: 500 },
    },
    axisBorder: { show: true, color: "#cbd2dc" },
    axisTicks: { show: true, color: "#cbd2dc" },
  },
  yaxis: {
    min: 0,
    forceNiceScale: true,
    labels: {
      formatter: (value) => formatCompactValue(value),
      style: { colors: ["#596579"], fontSize: "11px", fontWeight: 500 },
    },
    title: {
      text: "Valor total contratado",
      style: { color: "#718096", fontSize: "11px", fontWeight: 650 },
    },
  },
  grid: {
    borderColor: "#e2e7ed",
    strokeDashArray: 0,
    padding: { top: 24, right: 10, bottom: 0, left: 4 },
  },
  tooltip: {
    theme: "light",
    style: { fontSize: "12px", fontFamily: "Manrope, sans-serif" },
    y: {
      formatter: (value) => fullCurrency.format(fromThousands(Number(value ?? 0))),
      title: { formatter: () => "Valor: " },
    },
  },
  legend: { show: false },
  responsive: [
    {
      breakpoint: 700,
      options: {
        chart: { height: 390 },
        plotOptions: { bar: { columnWidth: "68%" } },
        dataLabels: { style: { fontSize: "10px" } },
        yaxis: { title: { text: undefined } },
      },
    },
  ],
}));
</script>

<template>
  <div class="value-column-chart">
    <VueApexCharts type="bar" height="460" :options="chartOptions" :series="chartSeries" />
  </div>
</template>

<style scoped>
.value-column-chart {
  min-height: 460px;
}

.value-column-chart :deep(.apexcharts-canvas),
.value-column-chart :deep(.apexcharts-svg) {
  max-width: 100%;
}

.value-column-chart :deep(.apexcharts-toolbar button) {
  border-radius: 5px;
}

.value-column-chart :deep(.apexcharts-toolbar button:hover),
.value-column-chart :deep(.apexcharts-toolbar button:focus-visible),
.value-column-chart :deep(.apexcharts-toolbar button.apexcharts-selected) {
  background: #e6f2ff;
}

.value-column-chart :deep(.apexcharts-bar-area) {
  transition:
    opacity 160ms ease,
    filter 160ms ease,
    stroke-width 160ms ease;
}

.value-column-chart :deep(.apexcharts-bar-series:has(.apexcharts-bar-area:hover) .apexcharts-bar-area:not(:hover)) {
  opacity: 0.3 !important;
}

.value-column-chart :deep(.apexcharts-bar-area:hover) {
  opacity: 1 !important;
  filter: brightness(0.82) saturate(1.15) drop-shadow(0 4px 4px rgb(15 23 42 / 22%));
  stroke: #17324d;
  stroke-width: 2px;
}

.value-column-chart :deep(.apexcharts-tooltip) {
  border: 1px solid #c7d0dc;
  border-radius: 9px;
  box-shadow: 0 10px 24px rgb(15 23 42 / 20%);
}

.value-column-chart :deep(.apexcharts-tooltip-title) {
  border-bottom-color: #d9e0e8;
  background: #f3f6fa;
  color: #20324a;
  font-weight: 800;
}

@media (max-width: 700px) {
  .value-column-chart {
    min-height: 390px;
  }
}
</style>
