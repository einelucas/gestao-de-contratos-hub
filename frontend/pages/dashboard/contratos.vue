<script setup lang="ts">
import { Bell, CalendarX, CheckCheck, CheckCircle2, CircleCheck, FileText, Grid2X2, List, Plus, RefreshCw, TriangleAlert, Upload } from "lucide-vue-next";
import type { Contract } from "~/types/api";
import type { SortMode, StatusFilter } from "~/utils/contracts";
import { sortContracts } from "~/utils/contracts";
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
const supplier = ref('Todos'); const unit = ref('Todas'); const situation = ref('Todos'); const statusFilter = ref<StatusFilter>('Todos'); const sortMode = ref<SortMode>('Status e vencimento'); const viewMode = ref<'grid'|'list'>('grid'); const page = ref(1); const selected = ref<Contract|null>(null); const perPage = ref(20);

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
function onImported(count: number): void {
  selected.value = null;
  globalSearch.value = '';
  supplier.value = 'Todos'; unit.value = 'Todas'; situation.value = 'Todos'; statusFilter.value = 'Todos';
  page.value = 1;
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
const baseFiltered = computed(() => contracts.value.filter(c => { const q=globalSearch.value.trim().toLowerCase(); return (!q || c.supplier.toLowerCase().includes(q) || c.contractNumber.toLowerCase().startsWith(q)) && (supplier.value==='Todos'||c.supplier===supplier.value) && (unit.value==='Todas'||c.unit===unit.value) && (situation.value==='Todos'||c.situation===situation.value); }));
const kpis = computed(() => ({ total: baseFiltered.value.length, vencido: baseFiltered.value.filter(c=>c.alert==='Vencido').length, atencao: baseFiltered.value.filter(c=>c.alert==='Atencao').length, regular: baseFiltered.value.filter(c=>c.alert==='Regular').length, finalizado: baseFiltered.value.filter(c=>c.alert==='Finalizado').length }));
const filtered = computed(() => sortContracts(baseFiltered.value.filter(c => statusFilter.value==='Todos' || c.alert===statusFilter.value), sortMode.value));
const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / perPage.value)));
const pageItems = computed(() => filtered.value.slice((page.value-1)*perPage.value, page.value*perPage.value));
watch([globalSearch,supplier,unit,situation,statusFilter,sortMode],()=>page.value=1);
watch(totalPages, value => { if(page.value>value) page.value=value; });
function setStatus(value: StatusFilter){ statusFilter.value = statusFilter.value === value ? 'Todos' : value; }
</script>
<template>
  <ModuleWorkspace eyebrow="Projetos e Arquitetura · Contratos" title="Contratos" description="Acompanhe vigências, fornecedores, valores e contratos que exigem atenção.">
    <div class="contracts-dashboard">
      <section class="contract-kpis">
        <ContractKpiCard label="Total de contratos" :value="kpis.total" :active="statusFilter==='Todos'" tone="default" :icon="FileText" @click="statusFilter='Todos'" />
        <ContractKpiCard label="Regulares" :value="kpis.regular" :active="statusFilter==='Regular'" tone="good" :icon="CircleCheck" @click="setStatus('Regular')" />
        <ContractKpiCard label="Atenção · 20 dias" :value="kpis.atencao" :active="statusFilter==='Atencao'" tone="default" :icon="TriangleAlert" class="attention" @click="setStatus('Atencao')" />
        <ContractKpiCard label="Vencidos" :value="kpis.vencido" :active="statusFilter==='Vencido'" tone="bad" :icon="CalendarX" @click="setStatus('Vencido')" />
        <ContractKpiCard label="Finalizados" :value="kpis.finalizado" :active="statusFilter==='Finalizado'" tone="default" :icon="CheckCheck" @click="setStatus('Finalizado')" />
      </section>

      <section class="surface contracts-surface">
        <div class="contract-filter-bar">
          <label><span>Fornecedor</span><select v-model="supplier"><option v-for="item in suppliers" :key="item">{{ item }}</option></select></label>
          <label><span>Unidade</span><select v-model="unit"><option v-for="item in units" :key="item">{{ item }}</option></select></label>
          <label><span>Situação</span><select v-model="situation"><option>Todos</option><option>Vigente</option><option>Vencido</option><option>Finalizado</option></select></label>
          <label class="sort-field"><span>Ordenação</span><select v-model="sortMode"><option>Status e vencimento</option><option>Vencimento mais próximo</option></select></label>
          <div class="filter-actions"><button v-if="canCreate" type="button" class="new-contract-button" @click="creating = true"><Plus class="size-4" />Novo contrato</button><button class="icon-control" :class="{ active: viewMode==='grid' }" @click="viewMode='grid'"><Grid2X2 class="size-4" /></button><button class="icon-control" :class="{ active: viewMode==='list' }" @click="viewMode='list'"><List class="size-4" /></button><button class="icon-control" title="Atualizar" @click="loadContracts(); loadAttention()"><RefreshCw class="size-4" /></button><button class="icon-control notification-control" title="Notificações" @click="notificationTrigger++"><Bell class="size-4" /><span v-if="attentionCount">{{ attentionCount }}</span></button></div>
        </div>
        <div v-if="loading" class="contracts-state">Carregando contratos...</div>
        <div v-else-if="error" class="contracts-state error">{{ error }}</div>
        <template v-else>
          <p v-if="sectorsError" class="contracts-state error" role="alert">Setores indisponíveis no momento ({{ sectorsError }}). <button type="button" class="icon-control" title="Tentar novamente" @click="loadSectors()"><RefreshCw class="size-4" /></button></p>
          <p v-if="flash" class="flash-success" role="status"><CheckCircle2 class="size-4" />{{ flash }}</p>
          <div class="contracts-result-head"><p><strong>{{ filtered.length }}</strong> contratos encontrados</p><div class="contracts-result-meta"><button v-if="canImport" type="button" class="import-text-action" title="Importar contratos" aria-label="Importar contratos" @click="importing = true"><Upload class="size-4" />Importar</button><span v-if="lastUpdated">Atualizado às {{ lastUpdated.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'}) }}</span></div></div>
          <div v-if="pageItems.length" :class="viewMode==='grid' ? 'contract-grid' : 'contract-list'"><ContractCard v-for="item in pageItems" :key="item.id" :contract="item" :list="viewMode==='list'" @select="selected=$event" /></div>
          <div v-else class="contracts-state">Nenhum contrato corresponde aos filtros.</div>
          <div class="contracts-pagination"><label>Itens por página <select v-model.number="perPage"><option :value="10">10</option><option :value="20">20</option><option :value="30">30</option><option :value="50">50</option></select></label><div><button :disabled="page<=1" @click="page--">Anterior</button><span>Página {{ page }} de {{ totalPages }}</span><button :disabled="page>=totalPages" @click="page++">Próxima</button></div></div>
        </template>
      </section>
    </div>
    <ContractDetailsDrawer :contract="selected" :sectors="sectors" @close="closeDetails" @updated="onContractUpdated" />
    <ContractForm mode="create" :sectors="sectors" :open="creating" @close="creating = false" @saved="onContractCreated" />
    <ContractImportModal :open="importing" :sectors="sectors" @close="importing = false" @imported="onImported" />
  </ModuleWorkspace>
</template>
