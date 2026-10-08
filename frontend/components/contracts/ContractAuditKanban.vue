<script setup lang="ts">
import { Building2, CalendarDays, GripVertical, RefreshCw, Search, WalletCards } from "lucide-vue-next";
import type { AuditBoard, AuditStage, Contract } from "~/types/api";
import { dateBr, daysToEndLabel, money } from "~/utils/contracts";

const STAGES: Array<{ key: AuditStage; label: string; color: string }> = [
  { key: "AGUARDANDO_ANALISE", label: "Aguardando Análise", color: "#c85d76" },
  { key: "CHAMADO_ELES", label: "Chamado Elos", color: "#2f73d9" },
  { key: "ANALISE_INTERNA_INPASA", label: "Análise Interna – INPASA", color: "#d98bd2" },
  { key: "FORNECEDOR_CONTATADO", label: "Fornecedor Contatado", color: "#2f9870" },
  { key: "EM_TRATATIVA", label: "Em Tratativa", color: "#35bd86" },
  { key: "EM_FINALIZACAO", label: "Em Finalização", color: "#7c8295" },
  { key: "FINALIZADO", label: "Finalizado", color: "#587b4a" },
];

const api = useApi();
const items = ref<Contract[]>([]);
const units = ref<string[]>([]);
const unit = ref("Todas");
const search = ref("");
const loading = ref(true);
const error = ref("");
const movingId = ref<string | null>(null);
const draggedId = ref<string | null>(null);
const overStage = ref<AuditStage | null>(null);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const response = await api.get<AuditBoard>("/contratos/auditoria");
    items.value = response.items;
    units.value = response.units;
    if (unit.value !== "Todas" && !units.value.includes(unit.value)) unit.value = "Todas";
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível carregar o quadro de auditoria.";
  } finally {
    loading.value = false;
  }
}

onMounted(load);

const filtered = computed(() => {
  const query = search.value.trim().toLocaleLowerCase("pt-BR");
  return items.value.filter((item) =>
    (unit.value === "Todas" || item.unit === unit.value)
    && (!query || item.contractNumber.toLocaleLowerCase("pt-BR").includes(query)
      || item.supplier.toLocaleLowerCase("pt-BR").includes(query)),
  );
});

function stageItems(stage: AuditStage): Contract[] {
  return filtered.value.filter((item) => item.auditStage === stage);
}

function startDrag(event: DragEvent, item: Contract): void {
  if (!item.canEdit || movingId.value) return;
  draggedId.value = item.id;
  event.dataTransfer?.setData("text/plain", item.id);
  if (event.dataTransfer) event.dataTransfer.effectAllowed = "move";
}

function endDrag(): void {
  draggedId.value = null;
  overStage.value = null;
}

async function moveContract(item: Contract, stage: AuditStage): Promise<void> {
  if (!item.canEdit || item.auditStage === stage || movingId.value) return;
  const previous = { ...item };
  movingId.value = item.id;
  error.value = "";
  item.auditStage = stage;
  item.finalized = stage === "FINALIZADO";
  item.situation = item.finalized ? "Finalizado" : "Vencido";
  item.alert = item.finalized ? "Finalizado" : "Vencido";
  try {
    const updated = await api.patch<Contract>(`/contratos/${item.id}/auditoria`, { stage });
    const index = items.value.findIndex((candidate) => candidate.id === item.id);
    if (index >= 0) items.value.splice(index, 1, updated);
  } catch (cause) {
    Object.assign(item, previous);
    error.value = cause instanceof Error ? cause.message : "Não foi possível mover o contrato.";
  } finally {
    movingId.value = null;
    endDrag();
  }
}

function drop(stage: AuditStage, event: DragEvent): void {
  const id = draggedId.value || event.dataTransfer?.getData("text/plain");
  const item = items.value.find((candidate) => candidate.id === id);
  if (item) void moveContract(item, stage);
  else endDrag();
}

function onStageSelect(item: Contract, event: Event): void {
  const target = event.target as HTMLSelectElement;
  void moveContract(item, target.value as AuditStage);
}

function openContract(item: Contract): void {
  void navigateTo({ path: "/dashboard/contratos", query: { contrato: item.id } });
}
</script>

<template>
  <div class="audit-board-page">
    <section class="surface audit-toolbar" aria-label="Filtros da auditoria">
      <label>
        <span>Unidade</span>
        <select v-model="unit">
          <option>Todas</option>
          <option v-for="item in units" :key="item">{{ item }}</option>
        </select>
      </label>
      <label class="audit-search">
        <span>Buscar contrato</span>
        <div><Search class="size-4" /><input v-model="search" type="search" placeholder="Número ou fornecedor" /></div>
      </label>
      <div class="audit-toolbar-summary">
        <span>{{ filtered.length }} contrato{{ filtered.length === 1 ? "" : "s" }} no quadro</span>
        <button type="button" class="btn" :disabled="loading" @click="load"><RefreshCw class="size-4" />Atualizar</button>
      </div>
    </section>

    <p v-if="error" class="contracts-state error" role="alert">{{ error }}</p>
    <div v-if="loading && !items.length" class="contracts-state">Carregando auditoria…</div>
    <div v-else class="audit-board-scroll">
      <div class="audit-kanban" aria-label="Kanban de auditoria dos contratos vencidos">
        <section
          v-for="stage in STAGES"
          :key="stage.key"
          class="audit-column"
          :class="{ 'is-over': overStage === stage.key }"
          @dragover.prevent="overStage = stage.key"
          @dragleave.self="overStage = null"
          @drop.prevent="drop(stage.key, $event)"
        >
          <header :style="{ backgroundColor: stage.color }">
            <span>{{ stage.label }}</span>
            <strong>{{ stageItems(stage.key).length }}</strong>
          </header>

          <div class="audit-column-body">
            <article
              v-for="item in stageItems(stage.key)"
              :key="item.id"
              class="audit-contract-card"
              :class="{ 'is-dragging': draggedId === item.id, 'is-moving': movingId === item.id }"
              :draggable="item.canEdit && !movingId"
              @dragstart="startDrag($event, item)"
              @dragend="endDrag"
            >
              <button type="button" class="audit-card-main" @click="openContract(item)">
                <span class="audit-card-topline">
                  <strong>Contrato {{ item.contractNumber }}</strong>
                  <GripVertical v-if="item.canEdit" class="size-4" aria-hidden="true" />
                </span>
                <span class="audit-card-supplier">{{ item.supplier }}</span>
                <span class="audit-card-meta"><Building2 class="size-3.5" />{{ item.unit || "Sem unidade" }} · {{ item.sectorName }}</span>
                <span class="audit-card-meta"><CalendarDays class="size-3.5" />{{ dateBr(item.endDate) }} · {{ item.finalized ? "Finalizado" : daysToEndLabel(item.daysToEnd) }}</span>
                <span class="audit-card-meta"><WalletCards class="size-3.5" />{{ money(item.totalValue) }}</span>
              </button>
              <label v-if="item.canEdit" class="audit-card-move" @click.stop>
                <span>Mover para</span>
                <select :value="item.auditStage ?? ''" :disabled="movingId === item.id" @change="onStageSelect(item, $event)">
                  <option v-for="target in STAGES" :key="target.key" :value="target.key">{{ target.label }}</option>
                </select>
              </label>
              <span v-else class="audit-card-readonly">Somente consulta</span>
            </article>

            <p v-if="!stageItems(stage.key).length" class="audit-column-empty">Nenhum contrato</p>
          </div>
        </section>
      </div>
    </div>
    <p class="audit-board-help">Arraste os cards entre as etapas. O seletor em cada card permite a mesma movimentação pelo teclado.</p>
  </div>
</template>

<style scoped>
.audit-board-page { display: grid; gap: 14px; }
.audit-toolbar { display: grid; grid-template-columns: minmax(190px, 260px) minmax(240px, 1fr) auto; gap: 14px; align-items: end; padding: 16px 18px; }
.audit-toolbar label { display: grid; gap: 6px; }
.audit-toolbar label > span { color: #52657f; font-size: 10px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }
.audit-toolbar select, .audit-toolbar input { width: 100%; height: 42px; border: 1px solid #dbe3ee; border-radius: 10px; background: #fff; color: #20324a; font-size: 13px; outline: none; }
.audit-toolbar select { padding: 0 12px; }
.audit-search > div { position: relative; }
.audit-search svg { position: absolute; left: 12px; top: 13px; color: #8190a5; }
.audit-search input { padding: 0 12px 0 38px; }
.audit-toolbar select:focus, .audit-toolbar input:focus { border-color: #5b7fb2; box-shadow: 0 0 0 3px rgba(48, 79, 126, .12); }
.audit-toolbar-summary { display: flex; align-items: center; gap: 12px; padding-bottom: 1px; color: #62708a; font-size: 12px; font-weight: 700; white-space: nowrap; }
.audit-board-scroll { overflow-x: auto; padding-bottom: 8px; }
.audit-kanban { display: grid; grid-template-columns: repeat(7, minmax(180px, 1fr)); gap: 10px; min-width: 1320px; align-items: stretch; }
.audit-column { display: grid; grid-template-rows: auto 1fr; min-height: 510px; overflow: hidden; border: 1px solid #e4e9f1; border-radius: 10px; background: #f5f7fa; transition: border-color .15s ease, box-shadow .15s ease; }
.audit-column.is-over { border-color: #5b7fb2; box-shadow: inset 0 0 0 2px rgba(48, 79, 126, .12); }
.audit-column > header { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 46px; padding: 10px 11px; color: #fff; }
.audit-column > header span { font-size: 11px; font-weight: 800; line-height: 1.25; }
.audit-column > header strong { display: grid; place-items: center; min-width: 23px; height: 23px; padding: 0 6px; border-radius: 999px; background: rgba(255,255,255,.2); font-size: 11px; }
.audit-column-body { display: flex; flex-direction: column; gap: 8px; padding: 9px; }
.audit-contract-card { overflow: hidden; border: 1px solid #e2e7ee; border-radius: 8px; background: #fff; box-shadow: 0 3px 9px rgba(32,50,74,.08); transition: opacity .15s ease, transform .15s ease, box-shadow .15s ease; }
.audit-contract-card[draggable="true"] { cursor: grab; }
.audit-contract-card[draggable="true"]:active { cursor: grabbing; }
.audit-contract-card:hover { transform: translateY(-1px); box-shadow: 0 6px 14px rgba(32,50,74,.12); }
.audit-contract-card.is-dragging { opacity: .45; }
.audit-contract-card.is-moving { opacity: .65; pointer-events: none; }
.audit-card-main { display: grid; gap: 7px; width: 100%; padding: 10px; border: 0; background: transparent; color: #20324a; text-align: left; }
.audit-card-main:focus-visible { outline: 2px solid #5b7fb2; outline-offset: -2px; }
.audit-card-topline { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.audit-card-topline strong { font-size: 10px; font-weight: 850; letter-spacing: .025em; text-transform: uppercase; }
.audit-card-topline svg { flex: 0 0 auto; color: #8c98a9; }
.audit-card-supplier { min-height: 30px; color: #263950; font-size: 11px; font-weight: 750; line-height: 1.35; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; overflow: hidden; }
.audit-card-meta { display: flex; align-items: flex-start; gap: 5px; color: #6f7e92; font-size: 9.5px; line-height: 1.35; }
.audit-card-meta svg { flex: 0 0 auto; margin-top: 1px; color: #7890ae; }
.audit-card-move { display: grid; gap: 4px; padding: 8px 10px 10px; border-top: 1px solid #eef1f5; }
.audit-card-move span, .audit-card-readonly { color: #8a97ab; font-size: 8.5px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }
.audit-card-move select { width: 100%; height: 29px; border: 1px solid #dce3ec; border-radius: 6px; background: #f9fafc; padding: 0 7px; color: #34465f; font-size: 9.5px; }
.audit-card-readonly { display: block; padding: 0 10px 10px; }
.audit-column-empty { margin: auto; padding: 28px 8px; color: #9aa5b5; font-size: 10.5px; text-align: center; }
.audit-board-help { margin: 0; color: #7b8798; font-size: 11px; text-align: right; }
@media (max-width: 800px) {
  .audit-toolbar { grid-template-columns: 1fr; }
  .audit-toolbar-summary { justify-content: space-between; white-space: normal; }
  .audit-kanban { grid-template-columns: repeat(7, 230px); min-width: max-content; }
  .audit-column { min-height: 440px; }
}
</style>
