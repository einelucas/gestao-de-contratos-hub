<script setup lang="ts">
import { RefreshCw, RotateCw } from "lucide-vue-next";
import type { ContractNotification, ContractNotificationList } from "~/types/api";
import { formatDate } from "~/utils/format";
import { dateBr } from "~/utils/contracts";
import {
  NOTIFICATION_STATUS_LABEL,
  PROVIDER_LABEL,
  milestoneLabel,
  notificationStatusTone,
} from "~/utils/notifications";

const props = defineProps<{ contractId: string }>();

const api = useApi();
const { store } = useAuth();
const items = ref<ContractNotification[]>([]);
const loading = ref(false);
const error = ref("");
const resending = ref<string | null>(null);
const canResend = computed(() => store.can("alerts:manage"));

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    items.value = (await api.get<ContractNotificationList>(`/contratos/${props.contractId}/notificacoes`)).items;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível carregar o histórico.";
  } finally {
    loading.value = false;
  }
}

async function resend(item: ContractNotification): Promise<void> {
  resending.value = item.id;
  error.value = "";
  try {
    await api.post(`/notificacoes-contratos/${item.id}/reenviar`);
    await load();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível reenviar.";
  } finally {
    resending.value = null;
  }
}

watch(() => props.contractId, load, { immediate: true });
defineExpose({ load });
</script>

<template>
  <section class="notification-history">
    <div class="section-head">
      <h3>Histórico de alertas por e-mail</h3>
      <button type="button" class="drawer-icon-button" title="Atualizar" :disabled="loading" @click="load">
        <RefreshCw class="size-3.5" />
      </button>
    </div>
    <p v-if="error" class="form-error">{{ error }}</p>
    <p v-if="loading && !items.length" class="history-empty">Carregando…</p>
    <p v-else-if="!items.length" class="history-empty">Nenhum alerta gerado para este contrato.</p>
    <ol v-else class="history-list">
      <li v-for="item in items" :key="item.id">
        <div class="history-line">
          <span class="pill" :class="notificationStatusTone(item.status)">{{ NOTIFICATION_STATUS_LABEL[item.status] }}</span>
          <strong>{{ milestoneLabel(item.type, item.noticeDays) }}</strong>
          <span class="muted">· vigência até {{ dateBr(item.contractEndDate) }}</span>
        </div>
        <div class="history-meta">
          <span>{{ item.recipient || "sem destinatário" }}</span>
          <span>{{ formatDate(item.sentAt || item.lastAttemptAt || item.createdAt, true) }}</span>
          <span v-if="item.attempts > 1">{{ item.attempts }} tentativas</span>
          <span v-if="item.provider">{{ PROVIDER_LABEL[item.provider] ?? item.provider }}</span>
        </div>
        <p v-if="item.error" class="history-error">{{ item.error }}</p>
        <button
          v-if="canResend && item.canRetry"
          type="button"
          class="btn small"
          :disabled="resending === item.id"
          @click="resend(item)"
        >
          <RotateCw class="size-3.5" />{{ resending === item.id ? "Reenviando…" : "Reenviar" }}
        </button>
      </li>
    </ol>
  </section>
</template>
