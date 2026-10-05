<script setup lang="ts">
import { Bell, Mail, RefreshCw, X } from "lucide-vue-next";
import { formatDate } from "~/utils/format";
import { NOTIFICATION_STATUS_LABEL, NOTIFICATION_TYPE_LABEL } from "~/utils/notifications";

/** Painel do sino. A lista e as mensagens vêm do backend (`GET /alertas/contratos`). */
const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: []; select: [contractId: string] }>();
const { data, loading, error, load } = useAttention();

watch(
  () => props.open,
  (open) => {
    if (open) void load();
  },
);
</script>
<template>
  <Teleport to="body">
    <div v-if="open" class="notification-backdrop" @click.self="emit('close')">
      <aside class="notification-panel">
        <header>
          <div>
            <Bell class="size-5" />
            <div>
              <h2>Notificações</h2>
              <p v-if="data">
                {{ data.overdue }} vencidos · {{ data.attention }} em atenção
                <template v-if="data.withoutDate"> · {{ data.withoutDate }} sem data</template>
              </p>
            </div>
          </div>
          <div class="drawer-actions">
            <button type="button" class="drawer-icon-button" title="Atualizar" :disabled="loading" @click="load"><RefreshCw class="size-4" /></button>
            <button class="drawer-close" aria-label="Fechar" @click="emit('close')"><X class="size-5" /></button>
          </div>
        </header>
        <p v-if="error" class="notification-empty error">{{ error }}</p>
        <div v-else class="notification-list">
          <button v-for="item in data?.items ?? []" :key="item.contractId" type="button" @click="emit('select', item.contractId)">
            <ContractStatusBadge :alert="item.alert" class="notification-status" />
            <strong>{{ item.supplier }}</strong>
            <span class="notification-summary">Contrato {{ item.contractNumber }} · {{ item.message }}</span>
            <span v-if="item.lastNotification" class="notification-mail">
              <Mail class="size-3" />
              {{ NOTIFICATION_TYPE_LABEL[item.lastNotification.type] }} ·
              {{ NOTIFICATION_STATUS_LABEL[item.lastNotification.status] }}
              {{ formatDate(item.lastNotification.sentAt || item.lastNotification.createdAt, true) }}
            </span>
            <span v-else-if="!item.notify" class="notification-mail muted">Alertas por e-mail desativados</span>
          </button>
          <p v-if="loading && !data" class="notification-empty">Carregando…</p>
          <p v-else-if="data && !data.items.length" class="notification-empty">Nenhum contrato exige atenção agora.</p>
        </div>
      </aside>
    </div>
  </Teleport>
</template>
