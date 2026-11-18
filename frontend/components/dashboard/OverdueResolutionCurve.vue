<script setup lang="ts">
import type { ApexAxisChartSeries, ApexOptions } from "apexcharts";
import ptBr from "apexcharts/dist/locales/pt-br.json";
import { TrendingDown } from "lucide-vue-next";
import VueApexCharts from "vue3-apexcharts";
import { VProgressLinear, VSkeletonLoader } from "vuetify/components";
import type { OverdueHistoryPoint, OverdueHistorySeries } from "~/types/api";
import { formatNumber } from "~/utils/format";

/** Histórico real e corporativo, com drill-down mantido pela página. */
const props = defineProps<{ reloadToken: number }>();
const emit = defineEmits<{
  select: [payload: { date: string; series: OverdueHistorySeries }];
}>();

const api = useApi();
const points = ref<OverdueHistoryPoint[]>([]);
const loading = ref(false);
const error = ref("");

let loadSeq = 0;
async function load(): Promise<void> {
  const seq = ++loadSeq;
  loading.value = true;
  error.value = "";
  try {
    const response = await api.get<{ items: OverdueHistoryPoint[] }>("/contratos/vencidos-historico");
    if (seq !== loadSeq) return;
    points.value = response.items;
  } catch (cause) {
    if (seq !== loadSeq) return;
    error.value = cause instanceof Error ? cause.message : "Não foi possível carregar o histórico.";
  } finally {
    if (seq === loadSeq) loading.value = false;
  }
}

onMounted(load);
watch(() => props.reloadToken, load);

const first = computed(() => points.value[0] ?? null);
const latest = computed(() => points.value[points.value.length - 1] ?? null);

function dateTimestamp(date: string): number {
  return new Date(`${date}T00:00:00`).getTime();
}

function formatDateLabel(date: string): string {
  return new Date(`${date}T00:00:00`).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
  });
}

function selectPoint(seriesIndex: number, dataPointIndex: number): void {
  const point = points.value[dataPointIndex];
  if (!point) return;

  const series: OverdueHistorySeries | undefined =
    seriesIndex === 0 ? "remaining" : seriesIndex === 1 ? "resolved" : undefined;
  if (series) emit("select", { date: point.date, series });
}

/**
 * O ApexCharts só fornece dataPointIndex ao clicar exatamente num marcador.
 * Como este gráfico usa linhas limpas (sem marcadores permanentes), converte o
 * X do clique no ponto de data mais próximo quando o clique cai no traçado.
 */
function selectNearestLinePoint(event: MouseEvent, chartContext: unknown): void {
  const target = event.target instanceof Element ? event.target : null;
  const seriesGroup = target?.closest<SVGGElement>(".apexcharts-series");
  const seriesIndex = Number(seriesGroup?.getAttribute("rel")) - 1;
  if (seriesIndex < 0 || seriesIndex > 1) return;

  const context = chartContext as {
    el?: Element;
    w?: { globals?: { minX?: number; maxX?: number } };
  };
  const grid = context.el?.querySelector<SVGElement>(".apexcharts-grid");
  const bounds = grid?.getBoundingClientRect();
  const minX = context.w?.globals?.minX;
  const maxX = context.w?.globals?.maxX;
  if (!bounds?.width || minX === undefined || maxX === undefined) return;

  const ratio = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
  const clickedTimestamp = minX + ratio * (maxX - minX);
  const nearest = points.value.reduce(
    (best, point, index) => {
      const distance = Math.abs(dateTimestamp(point.date) - clickedTimestamp);
      return distance < best.distance ? { index, distance } : best;
    },
    { index: -1, distance: Number.POSITIVE_INFINITY },
  );
  if (nearest.index >= 0) selectPoint(seriesIndex, nearest.index);
}

const chartSeries = computed<ApexAxisChartSeries>(() => [
  {
    name: "Vencidos restantes",
    data: points.value.map((point) => ({ x: dateTimestamp(point.date), y: point.remaining })),
  },
  {
    name: "Regularizações (acumulado)",
    data: points.value.map((point) => ({ x: dateTimestamp(point.date), y: point.resolved })),
  },
]);

const chartOptions = computed<ApexOptions>(() => ({
  chart: {
    id: "overdue-resolution-history",
    type: "line",
    height: 350,
    fontFamily: "Manrope, sans-serif",
    foreColor: "#596579",
    locales: [ptBr],
    defaultLocale: "pt-br",
    animations: {
      enabled: true,
      speed: 500,
      animateGradually: { enabled: false },
      dynamicAnimation: { enabled: true, speed: 350 },
    },
    toolbar: {
      show: true,
      offsetY: -4,
      tools: {
        download: true,
        selection: false,
        zoom: true,
        zoomin: true,
        zoomout: true,
        pan: true,
        reset: true,
      },
      export: {
        csv: {
          filename: "historico-vigencia-contratos-vencidos",
          headerCategory: "Data",
          headerValue: "Quantidade",
          categoryFormatter: (timestamp) =>
            timestamp === undefined ? "" : new Date(timestamp).toLocaleDateString("pt-BR"),
        },
        svg: { filename: "historico-vigencia-contratos-vencidos" },
        png: { filename: "historico-vigencia-contratos-vencidos" },
      },
      autoSelected: "zoom",
    },
    zoom: {
      enabled: true,
      type: "x",
      autoScaleYaxis: false,
      allowMouseWheelZoom: "auto",
    },
    events: {
      click: (event, chartContext, config) => {
        if (!config) return;
        if (config.seriesIndex >= 0 && config.dataPointIndex >= 0) {
          selectPoint(config.seriesIndex, config.dataPointIndex);
          return;
        }
        if (event instanceof MouseEvent) selectNearestLinePoint(event, chartContext);
      },
      markerClick: (_event, _chartContext, config) => {
        if (!config) return;
        selectPoint(config.seriesIndex, config.dataPointIndex);
      },
      dataPointSelection: (_event, _chartContext, config) => {
        if (!config) return;
        selectPoint(config.seriesIndex, config.dataPointIndex);
      },
    },
  },
  colors: ["#c0392b", "#4a7b36"],
  dataLabels: { enabled: false },
  stroke: { curve: "smooth", width: 4, lineCap: "round" },
  grid: {
    borderColor: "#e2e7ed",
    strokeDashArray: 0,
    padding: { top: 4, right: 12, bottom: 0, left: 8 },
  },
  markers: {
    size: points.value.length === 1 ? 5 : 0,
    strokeWidth: 0,
    hover: { size: 6, sizeOffset: 2 },
  },
  xaxis: {
    type: "datetime",
    tickAmount: Math.min(8, Math.max(2, points.value.length - 1)),
    labels: {
      datetimeUTC: false,
      format: "dd MMM",
      style: { colors: "#596579", fontSize: "11px", fontWeight: 500 },
    },
    axisBorder: { show: true, color: "#cbd2dc" },
    axisTicks: { show: true, color: "#cbd2dc" },
    tooltip: { enabled: false },
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
  tooltip: {
    enabled: true,
    shared: false,
    intersect: false,
    followCursor: false,
    x: { format: "dd MMM yyyy" },
    y: { formatter: (value) => `${formatNumber(value, 0)} contratos` },
    marker: { show: true },
  },
  legend: {
    show: true,
    position: "bottom",
    horizontalAlign: "center",
    fontSize: "12px",
    fontWeight: 600,
    labels: { colors: "#596579" },
    markers: { size: 6, shape: "circle", offsetX: -2 },
    itemMargin: { horizontal: 12, vertical: 4 },
  },
  noData: { text: "Nenhum histórico registrado." },
}));
</script>

<template>
  <DashboardCard
    title="Histórico de vigência dos Contratos Vencidos"
    subtitle="Indicador corporativo — todas as unidades. Não responde aos filtros acima. Histórico real, registrado no servidor a cada atualização do Dashboard."
    :icon="TrendingDown"
    class="span-2"
  >
    <div v-if="error" class="contracts-state error">{{ error }}</div>
    <div v-else-if="loading && !points.length" class="history-chart-loading" aria-busy="true" aria-label="Carregando histórico">
      <VProgressLinear color="primary" height="3" indeterminate />
      <VSkeletonLoader type="heading, paragraph, image" />
    </div>
    <div v-else-if="!points.length" class="history-empty">Nenhum histórico de contratos vencidos registrado ainda.</div>
    <div v-else class="overdue-curve">
      <div class="curve-summary">
        <div>
          <span>Vencidos agora (todas as unidades)</span>
          <strong class="danger">{{ formatNumber(latest?.remaining ?? 0, 0) }}</strong>
        </div>
        <i aria-hidden="true" />
        <div>
          <span>Regularizações (desde o início do acompanhamento)</span>
          <strong class="success">{{ formatNumber(latest?.resolved ?? 0, 0) }}</strong>
        </div>
        <i aria-hidden="true" />
        <div>
          <span>Acompanhando desde</span>
          <strong>{{ first ? formatDateLabel(first.date) : "—" }}</strong>
        </div>
      </div>

      <p v-if="points.length === 1" class="single-point-hint">
        Primeiro registro de hoje. A curva cresce a cada atualização do Dashboard, conforme os contratos forem regularizados.
      </p>

      <div class="apex-chart-shell">
        <VueApexCharts
          type="line"
          height="350"
          :options="chartOptions"
          :series="chartSeries"
          aria-label="Histórico real de contratos vencidos restantes e regularizações acumuladas, todas as unidades"
        />
      </div>

      <p class="chart-hint">Clique em uma linha ou em um ponto para ver os contratos daquela data.</p>
    </div>
  </DashboardCard>
</template>

<style scoped>
.overdue-curve {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.curve-summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 16px;
}
.curve-summary > div {
  display: grid;
  gap: 2px;
}
.curve-summary > div span {
  color: #8a97ab;
  font-size: 10.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.curve-summary > div strong {
  color: #20324a;
  font-size: 15px;
  font-weight: 800;
}
.curve-summary > div strong.danger {
  color: #b9362b;
}
.curve-summary > div strong.success {
  color: #4a7b36;
}
.curve-summary > i {
  width: 1px;
  height: 26px;
  background: #e4e9f0;
}
.single-point-hint,
.chart-hint {
  margin: 0;
  color: #7b8799;
  font-size: 11px;
}
.chart-hint {
  margin-top: -6px;
  text-align: center;
}
.apex-chart-shell {
  min-height: 350px;
  border-radius: 10px;
  background: #fff;
}
.history-chart-loading {
  display: grid;
  gap: 8px;
  min-height: 350px;
}
.history-chart-loading :deep(.v-skeleton-loader) {
  background: transparent;
}
.apex-chart-shell :deep(.apexcharts-toolbar) {
  gap: 2px;
}
.apex-chart-shell :deep(.apexcharts-toolbar button) {
  border-radius: 5px;
}
.apex-chart-shell :deep(.apexcharts-toolbar button:hover),
.apex-chart-shell :deep(.apexcharts-toolbar button:focus-visible),
.apex-chart-shell :deep(.apexcharts-toolbar button.apexcharts-selected) {
  background: #e6f2ff;
}
.apex-chart-shell :deep(.apexcharts-line-series .apexcharts-series),
.apex-chart-shell :deep(.apexcharts-marker) {
  cursor: pointer;
}
.apex-chart-shell :deep(.apexcharts-tooltip),
.apex-chart-shell :deep(.apexcharts-xaxistooltip) {
  border-color: #d8dde3;
  border-radius: 8px;
  box-shadow: 0 6px 16px rgb(15 23 42 / 12%);
}
@media (max-width: 768px) {
  .apex-chart-shell {
    min-height: 315px;
    margin-inline: -8px;
  }
}
</style>
