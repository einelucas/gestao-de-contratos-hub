<script setup lang="ts">
import { TrendingDown } from "lucide-vue-next";
import type { OverdueHistoryPoint, OverdueHistorySeries } from "~/types/api";
import { formatNumber } from "~/utils/format";

/**
 * Histórico REAL de resolução dos contratos vencidos — vem de
 * `GET /contratos/vencidos-historico` (org-wide, igual para todo mundo com
 * acesso ao Hub), não de projeção nem de armazenamento local do navegador.
 * O backend reconcilia a cada chamada: quem saiu da lista de vencidos vira
 * "regularizado" (acumulado, nunca diminui); quem é novo só conta como
 * "restante". O acumulado conta REGULARIZAÇÕES (ciclos resolvidos): um
 * contrato que vence, é regularizado e vence de novo conta duas vezes — por
 * isso a tela fala em "regularizações", não em "contratos regularizados".
 * Não há percentual de progresso: novos vencidos entram na série depois, então
 * resolvidos / (restantes + resolvidos) não mede avanço sobre uma base fixa.
 * É um indicador corporativo (todas as unidades): não responde aos filtros do
 * Dashboard, porque não existe histórico por unidade/período para recortar.
 * `reloadToken` é incrementado pela página sempre que o
 * Dashboard é carregado/atualizado, para a curva acompanhar o resto da tela.
 */
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

function formatDateLabel(date: string): string {
  return new Date(`${date}T00:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function pointAriaLabel(point: OverdueHistoryPoint, series: OverdueHistorySeries): string {
  const count = series === "remaining" ? point.remaining : point.resolved;
  const label = series === "remaining"
    ? `${count} contratos vencidos. Abrir contratos vencidos nesta data.`
    : `${count} regularizações acumuladas. Abrir contratos regularizados nesta data.`;
  return `${formatDateLabel(point.date)}: ${label}`;
}

const width = 900;
const height = 300;
const pad = { left: 56, right: 30, top: 32, bottom: 50 };
const plotWidth = width - pad.left - pad.right;
const plotHeight = height - pad.top - pad.bottom;

const yMax = computed(() => {
  const values = points.value.flatMap((point) => [point.remaining, point.resolved]);
  return Math.max(1, ...values);
});

const x = (index: number) => pad.left + (index * plotWidth) / Math.max(1, points.value.length - 1);
const y = (value: number) => height - pad.bottom - (value / yMax.value) * plotHeight;
function dotX(index: number, series: OverdueHistorySeries): number {
  const point = points.value[index];
  if (!point || point.remaining !== point.resolved) return x(index);
  return x(index) + (series === "remaining" ? -6 : 6);
}

const yTicks = computed(() => {
  const steps = 4;
  return Array.from({ length: steps + 1 }, (_, index) => {
    const value = (yMax.value / steps) * index;
    return { value, y: y(value) };
  }).reverse();
});

function buildSmoothPath(coords: Array<{ x: number; y: number }>): string {
  if (!coords.length) return "";
  const first0 = coords[0];
  if (!first0) return "";
  if (coords.length === 1) return `M ${first0.x} ${first0.y}`;
  const tension = 0.18;
  let path = `M ${first0.x} ${first0.y}`;
  for (let index = 0; index < coords.length - 1; index++) {
    const current = coords[index];
    const next = coords[index + 1];
    if (!current || !next) continue;
    const previous = coords[index - 1] ?? current;
    const afterNext = coords[index + 2] ?? next;
    const cp1x = current.x + (next.x - previous.x) * tension;
    const cp1y = current.y + (next.y - previous.y) * tension;
    const cp2x = next.x - (afterNext.x - current.x) * tension;
    const cp2y = next.y - (afterNext.y - current.y) * tension;
    path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${next.x} ${next.y}`;
  }
  return path;
}

const remainingCoords = computed(() => points.value.map((point, index) => ({ x: x(index), y: y(point.remaining) })));
const resolvedCoords = computed(() => points.value.map((point, index) => ({ x: x(index), y: y(point.resolved) })));
const remainingPath = computed(() => buildSmoothPath(remainingCoords.value));
const resolvedPath = computed(() => buildSmoothPath(resolvedCoords.value));

const hoveredIndex = ref<number | null>(null);
const hoveredPoint = computed(() => (hoveredIndex.value === null ? null : (points.value[hoveredIndex.value] ?? null)));
// Regularizações registradas entre o ponto anterior e o ponto em foco.
const hoveredResolvedDelta = computed(() => {
  if (hoveredIndex.value === null || hoveredIndex.value === 0) return null;
  const point = points.value[hoveredIndex.value];
  const previous = points.value[hoveredIndex.value - 1];
  return point && previous ? point.resolved - previous.resolved : null;
});

const tooltipStyle = computed(() => {
  if (hoveredIndex.value === null) return {};
  const px = (x(hoveredIndex.value) / width) * 100;
  const alignRight = px > 62;
  return {
    left: `${px}%`,
    top: `${(pad.top / height) * 100}%`,
    transform: `translate(${alignRight ? "-100%" : "0%"}, 0) translate(${alignRight ? "-10px" : "10px"}, 0)`,
  };
});
</script>

<template>
  <DashboardCard
    title="Evolução da Regularização dos Contratos Vencidos"
    subtitle="Indicador corporativo — todas as unidades. Não responde aos filtros acima. Histórico real, registrado no servidor a cada atualização do Dashboard."
    :icon="TrendingDown"
    class="span-2"
  >
    <div v-if="error" class="contracts-state error">{{ error }}</div>
    <div v-else-if="loading && !points.length" class="history-empty">Carregando histórico…</div>
    <div v-else-if="!points.length" class="history-empty">Nenhum histórico de contratos vencidos registrado ainda.</div>
    <div v-else class="overdue-curve">
      <div class="curve-summary">
        <div><span>Vencidos agora (todas as unidades)</span><strong class="danger">{{ formatNumber(latest?.remaining ?? 0, 0) }}</strong></div>
        <i aria-hidden="true" />
        <div><span>Regularizações (desde o início do acompanhamento)</span><strong class="success">{{ formatNumber(latest?.resolved ?? 0, 0) }}</strong></div>
        <i aria-hidden="true" />
        <div><span>Acompanhando desde</span><strong>{{ first ? formatDateLabel(first.date) : "—" }}</strong></div>
        <span class="real-data-badge">Dados reais</span>
      </div>

      <p v-if="points.length === 1" class="single-point-hint">
        Primeiro registro de hoje. A curva cresce a cada atualização do Dashboard, conforme os contratos forem regularizados.
      </p>

      <div v-else class="chart-stage">
        <svg
          class="chart-svg"
          :viewBox="`0 0 ${width} ${height}`"
          role="img"
          aria-label="Histórico real de contratos vencidos restantes e regularizações acumuladas, todas as unidades"
          preserveAspectRatio="xMidYMid meet"
        >
          <g v-for="tick in yTicks" :key="tick.value">
            <line :x1="pad.left" :x2="width - pad.right" :y1="tick.y" :y2="tick.y" class="chart-grid-line" />
            <text :x="pad.left - 9" :y="tick.y + 4" text-anchor="end" class="chart-axis-label">{{ Math.round(tick.value) }}</text>
          </g>

          <line :x1="pad.left" :x2="pad.left" :y1="pad.top" :y2="height - pad.bottom" class="chart-axis" />
          <line :x1="pad.left" :x2="width - pad.right" :y1="height - pad.bottom" :y2="height - pad.bottom" class="chart-axis" />

          <line
            v-if="hoveredIndex !== null"
            :x1="x(hoveredIndex)"
            :x2="x(hoveredIndex)"
            :y1="pad.top"
            :y2="height - pad.bottom"
            class="chart-hover-guide"
          />

          <path v-if="remainingPath" :d="remainingPath" fill="none" class="curve-line curve-remaining" />
          <path v-if="resolvedPath" :d="resolvedPath" fill="none" class="curve-line curve-resolved" />

          <template v-for="(point, index) in points" :key="point.date">
            <rect
              :x="x(index) - plotWidth / Math.max(1, points.length * 2)"
              y="0"
              :width="plotWidth / Math.max(1, points.length)"
              :height="height"
              fill="transparent"
              @mouseenter="hoveredIndex = index"
              @mouseleave="hoveredIndex = null"
            />
            <circle
              :cx="dotX(index, 'remaining')" :cy="y(point.remaining)" :r="hoveredIndex === index ? 6 : 5"
              class="curve-dot curve-remaining-dot" role="button" tabindex="0"
              :aria-label="pointAriaLabel(point, 'remaining')"
              @mouseenter="hoveredIndex = index"
              @click="emit('select', { date: point.date, series: 'remaining' })"
              @keydown.enter.prevent="emit('select', { date: point.date, series: 'remaining' })"
              @keydown.space.prevent="emit('select', { date: point.date, series: 'remaining' })"
            />
            <circle
              :cx="dotX(index, 'resolved')" :cy="y(point.resolved)" :r="hoveredIndex === index ? 6 : 5"
              class="curve-dot curve-resolved-dot" role="button" tabindex="0"
              :aria-label="pointAriaLabel(point, 'resolved')"
              @mouseenter="hoveredIndex = index"
              @click="emit('select', { date: point.date, series: 'resolved' })"
              @keydown.enter.prevent="emit('select', { date: point.date, series: 'resolved' })"
              @keydown.space.prevent="emit('select', { date: point.date, series: 'resolved' })"
            />
            <text :x="x(index)" :y="height - 16" text-anchor="middle" class="chart-x-label" :class="{ 'chart-x-label--active': hoveredIndex === index }">
              {{ formatDateLabel(point.date) }}
            </text>
          </template>
        </svg>

        <div v-if="hoveredPoint" class="chart-tooltip" :style="tooltipStyle">
          <div class="chart-tooltip-title">{{ formatDateLabel(hoveredPoint.date) }}</div>
          <div class="chart-tooltip-row"><span class="chart-tooltip-dot curve-remaining-dot" /><span>Restantes: <strong>{{ formatNumber(hoveredPoint.remaining, 0) }}</strong></span></div>
          <div class="chart-tooltip-row"><span class="chart-tooltip-dot curve-resolved-dot" /><span>Regularizações (acumulado): <strong>{{ formatNumber(hoveredPoint.resolved, 0) }}</strong></span></div>
          <div v-if="hoveredResolvedDelta !== null" class="chart-tooltip-row"><span>Desde o registro anterior: <strong>+{{ formatNumber(hoveredResolvedDelta, 0) }}</strong></span></div>
        </div>
      </div>

      <div class="chart-legend">
        <span class="chart-legend-item"><span class="chart-legend-square curve-remaining-dot" />Vencidos restantes</span>
        <span class="chart-legend-item"><span class="chart-legend-square curve-resolved-dot" />Regularizações (acumulado)</span>
        <span class="chart-legend-hint">Clique em um ponto para ver os contratos.</span>
      </div>
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
.real-data-badge {
  margin-left: auto;
  padding: 4px 10px;
  border: 1px solid #c9e2c0;
  border-radius: 999px;
  background: #eef7ea;
  color: #3f6b32;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.single-point-hint {
  margin: 0;
  color: #62708a;
  font-size: 12.5px;
}
.chart-stage {
  position: relative;
  width: 100%;
}
.chart-svg {
  display: block;
  width: 100%;
  height: auto;
  overflow: visible;
}
.chart-grid-line {
  stroke: #edf1f5;
  stroke-width: 1;
}
.chart-axis {
  stroke: #9aa3ad;
  stroke-width: 1.15;
}
.chart-axis-label,
.chart-x-label {
  fill: #7f8996;
  font-size: 10px;
  font-weight: 400;
}
.chart-x-label--active {
  fill: #1f2937;
  font-weight: 600;
}
.chart-hover-guide {
  stroke: #c3cbd6;
  stroke-width: 1;
  stroke-dasharray: 4 4;
  pointer-events: none;
}
.curve-line {
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.curve-remaining {
  stroke: #c0392b;
}
.curve-resolved {
  stroke: #4a7b36;
}
.curve-dot {
  cursor: pointer;
  stroke: #ffffff;
  stroke-width: 1.5;
}
.curve-dot:focus {
  outline: none;
  stroke: #20324a;
  stroke-width: 2.5;
}
.curve-remaining-dot {
  fill: #c0392b;
  background: #c0392b;
}
.curve-resolved-dot {
  fill: #4a7b36;
  background: #4a7b36;
}
.chart-tooltip {
  position: absolute;
  z-index: 5;
  min-width: 170px;
  padding: 9px 12px;
  background: #f3f4f6;
  border: 1px solid #d8dde3;
  border-radius: 8px;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.12);
  color: #1f2937;
  font-size: 12px;
  pointer-events: none;
}
.chart-tooltip-title {
  margin-bottom: 6px;
  font-weight: 700;
}
.chart-tooltip-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 0;
}
.chart-tooltip-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.chart-legend {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px 18px;
  color: #62708a;
  font-size: 12px;
}
.chart-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 7px;
}
.chart-legend-square {
  width: 9px;
  height: 9px;
  border-radius: 3px;
}
.chart-legend-hint {
  flex-basis: 100%;
  text-align: center;
  color: #8a97ab;
  font-size: 11px;
}
@media (max-width: 768px) {
  .real-data-badge {
    margin-left: 0;
  }
  .chart-axis-label,
  .chart-x-label {
    font-size: 9px;
  }
  .chart-tooltip {
    min-width: 150px;
    padding: 8px 10px;
    font-size: 11px;
  }
}
</style>
