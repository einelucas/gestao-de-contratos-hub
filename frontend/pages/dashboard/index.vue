<script setup lang="ts">
import { BarChart3, CalendarClock, CalendarX, CheckCheck, CircleCheck, CircleDollarSign, FileText, FilterX, PieChart, RefreshCw, Timer, TrendingUp, TriangleAlert } from "lucide-vue-next";
import type { ContractSummary, Sector } from "~/types/api";
import { money } from "~/utils/contracts";
import { formatNumber, formatPercent } from "~/utils/format";

definePageMeta({ middleware: "auth" });

const api = useApi();
const summary = ref<ContractSummary | null>(null);
const sectors = ref<Sector[]>([]);
const units = ref<string[]>([]);
const loading = ref(false);
const error = ref("");
const filters = reactive({ de: "", ate: "", sectorId: "", unit: "" });

const STATUS_COLOR = {
  Regular: "#609346",
  Atencao: "#eaa239",
  Vencido: "#c0392b",
  Finalizado: "#bdbfc1",
  SemData: "#007cc5",
} as const;

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    summary.value = await api.get<ContractSummary>("/contratos/resumo", {
      de: filters.de || undefined,
      ate: filters.ate || undefined,
      sectorId: filters.sectorId || undefined,
      unit: filters.unit || undefined,
    });
    // Opções de unidade vêm do recorte sem filtro de unidade, para a lista não encolher.
    if (!filters.unit) units.value = summary.value.byUnit.map((item) => item.key).filter(Boolean).sort((a, b) => a.localeCompare(b, "pt-BR"));
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível carregar o dashboard.";
  } finally {
    loading.value = false;
  }
}

function clearFilters(): void {
  Object.assign(filters, { de: "", ate: "", sectorId: "", unit: "" });
}

onMounted(async () => {
  sectors.value = (await api.get<{ items: Sector[] }>("/setores").catch(() => ({ items: [] }))).items;
});
watch(filters, load, { deep: true, immediate: true });

const hasFilters = computed(() => Boolean(filters.de || filters.ate || filters.sectorId || filters.unit));
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
    .map((item) => ({ label: item.label, value: item.count, color: STATUS_COLOR[item.key as keyof typeof STATUS_COLOR] })),
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
    label: month.label,
    value: month.expiring + month.finalized,
    values: { upcoming: month.expiring - month.overdue, overdue: month.overdue, finalized: month.finalized },
  })),
);
const expiringLine = computed(() => (summary.value?.monthly ?? []).map((month) => ({ label: month.label, value: month.expiring })));

const valueByUnit = computed(() =>
  (summary.value?.byUnit ?? [])
    .filter((group) => group.totalValue > 0)
    .slice(0, 12)
    .map((group) => ({ label: group.label, value: Math.round(group.totalValue / 1000) })),
);
</script>

<template>
  <ModuleWorkspace eyebrow="Projetos e Arquitetura · Contratos" title="Dashboard" description="Indicadores de vigência, prazos e valores dos contratos que você pode consultar.">
    <div class="contracts-dashboard">
      <section class="surface contracts-surface">
        <div class="contract-filter-bar dashboard-filter-bar">
          <label><span>Vencimento de</span><input v-model="filters.de" type="date" /></label>
          <label><span>Vencimento até</span><input v-model="filters.ate" type="date" /></label>
          <label><span>Setor</span><select v-model="filters.sectorId"><option value="">Todos os setores</option><option v-for="item in sectors" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
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
            <DonutChart v-if="statusDonut.length" :items="statusDonut" suffix="" show-legend-values />
            <p v-else class="history-empty">Nenhum contrato no recorte.</p>
          </DashboardCard>

          <DeadlineStatusCard :deadlines="summary.deadlines" />

          <DashboardCard title="Contratos por unidade" subtitle="Status empilhado por unidade." :icon="BarChart3" class="span-2">
            <BarChart v-if="unitPoints.length" :points="unitPoints" :series="statusSeries" series-label="Total" />
            <p v-else class="history-empty">Nenhum contrato no recorte.</p>
          </DashboardCard>

          <DashboardCard v-if="sectorPoints.length > 1" title="Contratos por setor" subtitle="Status empilhado por setor." :icon="BarChart3" class="span-2">
            <BarChart :points="sectorPoints" :series="statusSeries" series-label="Total" />
          </DashboardCard>

          <DashboardCard title="Vencimentos por mês" subtitle="Contratos pelo mês do fim da vigência." :icon="CalendarClock" class="span-2">
            <BarChart :points="monthlyPoints" :series="monthlySeries" series-label="Total" />
          </DashboardCard>

          <DashboardCard title="Tendência de vencimentos" subtitle="Contratos em aberto que vencem em cada mês." :icon="TrendingUp">
            <LineChart :points="expiringLine" series-label="Vencimentos" :show-legend="false" />
          </DashboardCard>

          <DashboardCard title="Atrasos" subtitle="Contratos vencidos e ainda em aberto." :icon="Timer">
            <div class="stat-tiles">
              <div><span>Vencidos em aberto</span><strong class="danger">{{ summary.overdue.count }}</strong></div>
              <div><span>Média de atraso</span><strong>{{ formatNumber(summary.overdue.averageDays, 1) }} dias</strong></div>
              <div><span>Maior atraso</span><strong>{{ summary.overdue.maxDays }} dias</strong></div>
            </div>
          </DashboardCard>

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
  </ModuleWorkspace>
</template>
