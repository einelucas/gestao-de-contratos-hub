<script setup lang="ts">
import { AlertTriangle, BellRing, CheckCircle2 } from "lucide-vue-next";
import type {
  Contract,
  ContractCreatePayload,
  ContractCriticality,
  ContractUpdatePayload,
  NotificationTeam,
  Sector,
} from "~/types/api";
import { contractTeamProblem, money, type TeamsLoadStatus } from "~/utils/contracts";
import { CRITICALITY_LABEL, REMINDER_SCHEDULE } from "~/utils/notifications";

/**
 * Formulário único de contrato (criação e edição) — os dois fluxos usam as mesmas
 * regras de validação e o mesmo layout.
 */
const props = defineProps<{
  open: boolean;
  mode: "create" | "edit";
  contract?: Contract | null;
  /** Setores visíveis ao usuário (com `canEdit`); só os editáveis aparecem no seletor. */
  sectors: Sector[];
}>();
const emit = defineEmits<{ close: []; saved: [contract: Contract] }>();

const api = useApi();
const saving = ref(false);
const error = ref("");
const notice = ref("");
const teamsBySector = ref<Record<string, NotificationTeam[]>>({});
// Status separado da lista: "erro ao consultar" não pode virar "setor sem equipes".
const teamsStatus = ref<Record<string, TeamsLoadStatus>>({});
const loadingTeams = computed(() => teamsStatus.value[form.sectorId] === "loading");
const teamsError = computed(() => teamsStatus.value[form.sectorId] === "error");

interface FormState {
  contractNumber: string;
  sectorId: string;
  supplier: string;
  serviceDescription: string;
  unit: string;
  startDate: string;
  endDate: string;
  finalized: boolean;
  serviceValue: number;
  ownMaterialValue: number;
  thirdPartyMaterialValue: number;
  notify: boolean;
  notificationTeamId: string;
  autoRenewal: boolean;
  criticality: ContractCriticality | "";
}

function blank(): FormState {
  return {
    contractNumber: "", sectorId: "", supplier: "", serviceDescription: "", unit: "", startDate: "", endDate: "",
    finalized: false, serviceValue: 0, ownMaterialValue: 0, thirdPartyMaterialValue: 0, notify: false,
    notificationTeamId: "", autoRenewal: false, criticality: "",
  };
}

function fromContract(contract: Contract): FormState {
  return {
    contractNumber: contract.contractNumber,
    sectorId: contract.sectorId,
    supplier: contract.supplier,
    serviceDescription: contract.serviceDescription,
    unit: contract.unit,
    startDate: contract.startDate ?? "",
    endDate: contract.endDate ?? "",
    finalized: contract.finalized,
    serviceValue: Number(contract.serviceValue || 0),
    ownMaterialValue: Number(contract.ownMaterialValue || 0),
    thirdPartyMaterialValue: Number(contract.thirdPartyMaterialValue || 0),
    notify: contract.notify,
    notificationTeamId: contract.notificationTeamId ?? "",
    autoRenewal: contract.autoRenewal,
    criticality: contract.criticality ?? "",
  };
}

const form = reactive<FormState>(blank());
let initial: FormState = { ...form };

const editableSectors = computed(() =>
  props.sectors.filter((sector) => sector.canEdit || sector.id === props.contract?.sectorId),
);
const title = computed(() =>
  props.mode === "create" ? "Novo contrato" : `Editar contrato ${props.contract?.contractNumber ?? ""}`,
);

async function loadTeams(sectorId: string, { force = false } = {}): Promise<void> {
  if (!sectorId) return;
  const status = teamsStatus.value[sectorId];
  if (status === "loading" || (status === "loaded" && !force)) return;
  teamsStatus.value = { ...teamsStatus.value, [sectorId]: "loading" };
  try {
    const response = await api.get<{ items: NotificationTeam[] }>("/equipes-notificacao", { setorId: sectorId });
    teamsBySector.value = { ...teamsBySector.value, [sectorId]: response.items };
    teamsStatus.value = { ...teamsStatus.value, [sectorId]: "loaded" };
  } catch {
    // Não zera a lista: a equipe atual continua valendo até o servidor dizer o contrário.
    teamsStatus.value = { ...teamsStatus.value, [sectorId]: "error" };
  }
}

watch(
  () => [props.open, props.mode, props.contract?.id] as const,
  ([open]) => {
    if (!open) return;
    Object.assign(form, props.mode === "edit" && props.contract ? fromContract(props.contract) : blank());
    if (props.mode === "create" && editableSectors.value.length === 1) form.sectorId = editableSectors.value[0]!.id;
    initial = { ...form };
    error.value = "";
    notice.value = "";
    teamsBySector.value = {};
    teamsStatus.value = {};
    void loadTeams(form.sectorId);
  },
  { immediate: true },
);

// Trocar o setor invalida a equipe do setor anterior (backend também recusa a combinação).
watch(
  () => form.sectorId,
  async (sectorId, previous) => {
    await loadTeams(sectorId);
    // Só invalida com a lista do novo setor de fato carregada; em erro, o backend decide ao salvar.
    if (teamsStatus.value[sectorId] !== "loaded") return;
    if (previous !== undefined && sectorId !== previous && form.notificationTeamId) {
      const stillValid = (teamsBySector.value[sectorId] ?? []).some((team) => team.id === form.notificationTeamId);
      if (!stillValid) {
        form.notificationTeamId = "";
        notice.value = "A equipe de notificação foi removida porque pertence a outro setor. Selecione uma equipe do novo setor.";
      }
    }
  },
);

const sectorTeams = computed(() => teamsBySector.value[form.sectorId] ?? []);
const selectedTeam = computed(() => sectorTeams.value.find((team) => team.id === form.notificationTeamId) ?? null);
const teamWarning = computed(() => {
  const team = selectedTeam.value;
  if (!team) return "";
  if (!team.active) return `A equipe "${team.name}" está desativada.`;
  if (!team.activeMemberCount) return `A equipe "${team.name}" não tem membros ativos — nenhum e-mail seria enviado.`;
  return "";
});
const valuesChanged = computed(
  () =>
    form.serviceValue !== initial.serviceValue ||
    form.ownMaterialValue !== initial.ownMaterialValue ||
    form.thirdPartyMaterialValue !== initial.thirdPartyMaterialValue,
);
const computedTotal = computed(
  () => Number(form.serviceValue || 0) + Number(form.ownMaterialValue || 0) + Number(form.thirdPartyMaterialValue || 0),
);

function validate(): string {
  if (props.mode === "create" && !form.contractNumber.trim()) return "Informe o número do contrato.";
  if (!form.sectorId) return "Selecione o setor.";
  if (!form.supplier.trim()) return "Informe o fornecedor.";
  if (form.startDate && form.endDate && form.endDate < form.startDate)
    return "O fim da vigência não pode ser anterior ao início.";
  if ([form.serviceValue, form.ownMaterialValue, form.thirdPartyMaterialValue].some((value) => Number(value) < 0))
    return "Valores não podem ser negativos.";
  const teamProblem = contractTeamProblem({
    teamId: form.notificationTeamId,
    notify: form.notify,
    teamsStatus: teamsStatus.value[form.sectorId],
    teamFound: Boolean(selectedTeam.value),
    teamWarning: teamWarning.value,
  });
  if (teamProblem) return teamProblem;
  return "";
}

function createPayload(): ContractCreatePayload {
  return {
    contractNumber: form.contractNumber.trim(),
    sectorId: form.sectorId,
    supplier: form.supplier.trim(),
    serviceDescription: form.serviceDescription.trim(),
    unit: form.unit.trim(),
    startDate: form.startDate || null,
    endDate: form.endDate || null,
    finalized: form.finalized,
    serviceValue: Number(form.serviceValue || 0),
    ownMaterialValue: Number(form.ownMaterialValue || 0),
    thirdPartyMaterialValue: Number(form.thirdPartyMaterialValue || 0),
    notify: form.notify,
    notificationTeamId: form.notificationTeamId || null,
    autoRenewal: form.autoRenewal,
    criticality: form.criticality || null,
  };
}

/** Edição: só os campos alterados — o backend audita exatamente o que foi enviado. */
function updatePayload(): ContractUpdatePayload {
  const changes: ContractUpdatePayload = {};
  const changed = <K extends keyof FormState>(key: K) => form[key] !== initial[key];
  if (changed("sectorId")) changes.sectorId = form.sectorId;
  if (changed("supplier")) changes.supplier = form.supplier.trim();
  if (changed("serviceDescription")) changes.serviceDescription = form.serviceDescription.trim();
  if (changed("unit")) changes.unit = form.unit.trim();
  if (changed("startDate")) changes.startDate = form.startDate || null;
  if (changed("endDate")) changes.endDate = form.endDate || null;
  if (changed("finalized")) changes.finalized = form.finalized;
  if (changed("serviceValue")) changes.serviceValue = Number(form.serviceValue || 0);
  if (changed("ownMaterialValue")) changes.ownMaterialValue = Number(form.ownMaterialValue || 0);
  if (changed("thirdPartyMaterialValue")) changes.thirdPartyMaterialValue = Number(form.thirdPartyMaterialValue || 0);
  if (changed("notify")) changes.notify = form.notify;
  if (changed("notificationTeamId")) changes.notificationTeamId = form.notificationTeamId || null;
  if (changed("autoRenewal")) changes.autoRenewal = form.autoRenewal;
  if (changed("criticality")) changes.criticality = form.criticality || null;
  return changes;
}

async function submit(): Promise<void> {
  error.value = validate();
  if (error.value) return;
  saving.value = true;
  try {
    if (props.mode === "create") {
      emit("saved", await api.post<Contract>("/contratos", createPayload()));
    } else if (props.contract) {
      const changes = updatePayload();
      if (!Object.keys(changes).length) {
        emit("close");
        return;
      }
      emit("saved", await api.patch<Contract>(`/contratos/${props.contract.id}`, changes));
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível salvar o contrato.";
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <AppModal :open="open" :title="title" @close="emit('close')">
    <form id="contract-form" class="contract-form" @submit.prevent="submit">
      <fieldset>
        <legend>Dados do contrato</legend>
        <div class="form-grid">
          <label>
            <span>Número do contrato</span>
            <input v-if="mode === 'create'" v-model="form.contractNumber" required maxlength="80" placeholder="Ex.: 21634" />
            <input v-else :value="form.contractNumber" disabled />
          </label>
          <label>
            <span>Setor</span>
            <select v-if="editableSectors.length > 1" v-model="form.sectorId" required>
              <option value="" disabled>Selecione o setor</option>
              <option v-for="sector in editableSectors" :key="sector.id" :value="sector.id">{{ sector.name }}</option>
            </select>
            <input v-else :value="editableSectors[0]?.name ?? ''" disabled />
          </label>
          <label class="span-2"><span>Fornecedor</span><input v-model="form.supplier" required maxlength="240" /></label>
          <label class="span-2"><span>Prestação / objeto</span><textarea v-model="form.serviceDescription" rows="2" /></label>
          <label><span>Unidade</span><input v-model="form.unit" maxlength="120" /></label>
          <label class="checkbox-field"><input v-model="form.finalized" type="checkbox" /><span>Contrato finalizado</span></label>
          <label><span>Início da vigência</span><input v-model="form.startDate" type="date" /></label>
          <label><span>Fim da vigência</span><input v-model="form.endDate" type="date" /></label>
          <label>
            <span>Criticidade</span>
            <select v-model="form.criticality">
              <option value="">Não informada</option>
              <option v-for="(label, key) in CRITICALITY_LABEL" :key="key" :value="key">{{ label }}</option>
            </select>
          </label>
          <label class="checkbox-field"><input v-model="form.autoRenewal" type="checkbox" /><span>Renovação automática</span></label>
        </div>
      </fieldset>

      <fieldset>
        <legend>Valores</legend>
        <div class="form-grid three">
          <label><span>Serviço (R$)</span><input v-model.number="form.serviceValue" type="number" min="0" step="0.01" /></label>
          <label><span>Material próprio (R$)</span><input v-model.number="form.ownMaterialValue" type="number" min="0" step="0.01" /></label>
          <label><span>Material terceiros (R$)</span><input v-model.number="form.thirdPartyMaterialValue" type="number" min="0" step="0.01" /></label>
        </div>
        <p class="form-hint">
          <template v-if="mode === 'edit' && contract">Total atual: <strong>{{ money(contract.totalValue) }}</strong></template>
          <template v-if="mode === 'create' || valuesChanged">
            <template v-if="mode === 'edit'"> · </template>Total calculado: <strong>{{ money(computedTotal) }}</strong>
          </template>
        </p>
      </fieldset>

      <fieldset>
        <legend><BellRing class="size-4" />Alertas de vencimento por e-mail</legend>
        <div class="form-grid">
          <label class="checkbox-field span-2"><input v-model="form.notify" type="checkbox" /><span>Enviar alertas de vencimento por e-mail</span></label>
          <label class="span-2">
            <span>Equipe de notificação</span>
            <select v-model="form.notificationTeamId" :disabled="!form.sectorId || loadingTeams">
              <option value="">{{ !form.sectorId ? "Selecione o setor primeiro" : "Nenhuma equipe" }}</option>
              <option v-if="form.notificationTeamId && !selectedTeam && !loadingTeams" :value="form.notificationTeamId">
                {{ teamsError ? "Equipe atual (lista indisponível)" : "Equipe atual" }}
              </option>
              <option v-for="team in sectorTeams" :key="team.id" :value="team.id" :disabled="!team.active && team.id !== initial.notificationTeamId">
                {{ team.name }} · {{ team.activeMemberCount }} destinatário(s){{ team.active ? "" : " · desativada" }}
              </option>
            </select>
          </label>
        </div>
        <p v-if="teamsError" class="form-hint warning-text">
          <AlertTriangle class="size-3.5" />Não foi possível consultar as equipes deste setor. A equipe atual foi mantida.
          <button type="button" class="link-button" @click="loadTeams(form.sectorId, { force: true })">Tentar novamente</button>
        </p>
        <p v-else-if="form.sectorId && teamsStatus[form.sectorId] === 'loaded' && !sectorTeams.length" class="form-hint">
          <AlertTriangle class="size-3.5" />Este setor ainda não tem equipe de notificação. Um administrador pode cadastrá-la em “Equipes”.
        </p>
        <p v-if="notice" class="form-hint warning-text"><AlertTriangle class="size-3.5" />{{ notice }}</p>
        <p v-if="teamWarning" class="form-hint warning-text"><AlertTriangle class="size-3.5" />{{ teamWarning }}</p>
        <div v-if="form.notify" class="reminder-schedule">
          <strong>Lembretes automáticos</strong>
          <ul>
            <li v-for="item in REMINDER_SCHEDULE" :key="item"><CheckCircle2 class="size-3.5" />{{ item }}</li>
          </ul>
          <p v-if="selectedTeam && selectedTeam.activeMemberCount" class="form-hint">
            Cada um dos {{ selectedTeam.activeMemberCount }} membro(s) ativo(s) de “{{ selectedTeam.name }}” recebe o próprio e-mail.
            O status “Atenção” do painel continua usando a janela fixa de 20 dias.
          </p>
        </div>
      </fieldset>

      <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    </form>
    <template #actions>
      <button type="button" class="btn" :disabled="saving" @click="emit('close')">Cancelar</button>
      <button type="submit" form="contract-form" class="btn primary" :disabled="saving">
        {{ saving ? "Salvando…" : mode === "create" ? "Criar contrato" : "Salvar alterações" }}
      </button>
    </template>
  </AppModal>
</template>

<style scoped>
.link-button {
  margin-left: 6px;
  padding: 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  font-weight: 700;
  text-decoration: underline;
  cursor: pointer;
}
</style>
