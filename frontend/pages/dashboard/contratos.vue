<script setup lang="ts">
import { Bell, CalendarX, CheckCheck, CheckCircle2, CircleCheck, FileText, Grid2X2, List, Plus, RefreshCw, TriangleAlert, Upload, X } from "lucide-vue-next";
import type { Contract } from "~/types/api";
import type { SortMode, StatusFilter, ValueCompositionFilter } from "~/utils/contracts";
import { matchesValueComposition, sortContracts, VALUE_COMPOSITION_OPTIONS } from "~/utils/contracts";
definePageMeta({ middleware: "auth" });

const { contracts, sectors, loading, error, sectorsError, lastUpdated, bootstrap, loadContracts, loadSectors } = useContracts();
// "Novo contrato" só para quem edita ao menos um setor (ADMIN: todos; ANALYST: canEdit; VIEWER: nenhum).
const canCreate = computed(() => sectors.value.some(sector => sector.canEdit));
const auth = useAuthStore();
const canImport = computed(() => auth.can('contracts:import'));
const creating = ref(false);
const importing = ref(false);
const flash = ref('');
let flashTimer: ReturnType<typeof setTimeout> | undefined;
function showFlash(message: string): void {
  flash.value = message;
  if (flashTimer) clearTimeout(flashTimer);
  flashTimer = setTimeout(() => (flash.value = ''), 6000);
}
const globalSearch = useState<string>('contracts-global-search', () => '');
const notificationTrigger = useState<number>('contracts-notification-trigger', () => 0);
const route = useRoute(); const router = useRouter();
const { count: attentionCount, load: loadAttention } = useAttention();
const exportTrigger = useState<number>('contracts-export-trigger', () => 0);
const { excel } = useExport();
const supplier = ref('Todos'); const unit = ref('Todas'); const situation = ref('Todos'); const valueComposition = ref<ValueCompositionFilter>('Todos'); const statusFilter = ref<StatusFilter>('Todos'); const sortMode = ref<SortMode>('Status e vencimento'); const viewMode = ref<'grid'|'list'>('grid'); const page = ref(1); const selected = ref<Contract|null>(null); const perPage = ref(20);

await bootstrap();

// ?contrato=<id> abre o detalhe (link do sino e do e-mail de alerta).
async function openFromQuery(id: unknown): Promise<void> {
  if (typeof id !== 'string' || !id) return;
  selected.value = contracts.value.find(c => c.id === id) ?? await useApi().get<Contract>(`/contratos/${id}`).catch(() => null);
}
// Depois da hidratação: abrir antes faria o cliente renderizar o drawer que o servidor não renderizou.
onMounted(() => openFromQuery(route.query.contrato));
watch(() => route.query.contrato, openFromQuery);
function closeDetails(): void {
  selected.value = null;
  if (route.query.contrato) void router.replace({ query: { ...route.query, contrato: undefined } });
}
function onContractCreated(created: Contract): void {
  creating.value = false;
  contracts.value.unshift(created);
  selected.value = created;
  showFlash(`Contrato ${created.contractNumber} criado.`);
  void loadSectors();
  void loadAttention();
}
function onContractUpdated(updated: Contract): void {
  const index = contracts.value.findIndex(c => c.id === updated.id);
  if (index >= 0) contracts.value.splice(index, 1, updated);
  selected.value = updated;
  void loadAttention();
}
function onContractDeleted(contractId: string): void {
  const removed = contracts.value.find(contract => contract.id === contractId);
  const index = contracts.value.findIndex(contract => contract.id === contractId);
  if (index >= 0) contracts.value.splice(index, 1);
  closeDetails();
  void loadSectors();
  void loadAttention();
  showFlash(removed ? `Contrato ${removed.contractNumber} excluído.` : 'Contrato excluído.');
}
function onImported(count: number): void {
  selected.value = null;
  clearFilters();
  void loadContracts();
  void loadSectors();
  void loadAttention();
  showFlash(`${count} contratos importados. A base do setor foi substituída.`);
}
watch(exportTrigger, () => {
  excel('gestao-contratos', filtered.value.map(c => ({
    Contrato: c.contractNumber, Fornecedor: c.supplier, Prestacao: c.serviceDescription, Unidade: c.unit,
    Situacao: c.situation, Alerta: c.alert, Inicio: c.startDate, Fim: c.endDate, ValorTotal: Number(c.totalValue), Setor: c.sectorName,
  })));
});
const suppliers = computed(() => ['Todos', ...Array.from(new Set(contracts.value.map(c => c.supplier))).sort((a,b)=>a.localeCompare(b,'pt-BR'))]);
const units = computed(() => ['Todas', ...Array.from(new Set(contracts.value.map(c => c.unit).filter(Boolean))).sort((a,b)=>a.localeCompare(b,'pt-BR'))]);
const baseFiltered = computed(() => contracts.value.filter(c => { const q=globalSearch.value.trim().toLowerCase(); return (!q || c.supplier.toLowerCase().includes(q) || c.contractNumber.toLowerCase().startsWith(q)) && (supplier.value==='Todos'||c.supplier===supplier.value) && (unit.value==='Todas'||c.unit===unit.value) && (situation.value==='Todos'||c.situation===situation.value) && matchesValueComposition(c, valueComposition.value); }));
const kpis = computed(() => ({ total: baseFiltered.value.length, regularization: baseFiltered.value.filter(c=>c.alert==='Regularizacao').length, vencido: baseFiltered.value.filter(c=>c.alert==='Vencido').length, atencao: baseFiltered.value.filter(c=>c.alert==='Atencao').length, regular: baseFiltered.value.filter(c=>c.alert==='Regular').length, finalizado: baseFiltered.value.filter(c=>c.alert==='Finalizado').length }));
const filtered = computed(() => sortContracts(baseFiltered.value.filter(c => statusFilter.value==='Todos' || c.alert===statusFilter.value), sortMode.value));
const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / perPage.value)));
const pageItems = computed(() => filtered.value.slice((page.value-1)*perPage.value, page.value*perPage.value));
watch([globalSearch,supplier,unit,situation,valueComposition,statusFilter,sortMode],()=>page.value=1);
watch(totalPages, value => { if(page.value>value) page.value=value; });
function setStatus(value: StatusFilter){ statusFilter.value = statusFilter.value === value ? 'Todos' : value; }

type ActiveFilterKey = 'search' | 'supplier' | 'unit' | 'situation' | 'valueComposition' | 'status';
interface ActiveFilter { key: ActiveFilterKey; label: string; value: string }

const STATUS_LABELS: Record<Exclude<StatusFilter, 'Todos'>, string> = {
  Regularizacao: 'Em regularização',
  Vencido: 'Vencidos pendentes',
  Atencao: 'Atenção · 20 dias',
  Regular: 'Regulares',
  Finalizado: 'Finalizados',
};

// "Limpar tudo" e os chips usam a mesma lista: o que aparece na tela é o que será limpo.
const activeFilters = computed<ActiveFilter[]>(() => {
  const items: ActiveFilter[] = [];
  const term = globalSearch.value.trim();
  if (term) items.push({ key: 'search', label: 'Busca', value: term });
  if (supplier.value !== 'Todos') items.push({ key: 'supplier', label: 'Fornecedor', value: supplier.value });
  if (unit.value !== 'Todas') items.push({ key: 'unit', label: 'Unidade', value: unit.value });
  if (situation.value !== 'Todos') items.push({ key: 'situation', label: 'Situação', value: situation.value });
  if (valueComposition.value !== 'Todos') {
    const composition = VALUE_COMPOSITION_OPTIONS.find(option => option.value === valueComposition.value);
    items.push({ key: 'valueComposition', label: 'Valores', value: composition?.label ?? valueComposition.value });
  }
  if (statusFilter.value !== 'Todos') items.push({ key: 'status', label: 'Status', value: STATUS_LABELS[statusFilter.value] });
  return items;
});

function removeFilter(key: ActiveFilterKey): void {
  if (key === 'search') globalSearch.value = '';
  else if (key === 'supplier') supplier.value = 'Todos';
  else if (key === 'unit') unit.value = 'Todas';
  else if (key === 'situation') situation.value = 'Todos';
  else if (key === 'valueComposition') valueComposition.value = 'Todos';
  else if (key === 'status') statusFilter.value = 'Todos';
}

function clearFilters(): void {
  globalSearch.value = '';
  supplier.value = 'Todos';
  unit.value = 'Todas';
  situation.value = 'Todos';
  valueComposition.value = 'Todos';
  statusFilter.value = 'Todos';
}
</script>
<template>
  <ModuleWorkspace eyebrow="Projetos e Arquitetura · Contratos" title="Contratos" description="Acompanhe vigências, fornecedores, valores e contratos que exigem atenção.">
    <div class="contracts-dashboard">
      <section class="contract-kpis">
        <ContractKpiCard label="Total de contratos" :value="kpis.total" :active="statusFilter==='Todos'" tone="default" :icon="FileText" @click="statusFilter='Todos'" />
        <ContractKpiCard label="Regulares" :value="kpis.regular" :active="statusFilter==='Regular'" tone="good" :icon="CircleCheck" @click="setStatus('Regular')" />
        <ContractKpiCard label="Atenção · 20 dias" :value="kpis.atencao" :active="statusFilter==='Atencao'" tone="default" :icon="TriangleAlert" class="attention" @click="setStatus('Atencao')" />
        <ContractKpiCard label="Vencidos pendentes" :value="kpis.vencido" :active="statusFilter==='Vencido'" tone="bad" :icon="CalendarX" @click="setStatus('Vencido')" />
        <ContractKpiCard label="Finalizados" :value="kpis.finalizado" :active="statusFilter==='Finalizado'" tone="default" :icon="CheckCheck" @click="setStatus('Finalizado')" />
      </section>

      <section class="surface contracts-surface">
        <div class="contract-filter-bar">
          <label><span>Fornecedor</span><select v-model="supplier"><option v-for="item in suppliers" :key="item">{{ item }}</option></select></label>
          <label><span>Unidade</span><select v-model="unit"><option v-for="item in units" :key="item">{{ item }}</option></select></label>
          <label><span>Situação</span><select v-model="situation"><option>Todos</option><option>Vigente</option><option>Vencido</option><option>Finalizado</option></select></label>
          <label><span>Valores</span><select v-model="valueComposition"><option v-for="option in VALUE_COMPOSITION_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option></select></label>
          <label class="sort-field"><span>Ordenação</span><select v-model="sortMode"><option>Status e vencimento</option><option>Vencimento mais próximo</option></select></label>
          <div class="filter-actions"><button v-if="canCreate" type="button" class="new-contract-button" @click="creating = true"><Plus class="size-4" />Novo contrato</button><button class="icon-control" :class="{ active: viewMode==='grid' }" @click="viewMode='grid'"><Grid2X2 class="size-4" /></button><button class="icon-control" :class="{ active: viewMode==='list' }" @click="viewMode='list'"><List class="size-4" /></button><button class="icon-control" title="Atualizar" @click="loadContracts(); loadAttention()"><RefreshCw class="size-4" /></button><button class="icon-control notification-control" title="Notificações" @click="notificationTrigger++"><Bell class="size-4" /><span v-if="attentionCount">{{ attentionCount }}</span></button></div>
        </div>
        <div v-if="activeFilters.length" class="active-filters" aria-label="Filtros ativos">
          <span class="active-filters-label">Filtros ativos</span>
          <span v-for="filter in activeFilters" :key="filter.key" class="filter-chip">
            <span class="filter-chip-label">{{ filter.label }}:</span>{{ filter.value }}
            <button type="button" class="filter-chip-remove" :aria-label="`Remover filtro ${filter.label}: ${filter.value}`" @click="removeFilter(filter.key)">
              <X class="size-3" />
            </button>
          </span>
          <button type="button" class="clear-filters" @click="clearFilters">Limpar tudo</button>
        </div>
        <div v-if="loading" class="contract-grid" aria-busy="true" aria-label="Carregando contratos">
          <div v-for="index in 10" :key="index" class="skeleton-card" aria-hidden="true">
            <span class="skeleton-line short"></span>
            <span class="skeleton-line long"></span>
            <span class="skeleton-line medium"></span>
            <span class="skeleton-line long"></span>
            <div class="skeleton-meta"><span></span><span></span><span></span></div>
          </div>
        </div>
        <div v-else-if="error" class="contracts-state error">{{ error }}</div>
        <template v-else>
          <p v-if="sectorsError" class="contracts-state error" role="alert">Setores indisponíveis no momento ({{ sectorsError }}). <button type="button" class="icon-control" title="Tentar novamente" @click="loadSectors()"><RefreshCw class="size-4" /></button></p>
          <p v-if="flash" class="flash-success" role="status"><CheckCircle2 class="size-4" />{{ flash }}</p>
          <div class="contracts-result-head"><p><strong>{{ filtered.length }}</strong> contratos encontrados</p><div class="contracts-result-meta"><button v-if="canImport" type="button" class="import-text-action" title="Importar contratos" aria-label="Importar contratos" @click="importing = true"><Upload class="size-4" />Importar</button><span v-if="lastUpdated">Atualizado às {{ lastUpdated.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'}) }}</span></div></div>
          <div v-if="pageItems.length" :class="viewMode==='grid' ? 'contract-grid' : 'contract-list'"><ContractCard v-for="item in pageItems" :key="item.id" :contract="item" :list="viewMode==='list'" @select="selected=$event" /></div>
          <div v-else class="contracts-empty">
            <span class="contracts-empty-icon" aria-hidden="true"><FileText :size="22" /></span>
            <h3>{{ activeFilters.length ? 'Nenhum contrato com esses filtros' : 'Nenhum contrato cadastrado' }}</h3>
            <p v-if="activeFilters.length">Ajuste ou limpe os filtros para ver outros contratos.</p>
            <p v-else>Cadastre o primeiro contrato ou importe uma planilha para começar.</p>
            <div class="contracts-empty-actions">
              <button v-if="activeFilters.length" type="button" class="btn" @click="clearFilters">Limpar filtros</button>
              <template v-else>
                <button v-if="canCreate" type="button" class="btn primary" @click="creating = true"><Plus class="size-4" />Novo contrato</button>
                <button v-if="canImport" type="button" class="btn" @click="importing = true"><Upload class="size-4" />Importar planilha</button>
              </template>
            </div>
          </div>
          <div class="contracts-pagination"><label>Itens por página <select v-model.number="perPage"><option :value="10">10</option><option :value="20">20</option><option :value="30">30</option><option :value="50">50</option></select></label><div><button :disabled="page<=1" @click="page--">Anterior</button><span>Página {{ page }} de {{ totalPages }}</span><button :disabled="page>=totalPages" @click="page++">Próxima</button></div></div>
        </template>
      </section>
    </div>
    <ContractDetailsDrawer :contract="selected" :sectors="sectors" @close="closeDetails" @updated="onContractUpdated" @deleted="onContractDeleted" />
    <ContractForm mode="create" :sectors="sectors" :open="creating" @close="creating = false" @saved="onContractCreated" />
    <ContractImportModal :open="importing" :sectors="sectors" @close="importing = false" @imported="onImported" />
  </ModuleWorkspace>
</template>
