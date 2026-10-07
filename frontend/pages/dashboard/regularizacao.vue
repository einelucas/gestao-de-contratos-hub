<script setup lang="ts">
import type { Contract, ContractUpdatePayload, RegularizationStage } from '~/types/api';
import { dateBr } from '~/utils/contracts';
definePageMeta({ middleware: 'auth' });
const api = useApi();
const { contracts, loading, error, loadContracts } = useContracts();
const stages: Array<{ key: RegularizationStage; label: string }> = [
  { key: 'aguardando_analise', label: 'Aguardando análise' },
  { key: 'chamados_elos', label: 'Chamados Elos' },
  { key: 'analise_interna', label: 'Análise interna' },
  { key: 'fornecedor_contatado', label: 'Fornecedor contatado' },
  { key: 'em_tratativa', label: 'Em tratativa' },
  { key: 'em_finalizacao', label: 'Em finalização' },
];
const search = ref('');
const unit = ref('');
const saving = ref(false);
const message = ref('');
const selected = ref<Contract | null>(null);
const picker = ref(false);
const dragged = ref<string | null>(null);
const form = reactive({ stage: 'aguardando_analise' as RegularizationStage, responsible: '', deadline: '', notes: '', endDate: '' });
const units = computed(() => [...new Set(contracts.value.map(c => c.unit).filter(Boolean))].sort());
const filtered = computed(() => contracts.value.filter(c => (!unit.value || c.unit === unit.value) && `${c.supplier} ${c.contractNumber} ${c.regularizationResponsible ?? ''}`.toLowerCase().includes(search.value.toLowerCase())));
const board = computed(() => filtered.value.filter(c => c.regularizationStage && !c.finalized));
const candidates = computed(() => filtered.value.filter(c => !c.regularizationStage && !c.finalized && c.canEdit));
const stageLabel = (key: string | null) => stages.find(s => s.key === key)?.label ?? 'Concluído';
const late = (c: Contract) => !!c.regularizationDeadline && c.regularizationDeadline < (new Date().getFullYear() + '-' + String(new Date().getMonth() + 1).padStart(2, '0') + '-' + String(new Date().getDate()).padStart(2, '0'));
function open(c: Contract) {
  selected.value = c;
  Object.assign(form, { stage: c.regularizationStage ?? 'aguardando_analise', responsible: c.regularizationResponsible ?? c.responsibleUserName ?? '', deadline: c.regularizationDeadline ?? '', notes: c.regularizationNotes ?? '', endDate: c.endDate ?? '' });
  message.value = '';
}
async function update(c: Contract, payload: ContractUpdatePayload) {
  if (saving.value || !c.canEdit) return;
  saving.value = true; message.value = '';
  try {
    const updated = await api.patch<Contract>(`/contratos/${c.id}`, payload);
    contracts.value = contracts.value.map(item => item.id === c.id ? updated : item);
    if (selected.value?.id === c.id) selected.value = updated;
    return updated;
  } catch (cause) { message.value = cause instanceof Error ? cause.message : 'Não foi possível salvar.'; }
  finally { saving.value = false; }
}
async function save() {
  if (!selected.value) return;
  const saved = await update(selected.value, { regularizationStage: form.stage, regularizationResponsible: form.responsible.trim() || null, regularizationDeadline: form.deadline || null, regularizationNotes: form.notes.trim() || null });
  if (saved) selected.value = null;
}
async function complete(finalized: boolean) {
  if (!selected.value) return;
  const saved = await update(selected.value, { regularizationStage: null, finalized, ...(finalized ? {} : { endDate: form.endDate || null }) });
  if (saved) selected.value = null;
}
async function drop(stage: RegularizationStage) {
  const c = contracts.value.find(item => item.id === dragged.value);
  dragged.value = null;
  if (c && c.regularizationStage !== stage) await update(c, { regularizationStage: stage });
}
onMounted(() => loadContracts());
</script>

<template>
  <ModuleWorkspace eyebrow="Projetos e Arquitetura · Contratos" title="Regularização" description="Acompanhe cada tratativa, seus responsáveis e a próxima etapa.">
    <section class="surface board-toolbar">
      <input v-model="search" aria-label="Buscar contratos" placeholder="Buscar fornecedor, contrato ou responsável" />
      <select v-model="unit" aria-label="Filtrar por unidade"><option value="">Todas as unidades</option><option v-for="u in units" :key="u">{{ u }}</option></select>
      <button class="btn" :disabled="loading || saving" @click="loadContracts()">Atualizar</button>
      <button class="btn primary" :disabled="saving" @click="picker = true">Adicionar contrato</button>
    </section>
    <p class="board-summary">{{ board.length }} contratos em regularização · {{ board.filter(late).length }} com prazo da tratativa atrasado</p>
    <p v-if="error || message" role="alert" class="contracts-state error">{{ error || message }}</p>
    <p v-if="loading" role="status">Carregando contratos…</p>
    <div v-else class="kanban" aria-label="Etapas da regularização" :aria-busy="saving">
      <section v-for="stage in stages" :key="stage.key" class="kanban-column" @dragover.prevent @drop.prevent="drop(stage.key)">
        <header><h2>{{ stage.label }}</h2><span>{{ board.filter(c => c.regularizationStage === stage.key).length }}</span></header>
        <article v-for="c in board.filter(c => c.regularizationStage === stage.key)" :key="c.id" class="kanban-card" :draggable="c.canEdit && !saving" @dragstart="dragged = c.id" @dragend="dragged = null">
          <button class="card-open" @click="open(c)"><strong>{{ c.supplier }}</strong><span>Contrato {{ c.contractNumber }}</span></button>
          <p>{{ c.unit || 'Unidade não informada' }}</p>
          <p>{{ c.regularizationResponsible || 'Responsável não definido' }}</p>
          <p :class="{ overdue: late(c) }">{{ c.regularizationDeadline ? `Prazo: ${dateBr(c.regularizationDeadline)}` : 'Prazo não definido' }}<span v-if="late(c)"> · Atrasado</span></p>
          <label class="move-label">Mover para<select :value="c.regularizationStage" :disabled="!c.canEdit || saving" @change="update(c, { regularizationStage: ($event.target as HTMLSelectElement).value as RegularizationStage })"><option v-for="s in stages" :key="s.key" :value="s.key">{{ s.label }}</option></select></label>
        </article>
        <p v-if="!board.some(c => c.regularizationStage === stage.key)" class="empty-column">Nenhum contrato nesta etapa</p>
      </section>
    </div>
    <AppModal :open="picker" title="Adicionar contrato à regularização" @close="picker = false">
      <p>Escolha um contrato. A etapa e o responsável serão definidos na próxima tela.</p>
      <p v-if="!candidates.length">Nenhum contrato disponível com permissão de edição.</p>
      <button v-for="c in candidates" :key="c.id" class="candidate" @click="picker = false; open(c)"><strong>{{ c.supplier }}</strong> · {{ c.contractNumber }} · {{ c.unit || 'Sem unidade' }}<ContractStatusBadge :alert="c.alert" /></button>
    </AppModal>
    <AppModal :open="!!selected" :title="selected ? `Contrato ${selected.contractNumber}` : 'Contrato'" wide @close="selected = null">
      <template v-if="selected">
        <h3>{{ selected.supplier }}</h3>
        <p>{{ selected.serviceDescription }}</p>
        <div class="detail-grid"><p><strong>Unidade</strong>{{ selected.unit || 'Não informada' }}</p><p><strong>Setor</strong>{{ selected.sectorName }}</p><p><strong>Vigência original</strong>{{ dateBr(selected.endDate) }} · {{ selected.situation }}</p></div>
        <fieldset :disabled="!selected.canEdit || saving" class="edit-grid">
          <label>Status da tratativa<select v-model="form.stage"><option v-for="s in stages" :key="s.key" :value="s.key">{{ s.label }}</option></select></label>
          <label>Responsável<input v-model="form.responsible" maxlength="180" placeholder="Nome do responsável" /></label>
          <label>Prazo da tratativa<input v-model="form.deadline" type="date" /></label>
          <label class="full">Próxima ação / observações<textarea v-model="form.notes" maxlength="10000" rows="3" /></label>
        </fieldset>
        <p v-if="message" role="alert" class="overdue">{{ message }}</p>
        <button v-if="selected.canEdit" class="btn primary" :disabled="saving" @click="save">{{ saving ? 'Salvando…' : 'Salvar acompanhamento' }}</button>
        <section v-if="selected.regularizationStage && selected.canEdit" class="completion"><h3>Concluir regularização</h3><p>Registre a nova vigência para renovar ou encerre o contrato. Em finalização ainda é uma etapa ativa.</p><label>Nova data de vencimento<input v-model="form.endDate" type="date" /></label><button class="btn" :disabled="saving" @click="complete(false)">Confirmar renovação</button><button class="btn" :disabled="saving" @click="complete(true)">Finalizar contrato</button></section>
        <section class="history"><h3>Histórico de acompanhamento</h3><p v-if="!selected.regularizationHistory?.length">Nenhuma movimentação registrada.</p><article v-for="(event, index) in [...(selected.regularizationHistory ?? [])].reverse()" :key="index"><strong>{{ stageLabel(event.stage) }}</strong><p>{{ new Date(event.date).toLocaleString('pt-BR') }} · {{ event.user }}</p><p v-if="event.previousStage">Anterior: {{ stageLabel(event.previousStage) }}</p><p>Responsável: {{ event.responsible || 'Não definido' }} · Prazo: {{ dateBr(event.deadline) }}</p><p v-if="event.notes">{{ event.notes }}</p></article></section>
      </template>
    </AppModal>
  </ModuleWorkspace>
</template>
<style scoped>
.board-toolbar{display:flex;flex-wrap:wrap;gap:12px;padding:18px}.board-toolbar input{flex:1;min-width:220px}input,select,textarea{border:1px solid #d8e2ef;border-radius:8px;background:white;padding:10px;color:#263c58;max-width:100%}.board-summary{margin:18px 0;color:#536883}.kanban{display:grid;grid-template-columns:repeat(6,minmax(245px,1fr));gap:16px;overflow-x:auto;padding-bottom:20px}.kanban-column{background:#edf2f8;border:1px solid #dce5ef;border-radius:14px;padding:12px;min-height:350px}.kanban-column>header{display:flex;align-items:center;justify-content:space-between;border-top:3px solid #397ac1;padding:14px 0;gap:8px}.kanban-column h2{font-size:14px;font-weight:700}.kanban-column header span{background:#dbe8fa;border-radius:20px;padding:3px 9px;color:#245fa9}.kanban-card{background:white;border:1px solid #dfe7f0;border-radius:10px;padding:14px;margin-bottom:12px;box-shadow:0 3px 10px #20324a08}.card-open{display:grid;gap:5px;text-align:left;width:100%}.card-open strong{font-size:15px;color:#203b5f}.card-open span,.kanban-card p{font-size:12px;color:#61748e;margin:8px 0;overflow-wrap:anywhere}.move-label{display:grid;gap:4px;font-size:11px;color:#61748e}.move-label select{font-size:12px;width:100%}.empty-column{font-size:12px;color:#8291a5;text-align:center;padding:28px 0}.overdue{color:#ba382f!important}.candidate{display:flex;flex-wrap:wrap;gap:8px;width:100%;padding:14px;border-bottom:1px solid #e2e8f0;text-align:left}.detail-grid,.edit-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:20px 0}.detail-grid strong{display:block;color:#61748e;font-size:12px}.edit-grid label{display:grid;gap:6px;font-size:13px}.full{grid-column:1/-1}.completion,.history{margin-top:24px;border-top:1px solid #e1e8f1;padding-top:18px}.completion{display:flex;flex-wrap:wrap;gap:12px}.completion h3,.completion p{width:100%}.history article{border-left:3px solid #397ac1;padding:10px 15px;margin-top:12px;background:#f4f7fb;font-size:13px}.primary{background:#304f7e;color:white}@media(max-width:650px){.detail-grid,.edit-grid{grid-template-columns:1fr}}
</style>
