<script setup lang="ts">
import { BellOff, BellRing, Eye, Pencil, X } from "lucide-vue-next";
import type { Contract, Sector } from "~/types/api";
import { dateBr, daysToEndLabel, money } from "~/utils/contracts";
import { CRITICALITY_LABEL, REMINDER_SCHEDULE } from "~/utils/notifications";

const props = defineProps<{ contract: Contract | null; sectors: Sector[] }>();
const emit = defineEmits<{ close: []; updated: [contract: Contract] }>();

const editing = ref(false);
const previewing = ref(false);
watch(() => props.contract?.id, () => {
  editing.value = false;
  previewing.value = false;
});

function onSaved(updated: Contract): void {
  editing.value = false;
  emit("updated", updated);
}
</script>
<template>
  <Teleport to="body">
    <div v-if="contract" class="drawer-backdrop" @click.self="emit('close')">
      <aside class="contract-drawer" aria-label="Detalhes do contrato">
        <header>
          <div><span class="drawer-eyebrow">Contrato {{ contract.contractNumber }}</span><h2>{{ contract.supplier }}</h2></div>
          <div class="drawer-actions">
            <button v-if="contract.canEdit" type="button" class="btn small" @click="editing = true"><Pencil class="size-3.5" />Editar</button>
            <button class="drawer-close" aria-label="Fechar" @click="emit('close')"><X class="size-5" /></button>
          </div>
        </header>
        <div class="drawer-body">
          <div class="drawer-status-line">
            <ContractStatusBadge :alert="contract.alert" /><span>{{ contract.unit }}</span><span>{{ contract.sectorName }}</span>
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
  </Teleport>
</template>
