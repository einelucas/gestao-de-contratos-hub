<script setup lang="ts">
import { createLatestRequest } from "~/utils/latestRequest";
import { Eye, Mail, Play, RefreshCw, RotateCw } from "lucide-vue-next";
import type {
  AlertItem,
  AlertRun,
  ContractNotification,
  ContractNotificationList,
  NotificationStatus,
  NotificationType,
} from "~/types/api";
import { formatDate } from "~/utils/format";
import { dateBr, daysToEndLabel } from "~/utils/contracts";
import {
  ALERT_ACTION_LABEL,
  NOTIFICATION_STATUS_LABEL,
  NOTIFICATION_TYPE_LABEL,
  PROVIDER_LABEL,
  alertActionTone,
  milestoneLabel,
  notificationStatusTone,
} from "~/utils/notifications";

const api = useApi();
const { load: loadAttention } = useAttention();

// ---------------------------------------------------------------- histórico
const items = ref<ContractNotification[]>([]);
const loading = ref(false);
const error = ref("");
const page = ref(1);
const totalPages = ref(1);
const total = ref(0);
const filters = reactive<{ status: NotificationStatus | ""; tipo: NotificationType | ""; destinatario: string; de: string; ate: string }>({
  status: "",
  tipo: "",
  destinatario: "",
  de: "",
  ate: "",
});
const resending = ref<string | null>(null);

// Filtros/paginação trocados rápido: a lista mostrada é sempre a da última consulta.
const listRequest = createLatestRequest();

async function load(): Promise<void> {
  const request = listRequest.begin();
  loading.value = true;
  error.value = "";
  try {
    const response = await api.request<ContractNotificationList>("/notificacoes-contratos", {
      method: "GET",
      query: {
        page: page.value,
        pageSize: 25,
        status: filters.status || undefined,
        tipo: filters.tipo || undefined,
        destinatario: filters.destinatario.trim() || undefined,
        de: filters.de || undefined,
        ate: filters.ate || undefined,
      },
      signal: request.signal,
    });
    if (!request.isCurrent()) return;
    items.value = response.items;
    totalPages.value = response.pagination?.totalPages ?? 1;
    total.value = response.pagination?.total ?? response.items.length;
  } catch (cause) {
    if (!request.isCurrent()) return;
    error.value = cause instanceof Error ? cause.message : "Não foi possível carregar os envios.";
  } finally {
    if (request.isCurrent()) loading.value = false;
  }
}

function applyFilters(): void {
  if (page.value === 1) void load();
  else page.value = 1;
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

watch(page, load);
watch(() => [filters.status, filters.tipo, filters.de, filters.ate], applyFilters);
onMounted(load);

// ---------------------------------------------------------------- prévia / execução
const previewDate = ref("");
const run = ref<AlertRun | null>(null);
const running = ref<"preview" | "execute" | null>(null);
const runError = ref("");
const emailPreview = ref<{ contractId: string; type: AlertItem["type"]; noticeDays: number; day: string | null } | null>(null);

function openEmail(item: AlertItem): void {
  emailPreview.value = { contractId: item.contractId, type: item.type, noticeDays: item.noticeDays, day: run.value?.today ?? null };
}

async function preview(): Promise<void> {
  running.value = "preview";
  runError.value = "";
  try {
    run.value = await api.get<AlertRun>("/alertas/previa", previewDate.value ? { data: previewDate.value } : undefined);
  } catch (cause) {
    runError.value = cause instanceof Error ? cause.message : "Não foi possível gerar a prévia.";
  } finally {
    running.value = null;
  }
}

async function execute(): Promise<void> {
  const ok = window.confirm(
    "Executar agora os alertas de hoje? E-mails elegíveis serão enviados de verdade (alertas já enviados não se repetem).",
  );
  if (!ok) return;
  running.value = "execute";
  runError.value = "";
  try {
    run.value = await api.post<AlertRun>("/alertas/executar?dry_run=false");
    await Promise.all([load(), loadAttention()]);
  } catch (cause) {
    runError.value = cause instanceof Error ? cause.message : "Não foi possível executar os alertas.";
  } finally {
    running.value = null;
  }
}

const summary = computed(() =>
  run.value
    ? [
        { label: "Analisados", value: run.value.contractsAnalyzed },
        { label: "Elegíveis", value: run.value.eligible },
        { label: run.value.dryRun ? "Seriam enviados" : "Enviados", value: run.value.sent },
        { label: "Já notificados", value: run.value.duplicates },
        { label: "Reenvios", value: run.value.retried },
        { label: "Falhas", value: run.value.failed },
        { label: "Ignorados", value: run.value.skipped },
      ]
    : [],
);
</script>

<template>
  <div class="notification-admin">
    <section class="surface admin-card">
      <header class="admin-card-head">
        <div>
          <h2>Execução dos alertas</h2>
          <p>O job diário roda sozinho. Use a prévia para conferir o que seria enviado sem nenhum efeito colateral.</p>
        </div>
        <div class="admin-card-actions">
          <label class="inline-field"><span>Simular data</span><input v-model="previewDate" type="date" /></label>
          <button type="button" class="btn" :disabled="running !== null" @click="preview">
            <Eye class="size-4" />{{ running === "preview" ? "Gerando…" : "Ver prévia" }}
          </button>
          <button type="button" class="btn primary" :disabled="running !== null" @click="execute">
            <Play class="size-4" />{{ running === "execute" ? "Executando…" : "Executar agora" }}
          </button>
        </div>
      </header>
      <p v-if="runError" class="form-error">{{ runError }}</p>
      <template v-if="run">
        <p class="run-caption">
          {{ run.dryRun ? "Prévia (nada foi enviado nem gravado)" : "Execução real" }} · dia {{ dateBr(run.today) }}
          <template v-if="run.provider"> · {{ PROVIDER_LABEL[run.provider] ?? run.provider }}</template>
        </p>
        <div class="run-summary">
          <div v-for="item in summary" :key="item.label"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></div>
        </div>
        <div v-if="run.items.length" class="table-scroll">
          <table class="admin-table">
            <thead><tr><th>Resultado</th><th>Contrato</th><th>Tipo</th><th>Destinatário</th><th>Vencimento</th><th>Motivo</th><th /></tr></thead>
            <tbody>
              <tr v-for="item in run.items" :key="`${item.contractId}-${item.type}-${item.retry}-${item.referenceDate}`">
                <td><span class="pill" :class="alertActionTone(item.action)">{{ ALERT_ACTION_LABEL[item.action] }}</span></td>
                <td><strong>{{ item.contractNumber }}</strong><small>{{ item.supplier }}</small></td>
                <td>{{ milestoneLabel(item.type, item.noticeDays) }}<small v-if="item.retry">reenvio</small></td>
                <td>{{ item.recipient || "—" }}</td>
                <td>{{ dateBr(item.contractEndDate) }}<small>{{ daysToEndLabel(item.daysToEnd) }}</small></td>
                <td><small>{{ item.error || item.reason }}</small></td>
                <td><button type="button" class="btn small" @click="openEmail(item)"><Mail class="size-3.5" />Visualizar e-mail</button></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="history-empty">Nenhum alerta elegível para este dia.</p>
      </template>
    </section>

    <section class="surface admin-card">
      <header class="admin-card-head">
        <div><h2>Histórico de envios</h2><p>{{ total }} registros</p></div>
        <button type="button" class="drawer-icon-button" title="Atualizar" :disabled="loading" @click="load"><RefreshCw class="size-4" /></button>
      </header>
      <div class="admin-filters">
        <label><span>Status</span>
          <select v-model="filters.status"><option value="">Todos</option><option v-for="(label, key) in NOTIFICATION_STATUS_LABEL" :key="key" :value="key">{{ label }}</option></select>
        </label>
        <label><span>Tipo</span>
          <select v-model="filters.tipo"><option value="">Todos</option><option v-for="(label, key) in NOTIFICATION_TYPE_LABEL" :key="key" :value="key">{{ label }}</option></select>
        </label>
        <label><span>Destinatário</span><input v-model="filters.destinatario" type="search" placeholder="e-mail" @keyup.enter="applyFilters" @search="applyFilters" /></label>
        <label><span>De</span><input v-model="filters.de" type="date" /></label>
        <label><span>Até</span><input v-model="filters.ate" type="date" /></label>
      </div>
      <p v-if="error" class="form-error">{{ error }}</p>
      <div class="table-scroll">
        <table class="admin-table">
          <thead><tr><th>Status</th><th>Contrato</th><th>Tipo</th><th>Destinatário</th><th>Vigência</th><th>Tentativas</th><th>Última atividade</th><th /></tr></thead>
          <tbody>
            <tr v-if="!loading && !items.length"><td colspan="8" class="history-empty">Nenhum envio encontrado.</td></tr>
            <tr v-for="item in items" :key="item.id">
              <td><span class="pill" :class="notificationStatusTone(item.status)">{{ NOTIFICATION_STATUS_LABEL[item.status] }}</span></td>
              <td>
                <NuxtLink :to="{ path: '/dashboard/contratos', query: { contrato: item.contractId } }"><strong>{{ item.contractNumber }}</strong></NuxtLink>
                <small>{{ item.supplier }}</small>
              </td>
              <td>{{ milestoneLabel(item.type, item.noticeDays) }}</td>
              <td>{{ item.recipient || "—" }}<small v-if="item.provider">{{ PROVIDER_LABEL[item.provider] ?? item.provider }}</small></td>
              <td>{{ dateBr(item.contractEndDate) }}</td>
              <td>{{ item.attempts }}</td>
              <td>{{ formatDate(item.sentAt || item.lastAttemptAt || item.createdAt, true) }}<small v-if="item.error" class="history-error" :title="item.error">{{ item.error }}</small></td>
              <td>
                <button v-if="item.canRetry" type="button" class="btn small" :disabled="resending === item.id" @click="resend(item)">
                  <RotateCw class="size-3.5" />{{ resending === item.id ? "Reenviando…" : "Reenviar" }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="totalPages > 1" class="contracts-pagination">
        <span>Página {{ page }} de {{ totalPages }}</span>
        <div><button :disabled="page <= 1" @click="page--">Anterior</button><button :disabled="page >= totalPages" @click="page++">Próxima</button></div>
      </div>
    </section>
    <EmailPreviewModal
      :open="Boolean(emailPreview)"
      :contract-id="emailPreview?.contractId ?? null"
      :type="emailPreview?.type"
      :notice-days="emailPreview?.noticeDays"
      :day="emailPreview?.day"
      @close="emailPreview = null"
    />
  </div>
</template>
