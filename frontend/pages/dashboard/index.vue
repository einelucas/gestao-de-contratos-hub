<script setup lang="ts">
import { BarChart3, CalendarClock, CalendarX, CheckCheck, CircleCheck, CircleDollarSign, FileText, FilterX, PieChart, RefreshCw, TriangleAlert } from "lucide-vue-next";
import type { Contract, ContractAlert, ContractSummary, DeadlineBucket, OverdueHistorySeries } from "~/types/api";
import { money, statusLabel } from "~/utils/contracts";
import {
  applyDashboardBaseFilters,
  filterByAlert,
  filterByDeadlineBucket,
  filterByMonth,
  filterByUnit,
  type MonthSegment,
} from "~/utils/dashboardDrilldown";
import { formatNumber, formatPercent } from "~/utils/format";
import { createLatestRequest } from "~/utils/latestRequest";

definePageMeta({ middleware: "auth" });

const api = useApi();
const summary = ref<ContractSummary | null>(null);
const units = ref<string[]>([]);
const loading = ref(false);
const error = ref("");
const filters = reactive({ de: "", ate: "", unit: "" });
/** Incrementado a cada `load()` bem-sucedido para o OverdueResolutionCurve recarregar junto. */
const overdueHistoryReloadToken = ref(0);

const STATUS_COLOR = {
  Regular: "#609346",
  Atencao: "#eaa239",
  Vencido: "#c0392b",
  Finalizado: "#bdbfc1",
  SemData: "#007cc5",
} as const;

// Filtros trocados rápido disparam várias cargas: só a mais recente pode mexer na tela.
const summaryRequest = createLatestRequest();

async function load(): Promise<void> {
  const request = summaryRequest.begin();
  const unitFilter = filters.unit;
  loading.value = true;
  error.value = "";
  // /contratos não é afetado pelos filtros do Dashboard e só alimenta o drilldown: carrega em
  // paralelo e com erro próprio, para uma falha ali não derrubar o resumo.
  void refreshContracts();
  try {
    const summaryResponse = await api.request<ContractSummary>("/contratos/resumo", {
      method: "GET",
      query: { de: filters.de || undefined, ate: filters.ate || undefined, unit: unitFilter || undefined },
      signal: request.signal,
    });
    if (!request.isCurrent()) return;
    summary.value = summaryResponse;
    // Opções de unidade vêm do recorte sem filtro de unidade, para a lista não encolher.
    if (!unitFilter) units.value = summaryResponse.byUnit.map((item) => item.key).filter(Boolean).sort((a, b) => a.localeCompare(b, "pt-BR"));
    overdueHistoryReloadToken.value++;
  } catch (cause) {
    if (!request.isCurrent()) return;
    error.value = cause instanceof Error ? cause.message : "Não foi possível carregar o dashboard.";
  } finally {
    if (request.isCurrent()) loading.value = false;
  }
}

function clearFilters(): void {
  Object.assign(filters, { de: "", ate: "", unit: "" });
}

const hasFilters = computed(() => Boolean(filters.de || filters.ate || filters.unit));
const kpis = computed(() => summary.value?.kpis);
const percentOf = (key: string) => summary.value?.byStatus.find((item) => item.key === key)?.percent ?? 0;

const kpiCards = computed(() => {
  const k = kpis.value;
  if (!k) return [];
  return [
    { label: "Total de contratos", value: k.total, sub: `${k.active} ativos`, tone: "default" as const, icon: FileText },
    { label: "Regulares", value: k.regular, sub: formatPercent(percentOf("Regular")), tone: "good" as const, icon: CircleCheck },
    { label: "Atenção · 20 dias", value: k.atencao, sub: formatPercent(percentOf("Atencao")), tone: "default" as const, icon: TriangleAlert },
    { label: "Vencidos", value: k.vencido, sub: formatPercent(percentOf("Vencido")), tone: "bad" as const, icon: CalendarX },
    { label: "Finalizados", value: k.finalizado, sub: formatPercent(percentOf("Finalizado")), tone: "default" as const, icon: CheckCheck },
  ];
});

const statusDonut = computed(() =>
  (summary.value?.byStatus ?? [])
    .filter((item) => item.count > 0)
    .map((item) => ({ key: item.key, label: item.label, value: item.percent, color: STATUS_COLOR[item.key as keyof typeof STATUS_COLOR] })),
);

const statusSeries = [
  { key: "regular", label: "Regulares", color: STATUS_COLOR.Regular },
  { key: "atencao", label: "Atenção", color: STATUS_COLOR.Atencao },
  { key: "vencido", label: "Vencidos", color: STATUS_COLOR.Vencido },
  { key: "semData", label: "Sem data", color: STATUS_COLOR.SemData },
  { key: "finalizado", label: "Finalizados", color: STATUS_COLOR.Finalizado },
];

function groupPoints(groups: ContractSummary["byUnit"]) {
  return groups.slice(0, 12).map((group) => ({
    key: group.key,
    label: group.label,
    value: group.total,
    values: {
      regular: group.regular,
      atencao: group.atencao,
      vencido: group.vencido,
      semData: group.semData,
      finalizado: group.finalizado,
    },
  }));
}

const unitPoints = computed(() => groupPoints(summary.value?.byUnit ?? []));
const sectorPoints = computed(() => groupPoints(summary.value?.bySector ?? []));

const monthlySeries = [
  { key: "upcoming", label: "A vencer", color: "#304f7e" },
  { key: "overdue", label: "Vencidos (em aberto)", color: STATUS_COLOR.Vencido },
  { key: "finalized", label: "Finalizados", color: STATUS_COLOR.Finalizado },
];
const monthlyPoints = computed(() =>
  (summary.value?.monthly ?? []).map((month) => ({
    key: month.month,
    label: month.label,
    value: month.expiring + month.finalized,
    values: { upcoming: month.expiring - month.overdue, overdue: month.overdue, finalized: month.finalized },
  })),
);
const valueByUnit = computed(() =>
  (summary.value?.byUnit ?? [])
    .filter((group) => group.totalValue > 0)
    .slice(0, 12)
    .map((group) => ({ label: group.label, value: Math.round(group.totalValue / 1000) })),
);

// ------------------------------------------------------------- drilldown
// Gráficos clicáveis: o popup reaproveita a mesma lista de /contratos (já
// filtrada pelo acesso do usuário, e não afetada pelos filtros do Dashboard),
// carregada junto com o resumo em `load()` e cacheada enquanto o Dashboard
// está aberto.
const allContracts = ref<Contract[]>([]);
const contractsLoaded = ref(false);
const contractsError = ref("");
const contractsRequest = createLatestRequest();
let contractsInFlight: Promise<void> | null = null;

/** Nunca rejeita: o erro fica em `contractsError` (mostrado no popup do drilldown). */
function refreshContracts(): Promise<void> {
  const request = contractsRequest.begin();
  const run = (async () => {
    try {
      const response = await api.request<{ items: Contract[] }>("/contratos", { method: "GET", signal: request.signal });
      if (!request.isCurrent()) return;
      allContracts.value = response.items;
      contractsLoaded.value = true;
      contractsError.value = "";
    } catch (cause) {
      if (!request.isCurrent()) return;
      contractsError.value = cause instanceof Error ? cause.message : "Não foi possível carregar os contratos.";
    } finally {
      if (request.isCurrent()) contractsInFlight = null;
    }
  })();
  contractsInFlight = run;
  return run;
}

async function ensureContracts(): Promise<void> {
  if (contractsInFlight) await contractsInFlight;
  if (!contractsLoaded.value) await refreshContracts();
}

const drilldown = reactive<{ open: boolean; title: string; contracts: Contract[] }>({
  open: false,
  title: "",
  contracts: [],
});
const drilldownLoading = ref(false);
const drilldownError = ref("");

async function openDrilldown(title: string, select: (base: Contract[]) => Contract[]): Promise<void> {
  drilldown.title = title;
  drilldown.open = true;
  drilldown.contracts = [];
  drilldownError.value = "";
  drilldownLoading.value = true;
  try {
    await ensureContracts();
    if (!contractsLoaded.value) {
      drilldownError.value = contractsError.value;
      return;
    }
    const base = applyDashboardBaseFilters(allContracts.value, filters);
    drilldown.contracts = select(base);
  } finally {
    drilldownLoading.value = false;
  }
}

const historyDetailsRequest = createLatestRequest();
async function openHistoryDrilldown(payload: { date: string; series: OverdueHistorySeries }): Promise<void> {
  const request = historyDetailsRequest.begin();
  const dateLabel = new Date(`${payload.date}T00:00:00`).toLocaleDateString("pt-BR");
  drilldown.title = payload.series === "remaining"
    ? `Contratos vencidos em ${dateLabel}`
    : `Contratos regularizados em ${dateLabel}`;
  drilldown.open = true;
  drilldown.contracts = [];
  drilldownError.value = "";
  drilldownLoading.value = true;
  try {
    const response = await api.request<{ items: Contract[] }>("/contratos/vencidos-historico/detalhes", {
      method: "GET",
      query: { data: payload.date, serie: payload.series },
      signal: request.signal,
    });
    if (!request.isCurrent()) return;
    drilldown.contracts = response.items;
  } catch (cause) {
    if (!request.isCurrent()) return;
    drilldownError.value = cause instanceof Error ? cause.message : "Não foi possível carregar os contratos do histórico.";
  } finally {
    if (request.isCurrent()) drilldownLoading.value = false;
  }
}
function closeDrilldown(): void {
  drilldown.open = false;
}

const SERIES_ALERT: Record<string, ContractAlert> = {
  regular: "Regular",
  atencao: "Atencao",
  vencido: "Vencido",
  semData: "SemData",
  finalizado: "Finalizado",
};

function onStatusSelect(item: { key?: string; label: string }): void {
  const alert = item.key as ContractAlert | undefined;
  if (!alert) return;
  void openDrilldown(`Contratos ${statusLabel(alert).toLowerCase()}`, (base) => filterByAlert(base, alert));
}

function onDeadlineSelect(key: DeadlineBucket["key"]): void {
  const label = summary.value?.deadlines.find((item) => item.key === key)?.label ?? "";
  void openDrilldown(`Contratos — ${label}`, (base) => filterByDeadlineBucket(base, key));
}

function onUnitBarSelect(payload: { point: { label: string; key?: string }; seriesKey?: string }): void {
  const unitKey = payload.point.key ?? payload.point.label;
  const alert = payload.seriesKey ? SERIES_ALERT[payload.seriesKey] : undefined;
  const title = alert
    ? `Contratos da unidade ${payload.point.label} — ${statusLabel(alert)}`
    : `Contratos da unidade ${payload.point.label}`;
  void openDrilldown(title, (base) => filterByUnit(base, unitKey, alert));
}

function onMonthlyBarSelect(payload: { point: { label: string; key?: string }; seriesKey?: string }): void {
  const month = payload.point.key;
  if (!month) return;
  const segment = payload.seriesKey as MonthSegment | undefined;
  const title =
    segment === "overdue"
      ? `Contratos vencidos em ${payload.point.label}`
      : segment === "finalized"
        ? `Contratos finalizados em ${payload.point.label}`
        : `Contratos com vencimento em ${payload.point.label}`;
  void openDrilldown(title, (base) => filterByMonth(base, month, segment));
}

// A execução imediata chama refreshContracts(), que usa contractsRequest e
// contractsInFlight. Registre o watcher só depois de inicializar esses estados.
watch(filters, load, { deep: true, immediate: true });

</script>

<template>
  <ModuleWorkspace eyebrow="Projetos e Arquitetura · Contratos" title="Dashboard" description="Indicadores de vigência, prazos e valores dos contratos que você pode consultar.">
    <div class="contracts-dashboard">
      <section class="surface contracts-surface">
        <div class="contract-filter-bar dashboard-filter-bar">
          <label><span>Vencimento de</span><input v-model="filters.de" type="date" /></label>
          <label><span>Vencimento até</span><input v-model="filters.ate" type="date" /></label>
          <label><span>Unidade</span><select v-model="filters.unit"><option value="">Todas</option><option v-for="item in units" :key="item" :value="item">{{ item }}</option></select></label>
          <div class="filter-actions">
            <button type="button" class="btn" :disabled="!hasFilters" @click="clearFilters"><FilterX class="size-4" />Limpar</button>
            <button type="button" class="btn" :disabled="loading" @click="load"><RefreshCw class="size-4" />Atualizar</button>
          </div>
        </div>
        <p v-if="summary" class="dashboard-caption">
          Situação em {{ new Date(`${summary.today}T00:00:00`).toLocaleDateString("pt-BR") }}
          <template v-if="summary.periodStart || summary.periodEnd"> · vencimentos no período selecionado (contratos sem data ficam de fora)</template>
        </p>
      </section>

      <div v-if="error" class="contracts-state error">{{ error }}</div>
      <div v-else-if="!summary" class="contracts-state">Carregando indicadores…</div>

      <template v-else>
        <section class="metric-grid dashboard-metric-grid" aria-label="Indicadores do recorte atual">
          <MetricCard v-for="card in kpiCards" :key="card.label" :label="card.label" :value="formatNumber(card.value, 0)" :detail="card.sub" :tone="card.tone" :icon="card.icon" :class="{ attention: card.icon === TriangleAlert }" />
        </section>

        <OnTimeChart :kpis="summary.kpis" />

        <div class="dashboard-grid">
          <DashboardCard title="Contratos por status" subtitle="Distribuição de todos os contratos do recorte." :icon="PieChart">
            <DonutChart v-if="statusDonut.length" :items="statusDonut" show-legend-values @select="onStatusSelect" />
            <p v-else class="history-empty">Nenhum contrato no recorte.</p>
          </DashboardCard>

          <DeadlineStatusCard :deadlines="summary.deadlines" @select="onDeadlineSelect" />

          <DashboardCard title="Contratos por unidade" subtitle="Status empilhado por unidade." :icon="BarChart3" class="span-2">
            <BarChart v-if="unitPoints.length" :points="unitPoints" :series="statusSeries" series-label="Total" @select="onUnitBarSelect" />
            <p v-else class="history-empty">Nenhum contrato no recorte.</p>
          </DashboardCard>

          <DashboardCard v-if="sectorPoints.length > 1" title="Contratos por setor" subtitle="Status empilhado por setor." :icon="BarChart3" class="span-2">
            <BarChart :points="sectorPoints" :series="statusSeries" series-label="Total" />
          </DashboardCard>

          <DashboardCard title="Vencimentos por mês" subtitle="Contratos pelo mês do fim da vigência." :icon="CalendarClock" class="span-2">
            <BarChart :points="monthlyPoints" :series="monthlySeries" series-label="Total" @select="onMonthlyBarSelect" />
          </DashboardCard>

          <OverdueResolutionCurve :reload-token="overdueHistoryReloadToken" @select="openHistoryDrilldown" />

          <DashboardCard v-if="summary.values.hasValues" title="Valores contratados" subtitle="Soma do valor total dos contratos do recorte." :icon="CircleDollarSign" class="span-2">
            <div class="stat-tiles four">
              <div><span>Total</span><strong>{{ money(summary.values.total) }}</strong></div>
              <div><span>Contratos ativos</span><strong>{{ money(summary.values.active) }}</strong></div>
              <div><span>Em atenção</span><strong class="warning">{{ money(summary.values.attention) }}</strong></div>
              <div><span>Vencidos</span><strong class="danger">{{ money(summary.values.overdue) }}</strong></div>
            </div>
            <BarChart v-if="valueByUnit.length" :points="valueByUnit" suffix=" mil" series-label="Valor total (R$)" color="#304f7e" />
          </DashboardCard>
        </div>
      </template>
    </div>
    <DashboardContractsModal
      :open="drilldown.open"
      :title="drilldown.title"
      :contracts="drilldown.contracts"
      :loading="drilldownLoading"
      :error="drilldownError"
      @close="closeDrilldown"
    />
  </ModuleWorkspace>
</template>
