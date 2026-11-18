<script setup lang="ts">
import type { ApexAxisChartSeries, ApexOptions } from "apexcharts";
import VueApexCharts from "vue3-apexcharts";
import { formatNumber } from "~/utils/format";

interface ChartPoint {
  label: string;
  key?: string;
  values: Record<string, number>;
}

interface ChartSeries {
  key: string;
  label: string;
  color: string;
}

const props = defineProps<{
  points: ChartPoint[];
  series: ChartSeries[];
}>();

const emit = defineEmits<{
  select: [payload: { point: ChartPoint; seriesKey?: string }];
}>();

const chartSeries = computed<ApexAxisChartSeries>(() =>
  props.series.map((item) => ({
    name: item.label,
    data: props.points.map((point) => point.values[item.key] ?? 0),
  })),
);

function selectSegment(seriesIndex: number, dataPointIndex: number): void {
  const point = props.points[dataPointIndex];
  if (!point) return;
  emit("select", { point, seriesKey: props.series[seriesIndex]?.key });
}

const chartOptions = computed<ApexOptions>(() => ({
  chart: {
    type: "bar",
    height: 500,
    stacked: true,
    fontFamily: "Manrope, sans-serif",
    foreColor: "#596579",
    toolbar: { show: true },
    zoom: { enabled: true },
    animations: {
      enabled: true,
      speed: 450,
      animateGradually: { enabled: false },
    },
    events: {
      dataPointSelection: (_event, _chartContext, config) => {
        if (!config) return;
        selectSegment(config.seriesIndex, config.dataPointIndex);
      },
    },
  },
  colors: props.series.map((item) => item.color),
  dataLabels: {
    enabled: false,
  },
  plotOptions: {
    bar: {
      horizontal: false,
      borderRadius: 8,
      borderRadiusApplication: "end",
      columnWidth: "62%",
    },
  },
  stroke: {
    show: true,
    width: 1,
    colors: ["#ffffff"],
  },
  fill: { opacity: 1 },
  states: {
    hover: {
      filter: { type: "darken", value: 0.28 },
    },
    active: {
      allowMultipleDataPointsSelection: false,
      filter: { type: "darken", value: 0.36 },
    },
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
    decimalsInFloat: 0,
    labels: {
      formatter: (value) => formatNumber(value, 0),
      style: { colors: ["#596579"], fontSize: "11px", fontWeight: 500 },
    },
  },
  grid: {
    borderColor: "#e2e7ed",
    strokeDashArray: 0,
    padding: { top: 2, right: 4, bottom: 0, left: 0 },
  },
  tooltip: {
    shared: true,
    intersect: false,
    theme: "light",
    style: { fontSize: "12px", fontFamily: "Manrope, sans-serif" },
    y: { formatter: (value) => `${formatNumber(value, 0)} contratos` },
  },
  legend: {
    show: true,
    position: "bottom",
    horizontalAlign: "center",
    fontSize: "12px",
    fontWeight: 600,
    labels: { colors: "#596579" },
    markers: { size: 6, shape: "circle", offsetX: -2 },
    itemMargin: { horizontal: 10, vertical: 4 },
    onItemClick: { toggleDataSeries: true },
  },
  responsive: [
    {
      breakpoint: 560,
      options: {
        chart: { height: 380 },
        plotOptions: { bar: { columnWidth: "72%" } },
        legend: { position: "bottom" },
      },
    },
  ],
}));
</script>

<template>
  <div class="stacked-column-chart">
    <VueApexCharts type="bar" height="500" :options="chartOptions" :series="chartSeries" />
    <p class="chart-hint">Clique em um segmento para ver os contratos correspondentes.</p>
  </div>
</template>

<style scoped>
.stacked-column-chart {
  min-height: 525px;
}

.chart-hint {
  margin: -4px 0 0;
  color: #7b8799;
  font-size: 11px;
  text-align: center;
}

.stacked-column-chart :deep(.apexcharts-canvas),
.stacked-column-chart :deep(.apexcharts-svg) {
  max-width: 100%;
}

.stacked-column-chart :deep(.apexcharts-toolbar button) {
  border-radius: 5px;
}

.stacked-column-chart :deep(.apexcharts-toolbar button:hover),
.stacked-column-chart :deep(.apexcharts-toolbar button:focus-visible),
.stacked-column-chart :deep(.apexcharts-toolbar button.apexcharts-selected) {
  background: #e6f2ff;
}

.stacked-column-chart :deep(.apexcharts-series),
.stacked-column-chart :deep(.apexcharts-legend-series) {
  cursor: pointer;
}

.stacked-column-chart :deep(.apexcharts-bar-area) {
  transition:
    opacity 160ms ease,
    filter 160ms ease,
    stroke-width 160ms ease;
}

.stacked-column-chart :deep(.apexcharts-bar-series:has(.apexcharts-bar-area:hover) .apexcharts-bar-area:not(:hover)) {
  opacity: 0.32 !important;
}

.stacked-column-chart :deep(.apexcharts-bar-area:hover) {
  opacity: 1 !important;
  filter: brightness(0.78) saturate(1.2) drop-shadow(0 4px 4px rgb(15 23 42 / 24%));
  stroke: #17324d;
  stroke-width: 2px;
}

.stacked-column-chart :deep(.apexcharts-tooltip) {
  border: 1px solid #c7d0dc;
  border-radius: 9px;
  box-shadow: 0 10px 24px rgb(15 23 42 / 20%);
}

.stacked-column-chart :deep(.apexcharts-tooltip-title) {
  border-bottom-color: #d9e0e8;
  background: #f3f6fa;
  color: #20324a;
  font-weight: 800;
}

@media (max-width: 560px) {
  .stacked-column-chart {
    min-height: 405px;
  }
}
</style>
