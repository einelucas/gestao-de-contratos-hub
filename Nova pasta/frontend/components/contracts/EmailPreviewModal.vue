<script setup lang="ts">
import { createLatestRequest } from "~/utils/latestRequest";
import { Info, Mail } from "lucide-vue-next";
import type { EmailPreview, NotificationType } from "~/types/api";

/** Mostra o e-mail exatamente como o builder do envio real o monta. Nada é enviado nem gravado. */
const props = defineProps<{
  open: boolean;
  contractId: string | null;
  type?: NotificationType;
  /** Marco de antecedência (45/20/1) quando `type` é ANTECEDENCIA. */
  noticeDays?: number;
  /** Dia simulado da prévia (AAAA-MM-DD), para os dias exibidos baterem com ela. */
  day?: string | null;
}>();
const emit = defineEmits<{ close: [] }>();

interface Milestone {
  key: string;
  label: string;
  type: NotificationType;
  days?: number;
}
const MILESTONES: Milestone[] = [
  { key: "A45", label: "45 dias", type: "ANTECEDENCIA", days: 45 },
  { key: "A20", label: "20 dias", type: "ANTECEDENCIA", days: 20 },
  { key: "A1", label: "1 dia", type: "ANTECEDENCIA", days: 1 },
  { key: "VENCIMENTO", label: "Vencimento", type: "VENCIMENTO" },
  { key: "VENCIDO", label: "Vencido", type: "VENCIDO" },
];

const api = useApi();
const selected = ref("A45");
const preview = ref<EmailPreview | null>(null);
const loading = ref(false);
const error = ref("");
const milestone = computed(
  () =>
    MILESTONES.find((item) => item.key === selected.value) ?? MILESTONES[0]!,
);
const illustrativeDays = computed(() =>
  Boolean(
    preview.value &&
    !props.day &&
    preview.value.actualDaysToEnd !== null &&
    preview.value.actualDaysToEnd !== preview.value.daysToEnd,
  ),
);

function describeDays(days: number): string {
  if (days === 0) return "vence hoje";
  return days > 0 ? `vence em ${days} dias` : `venceu há ${-days} dias`;
}

function initialKey(): string {
  if (props.type === "ANTECEDENCIA") return `A${props.noticeDays ?? 45}`;
  return props.type ?? "A45";
}

// Abrir o modal e trocar o marco disparam cargas seguidas: só a última pode virar o preview.
const previewRequest = createLatestRequest();

async function load(): Promise<void> {
  if (!props.contractId) return;
  const request = previewRequest.begin();
  loading.value = true;
  error.value = "";
  try {
    const response = await api.request<EmailPreview>("/alertas/modelo", {
      method: "GET",
      query: {
        contrato: props.contractId,
        tipo: milestone.value.type,
        dias: milestone.value.days,
        data: props.day || undefined,
      },
      signal: request.signal,
    });
    if (!request.isCurrent()) return;
    preview.value = response;
  } catch (cause) {
    if (!request.isCurrent()) return;
    preview.value = null;
    error.value =
      cause instanceof Error
        ? cause.message
        : "Não foi possível montar o modelo do e-mail.";
  } finally {
    if (request.isCurrent()) loading.value = false;
  }
}

watch(
  () => [props.open, props.contractId, props.type, props.noticeDays] as const,
  ([open]) => {
    if (!open) return;
    selected.value = MILESTONES.some((item) => item.key === initialKey())
      ? initialKey()
      : "A45";
    void load();
  },
  { immediate: true },
);
watch(selected, () => {
  if (props.open) void load();
});
</script>

<template>
  <AppModal
    :open="open"
    title="Modelo do e-mail de alerta"
    @close="emit('close')"
  >
    <div class="email-preview">
      <div class="email-preview-toolbar">
        <div class="segmented" role="tablist" aria-label="Marco do alerta">
          <button
            v-for="item in MILESTONES"
            :key="item.key"
            type="button"
            role="tab"
            :aria-selected="selected === item.key"
            :class="{ active: selected === item.key }"
            @click="selected = item.key"
          >
            {{ item.label }}
          </button>
        </div>
      </div>

      <p v-if="error" class="form-error">{{ error }}</p>
      <p v-else-if="loading && !preview" class="history-empty">
        Montando o e-mail…
      </p>

      <template v-if="preview">
        <dl class="email-headers">
          <div>
            <dt>Equipe</dt>
            <dd>{{ preview.teamName || "nenhuma equipe de notificação" }}</dd>
          </div>
          <div>
            <dt>Destinatários</dt>
            <dd>
              <template v-if="preview.recipients.length">
                {{ preview.recipients.length }} —
                {{ preview.recipients.join(", ") }}
                <small class="muted">(cada um recebe o próprio e-mail)</small>
              </template>
              <template v-else>nenhum destinatário ativo</template>
            </dd>
          </div>
          <div>
            <dt>Assunto</dt>
            <dd>{{ preview.subject }}</dd>
          </div>
        </dl>
        <p
          v-if="
            !preview.notify ||
            !preview.recipients.length ||
            preview.illustrativeDate ||
            illustrativeDays
          "
          class="form-hint"
        >
          <Info class="size-3.5" />
          <template v-if="!preview.notify"
            >Os alertas deste contrato estão desativados — este é só o
            modelo.</template
          >
          <template v-if="!preview.recipients.length">
            {{ preview.recipientsProblem || "Sem destinatários" }}: nenhum
            e-mail seria enviado.</template
          >
          <template v-if="preview.illustrativeDate">
            O contrato não tem fim de vigência; a data exibida é
            ilustrativa.</template
          >
          <template v-if="illustrativeDays">
            Simulação do marco escolhido; hoje o contrato
            {{ describeDays(preview.actualDaysToEnd ?? 0) }}.</template
          >
        </p>
        <iframe
          class="email-frame"
          :class="{ loading }"
          title="Pré-visualização do e-mail"
          sandbox=""
          :srcdoc="preview.html"
        />
        <p class="form-hint">
          <Mail class="size-3.5" />Visualização apenas — nenhum e-mail é enviado
          e nada é gravado.
        </p>
      </template>
    </div>
  </AppModal>
</template>
