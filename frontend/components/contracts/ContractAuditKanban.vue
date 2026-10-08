<script setup lang="ts">
import { Building2, CalendarDays, GripVertical, Layers3, RefreshCw, Search, WalletCards } from "lucide-vue-next";
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

const occupiedStages = computed(() =>
  STAGES.filter((stage) => filtered.value.some((item) => item.auditStage === stage.key)).length,
);

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
        <button type="button" class="btn" :disabled="loading" @click="load"><RefreshCw class="size-4" />Atualizar</button>
      </div>
    </section>

    <p v-if="error" class="contracts-state error" role="alert">{{ error }}</p>
    <div v-if="loading && !items.length" class="contracts-state">Carregando auditoria…</div>
    <template v-else>
      <section class="audit-summary" aria-label="Resumo do quadro">
        <div class="audit-summary-main">
          <span class="audit-summary-icon"><Layers3 class="size-4" /></span>
          <div>
            <strong>{{ filtered.length }} contrato{{ filtered.length === 1 ? "" : "s" }}</strong>
            <span>Distribuídos em {{ occupiedStages }} {{ occupiedStages === 1 ? "etapa ativa" : "etapas ativas" }}</span>
          </div>
        </div>
        <span class="audit-summary-badge"><GripVertical class="size-3.5" />Arraste entre etapas</span>
      </section>

      <div class="audit-board-scroll">
        <div class="audit-kanban" aria-label="Kanban de auditoria dos contratos vencidos">
        <section
          v-for="(stage, stageIndex) in STAGES"
          :key="stage.key"
          class="audit-column"
          :class="{ 'is-over': overStage === stage.key }"
          :style="{ '--column-accent': stage.color }"
          @dragover.prevent="overStage = stage.key"
          @dragleave.self="overStage = null"
          @drop.prevent="drop(stage.key, $event)"
        >
          <header>
            <div class="audit-column-heading">
              <span class="audit-column-stage">{{ stageIndex + 1 }}</span>
              <h3>{{ stage.label }}</h3>
            </div>
            <span class="audit-column-count">{{ stageItems(stage.key).length }}</span>
          </header>
          <div class="audit-column-accent" />

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

            <p v-if="!stageItems(stage.key).length" class="audit-column-empty"><span />Nenhum contrato</p>
          </div>
        </section>
        </div>
      </div>
      <p class="audit-board-help">O seletor em cada card permite a mesma movimentação pelo teclado.</p>
    </template>
  </div>
</template>

<style scoped>
.audit-board-page { display: grid; gap: 16px; }
.audit-toolbar { display: grid; grid-template-columns: minmax(260px, 1fr) minmax(300px, 1fr) auto; gap: 12px; align-items: end; padding: 16px; }
.audit-toolbar label { display: grid; gap: 6px; }
.audit-toolbar label > span { color: #52657f; font-size: 10px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }
.audit-toolbar select, .audit-toolbar input { width: 100%; height: 42px; border: 1px solid #dbe3ee; border-radius: 10px; background: #fff; color: #20324a; font-size: 13px; outline: none; }
.audit-toolbar select { padding: 0 12px; }
.audit-search > div { position: relative; }
.audit-search svg { position: absolute; left: 12px; top: 13px; color: #8190a5; }
.audit-search input { padding: 0 12px 0 38px; }
.audit-toolbar select:focus, .audit-toolbar input:focus { border-color: #5b7fb2; box-shadow: 0 0 0 3px rgba(48, 79, 126, .12); }
.audit-toolbar-summary { display: flex; align-items: center; padding-bottom: 1px; }
.audit-summary { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 12px 15px; border: 1px solid #e0e6ee; border-radius: 11px; background: #fff; box-shadow: 0 5px 18px rgb(35 55 80 / 4%); }
.audit-summary-main { display: flex; align-items: center; gap: 10px; }
.audit-summary-icon { display: grid; width: 32px; height: 32px; flex: 0 0 32px; place-items: center; border-radius: 8px; background: #edf2f8; color: #304f7e; }
.audit-summary-main > div { display: grid; gap: 1px; }
.audit-summary-main strong { color: #2b3e58; font-size: 11.5px; font-weight: 750; }
.audit-summary-main span { color: #8793a4; font-size: 10px; }
.audit-summary-badge { display: inline-flex; align-items: center; gap: 6px; padding: 5px 9px; border: 1px solid #dbe3ed; border-radius: 999px; background: #f7f9fc; color: #66758a; font-size: 9.5px; font-weight: 700; }
.audit-board-scroll { width: 100%; overflow-x: auto; overflow-y: hidden; padding: 1px 1px 10px; scrollbar-color: #aab3bf #edf1f5; scrollbar-width: thin; }
.audit-board-scroll::-webkit-scrollbar { height: 9px; }
.audit-board-scroll::-webkit-scrollbar-track { border-radius: 999px; background: #edf1f5; }
.audit-board-scroll::-webkit-scrollbar-thumb { border: 2px solid #edf1f5; border-radius: 999px; background: #aab3bf; }
.audit-kanban { display: flex; width: max-content; min-width: 100%; align-items: stretch; gap: 12px; }
.audit-column { --column-accent: #7890ad; display: flex; width: 286px; min-width: 286px; height: clamp(500px, calc(100vh - 360px), 720px); flex-direction: column; overflow: hidden; border: 1px solid #dfe5ed; border-radius: 11px; background: #f4f6f9; box-shadow: 0 4px 14px rgb(31 49 73 / 3%); transition: border-color .15s ease, box-shadow .15s ease; }
.audit-column.is-over { border-color: #5b7fb2; box-shadow: inset 0 0 0 2px rgba(48, 79, 126, .12); }
.audit-column > header { display: flex; min-height: 48px; align-items: center; justify-content: space-between; gap: 10px; padding: 0 12px; background: #fff; }
.audit-column-heading { display: flex; min-width: 0; align-items: center; gap: 7px; }
.audit-column-heading h3 { overflow: hidden; margin: 0; color: #243953; font-size: 11.5px; font-weight: 780; line-height: 1.25; text-overflow: ellipsis; white-space: nowrap; }
.audit-column-stage { display: grid; width: 22px; height: 22px; flex: 0 0 22px; place-items: center; border-radius: 6px; background: color-mix(in srgb, var(--column-accent) 14%, white); color: var(--column-accent); font-size: 9px; font-weight: 800; }
.audit-column-count { display: inline-flex; min-width: 24px; min-height: 24px; align-items: center; justify-content: center; padding: 2px 7px; border: 1px solid #e0e6ee; border-radius: 999px; background: #f8fafc; color: #6f7e91; font-size: 9.5px; font-weight: 760; }
.audit-column-accent { width: 100%; height: 4px; flex: 0 0 4px; background: var(--column-accent); }
.audit-column-body { display: flex; min-height: 0; flex: 1; flex-direction: column; gap: 9px; overflow-y: auto; padding: 10px; scrollbar-color: #aeb7c2 transparent; scrollbar-width: thin; }
.audit-column-body::-webkit-scrollbar { width: 7px; }
.audit-column-body::-webkit-scrollbar-thumb { border: 2px solid transparent; border-radius: 999px; background: #aeb7c2; background-clip: content-box; }
.audit-contract-card { flex: 0 0 auto; overflow: hidden; border: 1px solid #dde4ec; border-radius: 10px; background: #fff; box-shadow: 0 3px 9px rgb(31 48 70 / 3%); transition: opacity .15s ease, transform .15s ease, box-shadow .15s ease, border-color .15s ease; }
.audit-contract-card[draggable="true"] { cursor: grab; }
.audit-contract-card[draggable="true"]:active { cursor: grabbing; }
.audit-contract-card:hover { border-color: #bcc9d8; transform: translateY(-1px); box-shadow: 0 7px 18px rgb(31 48 70 / 8%); }
.audit-contract-card.is-dragging { opacity: .45; }
.audit-contract-card.is-moving { opacity: .65; pointer-events: none; }
.audit-card-main { display: grid; gap: 9px; width: 100%; padding: 12px; border: 0; background: transparent; color: #20324a; text-align: left; }
.audit-card-main:focus-visible { outline: 2px solid #5b7fb2; outline-offset: -2px; }
.audit-card-topline { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.audit-card-topline strong { color: #536b88; font-size: 10px; font-weight: 800; letter-spacing: .025em; text-transform: uppercase; }
.audit-card-topline svg { flex: 0 0 auto; color: #8c98a9; }
.audit-card-supplier { color: #243953; font-size: 12.5px; font-weight: 750; line-height: 1.4; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 3; overflow: hidden; }
.audit-card-meta { display: flex; align-items: flex-start; gap: 5px; color: #77869a; font-size: 10px; font-weight: 550; line-height: 1.4; }
.audit-card-meta svg { flex: 0 0 auto; margin-top: 1px; color: #7890ae; }
.audit-card-move { display: grid; gap: 4px; padding: 9px 12px 11px; border-top: 1px solid #eef1f5; }
.audit-card-move span, .audit-card-readonly { color: #8a97ab; font-size: 8.5px; font-weight: 800; letter-spacing: .04em; text-transform: uppercase; }
.audit-card-move select { width: 100%; height: 31px; border: 1px solid #dce3ec; border-radius: 7px; background: #f9fafc; padding: 0 8px; color: #34465f; font-size: 10px; }
.audit-card-readonly { display: block; padding: 0 10px 10px; }
.audit-column-empty { display: inline-flex; align-items: center; align-self: center; gap: 7px; margin-top: 12px; padding: 7px 9px; color: #9aa5b4; font-size: 10px; font-weight: 500; }
.audit-column-empty span { width: 6px; height: 6px; border-radius: 50%; background: #c8d0da; }
.audit-board-help { margin: 0; color: #7b8798; font-size: 11px; text-align: right; }
@media (max-width: 900px) {
  .audit-toolbar { grid-template-columns: 1fr; }
  .audit-toolbar-summary { justify-content: space-between; white-space: normal; }
  .audit-column { width: 260px; min-width: 260px; }
}
@media (max-width: 700px) {
  .audit-summary { align-items: flex-start; flex-direction: column; }
  .audit-column { width: 238px; min-width: 238px; height: 62vh; }
}
</style>
