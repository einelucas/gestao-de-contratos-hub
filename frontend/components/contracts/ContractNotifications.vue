<script setup lang="ts">
import { AtSign, Bell, BellRing, CalendarClock, Mail, RefreshCw, X } from "lucide-vue-next";
import type { InternalNotification } from "~/types/api";
import { formatDate } from "~/utils/format";
import { NOTIFICATION_STATUS_LABEL, NOTIFICATION_TYPE_LABEL } from "~/utils/notifications";

/** Central do aplicativo: menções/lembretes pessoais + prazos pré-existentes. */
const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: []; select: [contractId: string]; selectAudit: [contractId: string] }>();
const { data: deadlines, loading: deadlinesLoading, error: deadlinesError, load: loadDeadlines } = useAttention();
const { data: inbox, loading: inboxLoading, error: inboxError, unreadCount, load: loadInbox, markRead } = useInternalNotifications();
const tab = ref<"personal" | "deadlines">("personal");
const openingId = ref<string | null>(null);
const actionError = ref("");

async function refresh(): Promise<void> {
  await Promise.all([loadInbox(), loadDeadlines()]);
}

watch(() => props.open, (open) => {
  if (open) {
    tab.value = "personal";
    actionError.value = "";
    void refresh();
  }
});

function itemDate(item: InternalNotification): string {
  return new Date(item.scheduledAt).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

async function openNotification(item: InternalNotification): Promise<void> {
  if (openingId.value) return;
  openingId.value = item.id;
  actionError.value = "";
  try {
    await markRead(item);
    emit("selectAudit", item.contractId);
  } catch (cause) {
    actionError.value = cause instanceof Error ? cause.message : "Não foi possível abrir a notificação.";
  } finally {
    openingId.value = null;
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="props.open" class="notification-backdrop" @click.self="emit('close')">
      <aside class="notification-panel" role="dialog" aria-modal="true" aria-label="Notificações da Gestão de Contratos">
        <header>
          <div>
            <Bell class="size-5" />
            <div>
              <h2>Notificações do aplicativo</h2>
              <p>Menções, lembretes e prazos de contratos</p>
            </div>
          </div>
          <div class="drawer-actions">
            <button type="button" class="drawer-icon-button" title="Atualizar" :disabled="inboxLoading || deadlinesLoading" @click="refresh">
              <RefreshCw class="size-4" :class="{ 'animate-spin': inboxLoading || deadlinesLoading }" />
            </button>
            <button type="button" class="drawer-close" aria-label="Fechar" @click="emit('close')"><X class="size-5" /></button>
          </div>
        </header>

        <div class="flex gap-2 border-b border-slate-200 p-3" role="tablist" aria-label="Tipos de notificações">
          <button type="button" class="flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition-colors"
            :class="tab === 'personal' ? 'bg-[#304f7e] text-white' : 'bg-slate-100 text-slate-600'"
            :aria-selected="tab === 'personal'" role="tab" @click="tab = 'personal'">
            <AtSign class="size-4" /> Para mim
            <span v-if="unreadCount" class="rounded-full bg-white/20 px-1.5 text-xs">{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
          </button>
          <button type="button" class="flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold transition-colors"
            :class="tab === 'deadlines' ? 'bg-[#304f7e] text-white' : 'bg-slate-100 text-slate-600'"
            :aria-selected="tab === 'deadlines'" role="tab" @click="tab = 'deadlines'">
            <CalendarClock class="size-4" /> Prazos
            <span v-if="deadlines" class="rounded-full bg-white/20 px-1.5 text-xs">{{ deadlines.overdue + deadlines.attention }}</span>
          </button>
        </div>

        <p v-if="actionError" class="mx-4 mt-3 text-xs text-red-700" role="alert">{{ actionError }}</p>

        <div v-if="tab === 'personal'" class="notification-list">
          <p v-if="inboxError" class="notification-empty error">{{ inboxError }}</p>
          <template v-else>
            <button v-for="item in inbox?.items ?? []" :key="item.id" type="button" class="flex w-full flex-col items-start gap-1 text-left"
              :class="{ 'bg-blue-50/70': !item.readAt }" :disabled="openingId !== null"
              @click="openNotification(item)">
              <span class="flex w-full items-center justify-between gap-2">
                <span class="inline-flex items-center gap-1 text-xs font-semibold text-[#304f7e]">
                  <AtSign v-if="item.kind === 'MENTION'" class="size-3.5" />
                  <BellRing v-else class="size-3.5" />
                  {{ item.kind === 'MENTION' ? 'Menção na Auditoria' : 'Lembrete programado' }}
                </span>
                <span v-if="!item.readAt" class="size-2 shrink-0 rounded-full bg-blue-600" aria-label="Não lida" />
              </span>
              <strong>{{ item.actorName && item.kind === "MENTION" ? item.actorName + " mencionou você" : item.supplier }}</strong>
              <span class="notification-summary">Contrato {{ item.contractNumber }} · {{ item.message || "Você foi mencionado em uma atualização." }}</span>
              <small class="text-slate-500">{{ itemDate(item) }}</small>
            </button>
            <p v-if="inboxLoading && !inbox" class="notification-empty">Carregando notificações…</p>
            <p v-else-if="inbox && !inbox.items.length" class="notification-empty">Sem menções ou lembretes para você no momento.</p>
          </template>
        </div>

        <div v-else class="notification-list">
          <p v-if="deadlinesError" class="notification-empty error">{{ deadlinesError }}</p>
          <template v-else>
            <button v-for="item in deadlines?.items ?? []" :key="item.contractId" type="button" @click="emit('select', item.contractId)">
              <ContractStatusBadge :alert="item.alert" class="notification-status" />
              <strong>{{ item.supplier }}</strong>
              <span class="notification-summary">Contrato {{ item.contractNumber }} · {{ item.message }}</span>
              <span v-if="item.lastNotification" class="notification-mail">
                <Mail class="size-3" /> {{ NOTIFICATION_TYPE_LABEL[item.lastNotification.type] }} ·
                {{ NOTIFICATION_STATUS_LABEL[item.lastNotification.status] }}
                {{ formatDate(item.lastNotification.sentAt || item.lastNotification.createdAt, true) }}
              </span>
              <span v-else-if="!item.notify" class="notification-mail muted">Alertas por e-mail desativados</span>
            </button>
            <p v-if="deadlinesLoading && !deadlines" class="notification-empty">Carregando…</p>
            <p v-else-if="deadlines && !deadlines.items.length" class="notification-empty">Nenhum contrato exige atenção agora.</p>
          </template>
        </div>
      </aside>
    </div>
  </Teleport>
</template>
