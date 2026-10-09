<script setup lang="ts">
import { AlarmClock, BellOff, BellRing, Check, Copy, Eye, Pencil, Trash2, TriangleAlert, X } from "lucide-vue-next";
import type { Contract, Sector } from "~/types/api";
import { dateBr, daysToEndLabel, money, overdueDays, overdueLabel } from "~/utils/contracts";
import { CRITICALITY_LABEL, REMINDER_SCHEDULE } from "~/utils/notifications";

const props = defineProps<{ contract: Contract | null; sectors: Sector[] }>();
const emit = defineEmits<{ close: []; updated: [contract: Contract]; deleted: [contractId: string] }>();
const api = useApi();

const editing = ref(false);
const previewing = ref(false);
const deleting = ref(false);
const deleteBusy = ref(false);
const deleteError = ref("");
const deleteConfirmation = ref("");
const copied = ref(false);
let copiedTimer: ReturnType<typeof setTimeout> | undefined;
const lateDays = computed(() => (props.contract ? overdueDays(props.contract) : null));

async function copyNumber(): Promise<void> {
  if (!props.contract) return;
  try {
    await navigator.clipboard.writeText(props.contract.contractNumber);
    copied.value = true;
    clearTimeout(copiedTimer);
    copiedTimer = setTimeout(() => { copied.value = false; }, 1500);
  } catch {
    copied.value = false;
  }
}
onBeforeUnmount(() => clearTimeout(copiedTimer));

watch(() => props.contract?.id, () => {
  copied.value = false;
  editing.value = false;
  previewing.value = false;
  deleting.value = false;
  deleteBusy.value = false;
  deleteError.value = "";
  deleteConfirmation.value = "";
});

function onSaved(updated: Contract): void {
  editing.value = false;
  emit("updated", updated);
}

function openDeleteConfirmation(): void {
  deleteConfirmation.value = "";
  deleteError.value = "";
  deleting.value = true;
}

function closeDeleteConfirmation(): void {
  if (deleteBusy.value) return;
  deleting.value = false;
  deleteConfirmation.value = "";
  deleteError.value = "";
}

async function confirmDelete(): Promise<void> {
  const contract = props.contract;
  if (!contract || deleteConfirmation.value.trim() !== contract.contractNumber || deleteBusy.value) return;
  deleteBusy.value = true;
  deleteError.value = "";
  try {
    await api.delete<unknown>(`/contratos/${contract.id}`);
    deleting.value = false;
    emit("deleted", contract.id);
  } catch (cause) {
    deleteError.value = cause instanceof Error ? cause.message : "Não foi possível excluir o contrato.";
  } finally {
    deleteBusy.value = false;
  }
}
</script>
<template>
  <Teleport to="body">
    <div v-if="contract" class="drawer-backdrop" @click.self="emit('close')">
      <aside class="contract-drawer" aria-label="Detalhes do contrato">
        <header>
          <div>
            <div class="drawer-contract-number">
              <span class="drawer-eyebrow">Contrato {{ contract.contractNumber }}</span>
              <button
                type="button"
                class="copy-number-button"
                :class="{ copied }"
                :aria-label="copied ? 'Número copiado' : 'Copiar número do contrato'"
                :title="copied ? 'Copiado!' : 'Copiar número do contrato'"
                @click="copyNumber"
              >
                <component :is="copied ? Check : Copy" class="size-3.5" />
              </button>
            </div>
            <h2>{{ contract.supplier }}</h2>
          </div>
          <div class="drawer-actions">
            <button v-if="contract.canEdit" type="button" class="btn small danger-outline" @click="openDeleteConfirmation"><Trash2 class="size-3.5" />Excluir</button>
            <button v-if="contract.canEdit" type="button" class="btn small" @click="editing = true"><Pencil class="size-3.5" />Editar</button>
            <button class="drawer-close" aria-label="Fechar" @click="emit('close')"><X class="size-5" /></button>
          </div>
        </header>
        <div class="drawer-body">
          <div class="drawer-status-line">
            <ContractStatusBadge :alert="contract.alert" />
            <span v-if="lateDays !== null" class="contract-overdue"><AlarmClock class="size-3.5" />{{ overdueLabel(lateDays) }}</span>
            <span>{{ contract.unit }}</span><span>{{ contract.sectorName }}</span>
            <span v-if="contract.criticality" class="pill" :class="`criticality-${contract.criticality.toLowerCase()}`">
              Criticidade {{ CRITICALITY_LABEL[contract.criticality] }}
            </span>
          </div>
          <section><h3>Vigência</h3><div class="detail-grid"><div><span>Início</span><strong>{{ dateBr(contract.startDate) }}</strong></div><div><span>Fim</span><strong>{{ dateBr(contract.endDate) }}</strong></div><div><span>Dias para vencer</span><strong>{{ daysToEndLabel(contract.daysToEnd) }}</strong></div><div><span>Renovação automática</span><strong>{{ contract.autoRenewal ? 'Sim' : 'Não' }}</strong></div></div></section>
          <section>
            <h3 class="with-icon">
              <component :is="contract.notify ? BellRing : BellOff" class="size-4" />
              Alertas por e-mail {{ contract.notify ? 'ativados' : 'desativados' }}
            </h3>
            <div class="detail-grid">
              <div><span>Equipe de notificação</span><strong>{{ contract.notificationTeamName || 'Nenhuma' }}</strong></div>
              <div><span>Destinatários ativos</span><strong>{{ contract.notificationRecipients.length }}</strong></div>
            </div>
            <ul v-if="contract.notificationRecipients.length" class="recipient-list">
              <li v-for="email in contract.notificationRecipients" :key="email">{{ email }}</li>
            </ul>
            <p v-if="contract.notify" class="form-hint">Lembretes: {{ REMINDER_SCHEDULE.join(' · ') }}; depois de vencido, a cada 7 dias.</p>
            <p v-if="contract.notificationProblem" class="form-error">
              {{ contract.notificationProblem }} — nenhum e-mail será enviado.
            </p>
            <button type="button" class="btn small section-action" @click="previewing = true"><Eye class="size-3.5" />Visualizar e-mail</button>
          </section>
          <section><h3>Valores</h3><div class="detail-grid"><div><span>Serviço</span><strong>{{ money(contract.serviceValue) }}</strong></div><div><span>Material próprio</span><strong>{{ money(contract.ownMaterialValue) }}</strong></div><div><span>Material terceiros</span><strong>{{ money(contract.thirdPartyMaterialValue) }}</strong></div><div class="detail-total"><span>Total</span><strong>{{ money(contract.totalValue) }}</strong></div></div></section>
          <section><h3>Prestação</h3><p>{{ contract.serviceDescription || 'Não informada.' }}</p></section>
          <ContractNotificationHistory :key="`${contract.id}-${contract.updatedAt}`" :contract-id="contract.id" />
        </div>
      </aside>
    </div>
    <ContractForm mode="edit" :contract="contract" :sectors="sectors" :open="editing" @close="editing = false" @saved="onSaved" />
    <EmailPreviewModal :open="previewing" :contract-id="contract?.id ?? null" @close="previewing = false" />
    <AppModal :open="deleting" title="Excluir contrato" @close="closeDeleteConfirmation">
      <div v-if="contract" class="delete-contract-confirmation">
        <div class="delete-contract-warning">
          <TriangleAlert class="size-5" />
          <div>
            <strong>Esta ação é permanente.</strong>
            <p>O contrato {{ contract.contractNumber }} será removido das listas, do Kanban e dos indicadores do dashboard. O evento permanecerá registrado na auditoria.</p>
          </div>
        </div>
        <label>
          Digite <strong>{{ contract.contractNumber }}</strong> para confirmar
          <input v-model="deleteConfirmation" :disabled="deleteBusy" autocomplete="off" @keyup.enter="confirmDelete" />
        </label>
        <p v-if="deleteError" class="form-error" role="alert">{{ deleteError }}</p>
      </div>
      <template #actions>
        <button type="button" class="btn" :disabled="deleteBusy" @click="closeDeleteConfirmation">Cancelar</button>
        <button
          type="button"
          class="btn danger-solid"
          :disabled="deleteBusy || deleteConfirmation.trim() !== contract?.contractNumber"
          @click="confirmDelete"
        >
          <Trash2 class="size-4" />{{ deleteBusy ? 'Excluindo...' : 'Excluir permanentemente' }}
        </button>
      </template>
    </AppModal>
  </Teleport>
</template>
