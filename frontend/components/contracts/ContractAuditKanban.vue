<script setup lang="ts">

import {

  Building2,

  CalendarDays,



  RefreshCw,

  Search,

  WalletCards,

} from "lucide-vue-next";

import type {
  AuditActivity,
  AuditAttachment,
  AuditBoard,
  AuditStage,
  AuditUpdate,
  AuditUser,
  AuditWorkspace,
  Contract,
} from "~/types/api";

import { dateBr, daysToEndLabel, money } from "~/utils/contracts";

type UiAuditStage = AuditStage | "NAO_INICIADO";

const STAGES: Array<{ key: UiAuditStage; label: string; color: string }> = [

  { key: "NAO_INICIADO", label: "Não iniciado", color: "#94A3B8" },

  { key: "AGUARDANDO_ANALISE", label: "Aguardando Análise", color: "#D45B73" },

  { key: "CHAMADO_ELES", label: "Chamado aberto no Elos", color: "#3B82F6" },

  { key: "ANALISE_INTERNA_INPASA", label: "Análise Interna – INPASA", color: "#A855F7" },

  { key: "FORNECEDOR_CONTATADO", label: "Aguardando fornecedor", color: "#C58A1F" },

  { key: "EM_TRATATIVA", label: "Em Tratativa", color: "#0F9F8F" },

  { key: "EM_FINALIZACAO", label: "Em Finalização – Resolvido", color: "#16A34A" },

  { key: "FINALIZADO", label: "Finalizado", color: "#3F6212" },

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

const overStage = ref<UiAuditStage | null>(null);

const selectedContract = ref<Contract | null>(null);

const INITIAL_STAGE_LIMIT = 10;
const STAGE_LIMIT_STEP = 10;
const stageVisibleLimits = ref<Record<string, number>>({});
const auditSortMode = ref<
  "PRIORIDADE" | "VENCIMENTO" | "FORNECEDOR" | "TEMPO"
>("PRIORIDADE");
const hideEmptyStages = ref(false);
const stageTimingHistory = ref<Record<string, StageTimingEntry[]>>({});
const currentStageTiming = ref<Record<string, CurrentStageTiming>>({});
const stageClock = ref(Date.now());
let stageClockTimer: ReturnType<typeof setInterval> | undefined;



type StageTimingEntry = {
  id: string;
  contractId: string;
  stage: AuditStage;
  startedAt: string;
  endedAt: string;
  durationMs: number;
};

type CurrentStageTiming = {
  stage: AuditStage;
  startedAt: string;
};

type AuditTab = "updates" | "files" | "activity";

const activeAuditTab = ref<AuditTab>("updates");
const newUpdateText = ref("");
const auditUpdates = ref<AuditUpdate[]>([]);
type PendingAttachment = AuditAttachment & { file: File };
const pendingAttachments = ref<PendingAttachment[]>([]);
const updateTextarea = ref<HTMLTextAreaElement | null>(null);
const attachmentInput = ref<HTMLInputElement | null>(null);
const editingUpdateId = ref<string | null>(null);
const editingUpdateText = ref("");

const MAX_ATTACHMENT_BYTES = 5_000_000;
const users = ref<AuditUser[]>([]);
const currentUserId = ref("");
const auditActivity = ref<AuditActivity[]>([]);

const compactMode = ref(false);
const mentionsOnly = ref(false);


const mentionOpen = ref(false);
const mentionSearch = ref("");

const activeUsers = computed(() => users.value.filter((user) => user.active));

const filteredMentionUsers = computed(() => {
  const query = mentionSearch.value.trim().toLocaleLowerCase("pt-BR");

  return activeUsers.value.filter(
    (user) =>
      !query ||
      user.name.toLocaleLowerCase("pt-BR").includes(query) ||
      user.email.toLocaleLowerCase("pt-BR").includes(query),
  );
});

function userName(userId: string | null | undefined): string {
  if (!userId) return "Não definido";
  return users.value.find((user) => user.id === userId)?.name ?? "Usuário";
}

const selectedContractActivity = computed(() => {
  if (!selectedContract.value) return [];

  return auditActivity.value
    .filter((activity) => activity.contractId === selectedContract.value?.id)
    .sort(
      (a, b) =>
        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    );
});

const myMentionCount = computed(
  () =>
    auditUpdates.value.filter((update) =>
      update.mentionedUserIds.includes(currentUserId.value),
    ).length,
);

const selectedContractUpdates = computed(() => {
  if (!selectedContract.value) return [];

  return auditUpdates.value
    .filter((update) => update.contractId === selectedContract.value?.id)
    .sort(
      (a, b) =>
        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
    );
});

const selectedContractFiles = computed(() => {
  if (!selectedContract.value) return [];

  return selectedContractUpdates.value.flatMap((update) =>
    update.attachments.map((attachment) => ({
      ...attachment,
      updateId: update.id,
      author: update.author,
      createdAt: update.createdAt,
    })),
  );
});

function detectMentionedUsers(textValue: string): string[] {
  return activeUsers.value
    .filter((user) =>
      textValue.toLocaleLowerCase("pt-BR").includes(
        `@${user.name}`.toLocaleLowerCase("pt-BR"),
      ),
    )
    .map((user) => user.id);
}

async function publishUpdate(): Promise<void> {
  const contract = selectedContract.value;
  const textValue = newUpdateText.value.trim();

  if (!contract || (!textValue && pendingAttachments.value.length === 0)) return;
  const form = new FormData();
  form.append("text", textValue);
  form.append("mentionedUserIds", JSON.stringify(detectMentionedUsers(textValue)));
  for (const attachment of pendingAttachments.value) form.append("files", attachment.file);

  try {
    const created = await api.request<AuditUpdate>(
      `/contratos/${contract.id}/auditoria/atualizacoes`,
      { method: "POST", body: form },
    );
    auditUpdates.value.unshift(created);
    newUpdateText.value = "";
    pendingAttachments.value = [];
    mentionOpen.value = false;
    mentionSearch.value = "";
    cancelEditUpdate();
    await loadWorkspace(contract.id);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível publicar a atualização.";
  }
}


function insertMention(): void {
  mentionOpen.value = !mentionOpen.value;
  mentionSearch.value = "";

  nextTick(() => {
    updateTextarea.value?.focus();
  });
}

function selectMention(user: AuditUser): void {
  const current = newUpdateText.value;
  const needsSpace = current.length > 0 && !current.endsWith(" ");
  newUpdateText.value = `${current}${needsSpace ? " " : ""}@${user.name} `;

  mentionOpen.value = false;
  mentionSearch.value = "";

  nextTick(() => updateTextarea.value?.focus());
}

function openAttachmentPicker(): void {
  attachmentInput.value?.click();
}

function isImageAttachment(_attachment: AuditAttachment): boolean {
  // A prévia exige baixar o arquivo autenticado; o clique abre qualquer tipo.
  return false;
}

async function openAttachment(attachment: AuditAttachment): Promise<void> {
  try {
    const blob = await api.request<Blob>(attachment.url, { method: "GET", responseType: "blob" });
    const objectUrl = URL.createObjectURL(blob);
    window.open(objectUrl, "_blank", "noopener,noreferrer");
    setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível abrir o anexo.";
  }
}

async function onAttachmentSelected(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);

  for (const file of files) {
    if (file.size > MAX_ATTACHMENT_BYTES) {
      error.value =
        `O arquivo ${file.name} é maior que 5 MB.`;
      continue;
    }

    pendingAttachments.value.push({
      id: crypto.randomUUID(),
      name: file.name,
      size: file.size,
      type: file.type || "application/octet-stream",
      url: "",
      file,
    });
  }

  input.value = "";
}


function removePendingAttachment(id: string): void {
  pendingAttachments.value = pendingAttachments.value.filter(
    (item) => item.id !== id,
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function startEditUpdate(update: AuditUpdate): void {
  editingUpdateId.value = update.id;
  editingUpdateText.value = update.text;
}

function cancelEditUpdate(): void {
  editingUpdateId.value = null;
  editingUpdateText.value = "";
}

async function saveEditUpdate(updateId: string): Promise<void> {
  const textValue = editingUpdateText.value.trim();
  const update = auditUpdates.value.find((item) => item.id === updateId);

  if (!update || !textValue) return;

  try {
    const edited = await api.patch<AuditUpdate>(
      `/contratos/auditoria/atualizacoes/${updateId}`,
      { text: textValue, mentionedUserIds: detectMentionedUsers(textValue) },
    );
    Object.assign(update, edited);
    cancelEditUpdate();
    await loadWorkspace(update.contractId);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível editar a atualização.";
  }
}

async function deleteUpdate(updateId: string): Promise<void> {
  const confirmed = window.confirm("Deseja excluir este comentário?");

  if (!confirmed) return;

  const update = auditUpdates.value.find((item) => item.id === updateId);

  if (!update) return;
  try {
    await api.delete(`/contratos/auditoria/atualizacoes/${updateId}`);
    auditUpdates.value = auditUpdates.value.filter((item) => item.id !== updateId);
    if (editingUpdateId.value === updateId) cancelEditUpdate();
    await loadWorkspace(update.contractId);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível excluir a atualização.";
  }
}

function formatAuditDate(date: Date | string): string {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(typeof date === "string" ? new Date(date) : date);
}


function currentStageElapsedMs(contractId: string): number {
  const current = currentStageTiming.value[contractId];
  if (!current) return 0;

  return Math.max(
    0,
    stageClock.value - new Date(current.startedAt).getTime(),
  );
}

function bottleneckLevel(contractId: string): "critical" | "warning" | "normal" {
  const days = currentStageElapsedMs(contractId) / 86_400_000;

  if (days >= 7) return "critical";
  if (days >= 3) return "warning";
  return "normal";
}

function currentStageElapsedLabel(contractId: string): string {
  return formatStageDuration(currentStageElapsedMs(contractId));
}

function handleAuditKeydown(event: KeyboardEvent): void {
  if (!selectedContract.value) return;

  const target = event.target as HTMLElement | null;
  const isTyping =
    target?.tagName === "INPUT" ||
    target?.tagName === "TEXTAREA" ||
    target?.tagName === "SELECT";

  if (event.key === "Escape") {
    closeContract();
    return;
  }

  if (isTyping) return;

  if (event.key === "ArrowLeft" && canMoveSelectedBack.value) {
    event.preventDefault();
    moveSelectedBack();
  }

  if (event.key === "ArrowRight" && canMoveSelectedForward.value) {
    event.preventDefault();
    moveSelectedForward();
  }
}

function restoreStageTiming(): void {
  stageTimingHistory.value = {};
  currentStageTiming.value = {};
}

function saveStageTiming(): void {
  // A fonte de verdade é auditStageEnteredAt e o histórico do backend.
}

function ensureStageTiming(contracts: Contract[]): void {
  let changed = false;
  for (const contract of contracts) {
    if (!contract.auditStage) continue;

    const current = currentStageTiming.value[contract.id];
    const startedAt = contract.auditStageEnteredAt ?? contract.updatedAt;

    if (!current || current.stage !== contract.auditStage || current.startedAt !== startedAt) {
      currentStageTiming.value[contract.id] = {
        stage: contract.auditStage,
        startedAt,
      };
      changed = true;
    }
  }

  if (changed) saveStageTiming();
}

function registerStageTransition(
  contractId: string,
  fromStage: AuditStage | null | undefined,
  toStage: AuditStage,
): void {
  const now = new Date();
  const current = currentStageTiming.value[contractId];

  if (fromStage && current?.stage === fromStage) {
    const startedAt = new Date(current.startedAt);
    const durationMs = Math.max(0, now.getTime() - startedAt.getTime());

    const history = stageTimingHistory.value[contractId] ?? [];
    history.push({
      id: crypto.randomUUID(),
      contractId,
      stage: fromStage,
      startedAt: current.startedAt,
      endedAt: now.toISOString(),
      durationMs,
    });
    stageTimingHistory.value[contractId] = history;
  }

  currentStageTiming.value[contractId] = {
    stage: toStage,
    startedAt: now.toISOString(),
  };

  stageClock.value = now.getTime();
  saveStageTiming();
}

function formatStageDuration(durationMs: number): string {
  const totalMinutes = Math.floor(durationMs / 60000);

  if (totalMinutes < 1) return "menos de 1 min";

  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;

  if (days > 0) {
    return `${days}d ${hours}h`;
  }

  if (hours > 0) {
    return `${hours}h ${minutes}min`;
  }

  return `${minutes}min`;
}

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";

  try {
    const auditResponse = await api.get<AuditBoard>("/contratos/auditoria");
    items.value = auditResponse.items;
    units.value = auditResponse.units;
    users.value = auditResponse.users;
    currentUserId.value = auditResponse.currentUserId;

    ensureStageTiming(items.value);

    if (
      unit.value !== "Todas" &&
      !units.value.includes(unit.value)
    ) {
      unit.value = "Todas";
    }
  } catch (cause) {
    error.value =
      cause instanceof Error
        ? cause.message
        : "Não foi possível carregar os contratos da Auditoria.";
  } finally {
    loading.value = false;
  }
}

async function loadWorkspace(contractId: string): Promise<void> {
  const workspace = await api.get<AuditWorkspace>(
    `/contratos/${contractId}/auditoria/workspace`,
  );
  auditUpdates.value = [
    ...auditUpdates.value.filter((item) => item.contractId !== contractId),
    ...workspace.updates,
  ];
  auditActivity.value = [
    ...auditActivity.value.filter((item) => item.contractId !== contractId),
    ...workspace.activity,
  ];

  const transitions = workspace.activity
    .filter((item) => item.type === "STAGE" && item.toStage)
    .sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime());
  stageTimingHistory.value[contractId] = transitions.slice(0, -1).map((item, index) => {
    const next = transitions[index + 1]!;
    const startedAt = item.createdAt;
    const endedAt = next.createdAt;
    return {
      id: item.id,
      contractId,
      stage: item.toStage!,
      startedAt,
      endedAt,
      durationMs: Math.max(0, new Date(endedAt).getTime() - new Date(startedAt).getTime()),
    };
  });
}

onMounted(() => {
  restoreStageTiming();
  void load();

  window.addEventListener("keydown", handleAuditKeydown);

  stageClockTimer = setInterval(() => {
    stageClock.value = Date.now();
  }, 30000);
});

onBeforeUnmount(() => {
  clearInterval(stageClockTimer);
  window.removeEventListener("keydown", handleAuditKeydown);
});

const filtered = computed(() => {
  const query = search.value.trim().toLocaleLowerCase("pt-BR");

  return items.value.filter((item) => {
    const comments = auditUpdates.value
      .filter((update) => update.contractId === item.id)
      .map((update) => update.text)
      .join(" ")
      .toLocaleLowerCase("pt-BR");

    const matchesSearch =
      !query ||
      item.contractNumber.toLocaleLowerCase("pt-BR").includes(query) ||
      item.supplier.toLocaleLowerCase("pt-BR").includes(query) ||
      (item.unit ?? "").toLocaleLowerCase("pt-BR").includes(query) ||
      (item.sectorName ?? "").toLocaleLowerCase("pt-BR").includes(query) ||
      comments.includes(query);

    const matchesMention =
      !mentionsOnly.value ||
      auditUpdates.value.some(
        (update) =>
          update.contractId === item.id &&
          update.mentionedUserIds.includes(currentUserId.value),
      );

    return (
      (unit.value === "Todas" || item.unit === unit.value) &&
      matchesMention &&
      matchesSearch
    );
  });
});


function uiStageFor(item: Contract): UiAuditStage {
  if (item.auditStage) {
    return item.auditStage;
  }

  // Contratos finalizados antes de entrarem no fluxo aparecem em Finalizado.
  if (
    item.finalized ||
    item.situation === "Finalizado" ||
    item.alert === "Finalizado"
  ) {
    return "FINALIZADO";
  }

  return "NAO_INICIADO";
}

function resetStageLimits(): void {
  stageVisibleLimits.value = {};
}

function stageLimit(stage: UiAuditStage): number {
  return stageVisibleLimits.value[stage] ?? INITIAL_STAGE_LIMIT;
}

function showMoreStage(stage: UiAuditStage): void {
  stageVisibleLimits.value[stage] = stageLimit(stage) + STAGE_LIMIT_STEP;
}

function collapseStage(stage: UiAuditStage): void {
  stageVisibleLimits.value[stage] = INITIAL_STAGE_LIMIT;
}

const stageChartData = computed(() => {
  const total = filtered.value.length;

  return STAGES.map((stage) => {
    const count = filtered.value.filter(
      (item) => uiStageFor(item) === stage.key,
    ).length;

    return {
      key: stage.key,
      label: stage.label,
      color: stage.color,
      count,
      percent: total > 0 ? (count / total) * 100 : 0,
    };
  });
});

function focusStage(stage: UiAuditStage): void {
  if (!import.meta.client) return;

  if (hideEmptyStages.value && stageItems(stage).length === 0) {
    hideEmptyStages.value = false;
  }

  nextTick(() => {
    const column = document.querySelector<HTMLElement>(
      `[data-audit-stage="${stage}"]`,
    );

    column?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "center",
    });
  });
}


function stageItems(stage: UiAuditStage): Contract[] {
  const result = filtered.value.filter(
    (item) => uiStageFor(item) === stage,
  );

  return [...result].sort((a, b) => {
    if (auditSortMode.value === "FORNECEDOR") {
      return a.supplier.localeCompare(b.supplier, "pt-BR");
    }

    if (auditSortMode.value === "VENCIMENTO") {
      const aDate = a.endDate
        ? new Date(a.endDate).getTime()
        : Number.MAX_SAFE_INTEGER;
      const bDate = b.endDate
        ? new Date(b.endDate).getTime()
        : Number.MAX_SAFE_INTEGER;
      return aDate - bDate;
    }

    if (auditSortMode.value === "TEMPO") {
      return currentStageElapsedMs(b.id) - currentStageElapsedMs(a.id);
    }

    const alertRank: Record<string, number> = {
      Vencido: 0,
      Atencao: 1,
      Regularizacao: 2,
      Regular: 3,
      SemData: 4,
      Finalizado: 5,
    };

    const rankA = alertRank[a.alert] ?? 9;
    const rankB = alertRank[b.alert] ?? 9;

    if (rankA !== rankB) return rankA - rankB;

    const daysA = a.daysToEnd ?? Number.MAX_SAFE_INTEGER;
    const daysB = b.daysToEnd ?? Number.MAX_SAFE_INTEGER;
    return daysA - daysB;
  });
}

function visibleStageItems(stage: UiAuditStage): Contract[] {
  const all = stageItems(stage);

  // Durante uma busca/menção, mostra todos os resultados encontrados.
  if (search.value.trim() || mentionsOnly.value) {
    return all;
  }

  return all.slice(0, stageLimit(stage));
}

const visibleStages = computed(() =>
  hideEmptyStages.value
    ? STAGES.filter((stage) => stageItems(stage.key).length > 0)
    : STAGES,
);

watch([unit, search, mentionsOnly, auditSortMode], resetStageLimits);



function endDrag(): void {

  draggedId.value = null;

  overStage.value = null;

}

async function moveContract(
  item: Contract,
  stage: AuditStage,
): Promise<void> {
  if (!item.canEdit || uiStageFor(item) === stage || movingId.value) return;

  const previous = { ...item };
  const fromStage = previous.auditStage ?? undefined;
  const fromUiStage = uiStageFor(previous);

  if (
    stage === "FINALIZADO" &&
    fromUiStage !== "FINALIZADO" &&
    !window.confirm(
      `Finalizar o contrato ${item.contractNumber}? Essa ação moverá o contrato para a última etapa.`,
    )
  ) {
    return;
  }

  movingId.value = item.id;
  error.value = "";

  try {
    const updated = await api.patch<Contract>(
      `/contratos/${item.id}/auditoria`,
      { stage },
    );
    const index = items.value.findIndex((candidate) => candidate.id === item.id);
    if (index >= 0) items.value.splice(index, 1, updated);
    registerStageTransition(item.id, fromStage, stage);
    currentStageTiming.value[item.id] = {
      stage,
      startedAt: updated.auditStageEnteredAt ?? new Date().toISOString(),
    };
    if (selectedContract.value?.id === item.id) {
      selectedContract.value = updated;
      await loadWorkspace(item.id);
    }
  } catch (cause) {
    Object.assign(item, previous);
    error.value =
      cause instanceof Error
        ? cause.message
        : "Não foi possível mover o contrato.";
  } finally {
    movingId.value = null;
    endDrag();
  }
}



const selectedStageTimes = computed(() => {
  const contract = selectedContract.value;
  if (!contract) return [];

  // Faz o computed reagir ao relógio enquanto a etapa atual está em andamento.
  const now = stageClock.value;
  const history = stageTimingHistory.value[contract.id] ?? [];
  const current = currentStageTiming.value[contract.id];

  return STAGES.map((stage) => {
    const completedMs = history
      .filter((entry) => entry.stage === stage.key)
      .reduce((total, entry) => total + entry.durationMs, 0);

    const currentMs =
      current?.stage === stage.key
        ? Math.max(0, now - new Date(current.startedAt).getTime())
        : 0;

    return {
      key: stage.key,
      label: stage.label,
      durationMs: completedMs + currentMs,
      isCurrent: current?.stage === stage.key,
      hasTiming: completedMs > 0 || current?.stage === stage.key,
    };
  }).filter((stage) => stage.hasTiming);
});

const selectedUiStage = computed<UiAuditStage | null>(() => {
  const contract = selectedContract.value;
  return contract ? uiStageFor(contract) : null;
});

const selectedStageIndex = computed(() => {
  const contract = selectedContract.value;
  if (!contract) return -1;

  const currentStage = uiStageFor(contract);
  return STAGES.findIndex((stage) => stage.key === currentStage);
});

const selectedCurrentStageLabel = computed(() => {
  const contract = selectedContract.value;
  if (!contract) return "Não definida";

  return (
    STAGES.find((stage) => stage.key === uiStageFor(contract))?.label ??
    "Não definida"
  );
});

const selectedNextStageLabel = computed(() => {
  const index = selectedStageIndex.value;
  const next = index >= 0 ? STAGES[index + 1] : undefined;
  return next?.label ?? "Fluxo concluído";
});

const selectedLastActivity = computed(
  () => selectedContractActivity.value[0] ?? null,
);

const canMoveSelectedBack = computed(
  () =>
    Boolean(selectedContract.value?.canEdit) &&
    // Não permitimos voltar de Aguardando Análise para o backlog "Não iniciado".
    selectedStageIndex.value > 1 &&
    !movingId.value,
);

const canMoveSelectedForward = computed(
  () =>
    Boolean(selectedContract.value?.canEdit) &&
    selectedStageIndex.value >= 0 &&
    selectedStageIndex.value < STAGES.length - 1 &&
    !movingId.value,
);

function moveSelectedBack(): void {
  const contract = selectedContract.value;
  const index = selectedStageIndex.value;
  const targetStage = STAGES[index - 1];

  if (
    !contract ||
    index <= 1 ||
    !targetStage ||
    targetStage.key === "NAO_INICIADO"
  ) {
    return;
  }

  void moveContract(contract, targetStage.key);
}

function moveSelectedForward(): void {
  const contract = selectedContract.value;
  const index = selectedStageIndex.value;
  const targetStage = STAGES[index + 1];

  if (
    !contract ||
    index < 0 ||
    index >= STAGES.length - 1 ||
    !targetStage ||
    targetStage.key === "NAO_INICIADO"
  ) {
    return;
  }

  void moveContract(contract, targetStage.key);
}

function openContract(item: Contract): void {
  selectedContract.value = item;
  activeAuditTab.value = "updates";
  newUpdateText.value = "";
  pendingAttachments.value = [];
  void loadWorkspace(item.id).catch((cause: unknown) => {
    error.value = cause instanceof Error ? cause.message : "Não foi possível carregar os detalhes.";
  });
}

function closeContract(): void {
  selectedContract.value = null;
  activeAuditTab.value = "updates";
  newUpdateText.value = "";
  pendingAttachments.value = [];
  mentionOpen.value = false;
  mentionSearch.value = "";
  cancelEditUpdate();
}

</script>

<template>

  <div class="audit-board-page">

    <section class="surface audit-flow-overview" aria-label="Distribuição dos contratos por etapa">
      <header class="audit-flow-overview-head">
        <div>
          <span>Distribuição do fluxo</span>
          <strong>Contratos por etapa</strong>
        </div>

        <div class="audit-flow-total">
          <strong>{{ filtered.length }}</strong>
          <span>na auditoria</span>
        </div>
      </header>

      <div
        class="audit-flow-segments"
        role="img"
        :aria-label="`Distribuição de ${filtered.length} contratos entre as etapas da auditoria`"
      >
        <button
          v-for="stage in stageChartData.filter((item) => item.count > 0)"
          :key="stage.key"
          type="button"
          class="audit-flow-segment"
          :style="{
            width: `${stage.percent}%`,
            backgroundColor: stage.color,
          }"
          :data-count="stage.percent < 12 ? stage.count : ''"
          :title="`${stage.label}: ${stage.count} contrato${stage.count === 1 ? '' : 's'} (${stage.percent.toFixed(0)}%)`"
          @click="focusStage(stage.key)"
        >
          <span v-if="stage.percent >= 12">
            {{ stage.count }}
          </span>
        </button>

        <div v-if="filtered.length === 0" class="audit-flow-empty">
          Nenhum contrato corresponde aos filtros atuais.
        </div>
      </div>

      <div class="audit-flow-legend">
        <button
          v-for="stage in stageChartData"
          :key="stage.key"
          type="button"
          class="audit-flow-legend-item"
          :class="{ empty: stage.count === 0 }"
          @click="focusStage(stage.key)"
        >
          <span
            class="audit-flow-dot"
            :style="{ backgroundColor: stage.color }"
          />
          <span class="audit-flow-legend-label">{{ stage.label }}</span>
          <strong>{{ stage.count }}</strong>
          <small v-if="stage.count > 0">{{ stage.percent.toFixed(0) }}%</small>
        </button>
      </div>
    </section>

    <div class="audit-all-contracts-note">
      <strong>Todos os contratos estão incluídos.</strong>
      <span>
        Contratos sem histórico ficam em “Não iniciado”; contratos já
        finalizados aparecem diretamente em “Finalizado”.
      </span>
    </div>

    <section class="surface audit-toolbar audit-toolbar-refined" aria-label="Filtros da auditoria">
      <div class="audit-filter-row audit-filter-row-simple">
        <label>
          <span>Unidade</span>
          <select v-model="unit">
            <option>Todas</option>
            <option v-for="item in units" :key="item">{{ item }}</option>
          </select>
        </label>

        <label>
          <span>Ordenar cards</span>
          <select v-model="auditSortMode">
            <option value="PRIORIDADE">Prioridade e atraso</option>
            <option value="VENCIMENTO">Vencimento</option>
            <option value="FORNECEDOR">Fornecedor A–Z</option>
            <option value="TEMPO">Mais tempo na etapa</option>
          </select>
        </label>

        <label class="audit-search">
          <span>Buscar</span>
          <div>
            <Search class="size-4" />
            <input
              v-model="search"
              type="search"
              placeholder="Contrato, fornecedor, unidade ou comentário"
            />
          </div>
        </label>
      </div>

      <div class="audit-toolbar-bottom">
        <div class="audit-toolbar-hint">
          <span class="audit-live-dot" />
          <span>
            {{ filtered.length }} contrato{{ filtered.length === 1 ? "" : "s" }} visível{{ filtered.length === 1 ? "" : "eis" }}
          </span>
        </div>

        <div class="audit-toolbar-actions">
          <button
            type="button"
            class="btn"
            :class="{ active: mentionsOnly }"
            @click="mentionsOnly = !mentionsOnly"
          >
            @ Menções
            <span v-if="myMentionCount" class="audit-action-count">
              {{ myMentionCount }}
            </span>
          </button>

          <button type="button" class="btn" @click="compactMode = !compactMode">
            {{ compactMode ? "Cards normais" : "Compactar" }}
          </button>

          <button
            type="button"
            class="btn"
            :class="{ active: hideEmptyStages }"
            @click="hideEmptyStages = !hideEmptyStages"
          >
            {{ hideEmptyStages ? "Mostrar vazias" : "Ocultar vazias" }}
          </button>
<button type="button" class="btn btn-primary-soft" :disabled="loading" @click="load">
            <RefreshCw class="size-4" />
            Atualizar
          </button>
        </div>
      </div>
    </section>

    <p

      v-if="error"

      class="contracts-state error"

      role="alert"

    >

      {{ error }}

    </p>

    <div

      v-if="loading && !items.length"

      class="contracts-state"

    >

      Carregando auditoria…

    </div>

    <template v-else>



      <div class="audit-board-scroll">

        <div

          class="audit-kanban"

          aria-label="Kanban de auditoria de todos os contratos"

        >

          <section

            v-for="stage in visibleStages"

            :key="stage.key"

            :data-audit-stage="stage.key"

            class="audit-column"

            :class="{ 'is-over': overStage === stage.key }"

            :style="{ '--column-accent': stage.color }"

          >

            <header>

              <div class="audit-column-heading">

                <span class="audit-column-stage">

                  {{ STAGES.findIndex((item) => item.key === stage.key) + 1 }}

                </span>

                <h3>{{ stage.label }}</h3>

              </div>

              <span class="audit-column-count">

                {{ stageItems(stage.key).length }}

              </span>

            </header>

            <div class="audit-column-accent" />

            <div class="audit-column-body">

              <article

                v-for="item in visibleStageItems(stage.key)"

                :key="item.id"

                class="audit-contract-card"

                :class="{
                  'is-moving': movingId === item.id,
                  'is-compact': compactMode,
                  'is-bottleneck-warning': bottleneckLevel(item.id) === 'warning',
                  'is-bottleneck-critical': bottleneckLevel(item.id) === 'critical',
                }"

              >

                <button

                  type="button"

                  class="audit-card-main"

                  @click="openContract(item)"

                >

                  <span class="audit-card-topline">

                    <strong>

                      Contrato {{ item.contractNumber }}

                    </strong>

                  </span>

                  <span class="audit-card-supplier">

                    {{ item.supplier }}

                  </span>

                  <div class="audit-card-badges">
                    <span
                      v-if="uiStageFor(item) === 'NAO_INICIADO'"
                      class="audit-stage-age level-not-started"
                    >
                      Ainda não iniciado
                    </span>

                    <span
                      v-else-if="item.auditStage"
                      class="audit-stage-age"
                      :class="`level-${bottleneckLevel(item.id)}`"
                    >
                      {{ currentStageElapsedLabel(item.id) }} nesta etapa
                    </span>

                    <span
                      v-else
                      class="audit-stage-age level-finalized"
                    >
                      Finalizado
                    </span>
                  </div>

                  <span class="audit-card-meta">

                    <Building2 class="size-3.5" />

                    {{ item.unit || "Sem unidade" }}

                    ·

                    {{ item.sectorName }}

                  </span>

                  <span class="audit-card-meta">

                    <CalendarDays class="size-3.5" />

                    {{ dateBr(item.endDate) }}

                    ·

                    {{

                      item.finalized

                        ? "Finalizado"

                        : daysToEndLabel(item.daysToEnd)

                    }}

                  </span>

                  <span class="audit-card-meta">

                    <WalletCards class="size-3.5" />

                    {{ money(item.totalValue) }}

                  </span>

                </button>



              </article>

              <p

                v-if="!stageItems(stage.key).length"

                class="audit-column-empty"

              >

                <span />

                Nenhum contrato

              </p>

            </div>

            <footer
              v-if="
                !search.trim() &&
                !mentionsOnly &&
                stageItems(stage.key).length > INITIAL_STAGE_LIMIT
              "
              class="audit-column-pagination"
            >
              <span>
                Exibindo
                {{ Math.min(stageLimit(stage.key), stageItems(stage.key).length) }}
                de {{ stageItems(stage.key).length }}
              </span>

              <div>
                <button
                  v-if="stageLimit(stage.key) > INITIAL_STAGE_LIMIT"
                  type="button"
                  @click="collapseStage(stage.key)"
                >
                  Recolher
                </button>

                <button
                  v-if="stageLimit(stage.key) < stageItems(stage.key).length"
                  type="button"
                  @click="showMoreStage(stage.key)"
                >
                  Mostrar mais {{ STAGE_LIMIT_STEP }}
                </button>
              </div>
            </footer>

          </section>

        </div>

      </div>

      <p class="audit-board-help">

        “Não iniciado” é o backlog dos contratos que ainda não começaram o fluxo. Ao avançar, eles entram em Aguardando Análise.

      </p>

    </template>

    <!-- Painel lateral do contrato -->

    <div

      v-if="selectedContract"

      class="audit-detail-backdrop"

      @click.self="closeContract"

    >

      <aside class="audit-detail-panel">

        <header class="audit-detail-header">

          <div>

            <span>

              Contrato {{ selectedContract.contractNumber }}

            </span>

            <h2>

              {{ selectedContract.supplier }}

            </h2>

          </div>

          <button

            type="button"

            class="audit-detail-close"

            aria-label="Fechar"

            @click="closeContract"

          >

            ×

          </button>

        </header>

        <div class="audit-detail-content">

          <!-- Informações -->

          <section class="audit-detail-info">

            <div class="audit-section-heading">

              <h3>Informações</h3>

              <span class="audit-status-badge">

                {{ selectedContract.situation }}

              </span>

            </div>

            <div class="audit-info-item">

              <span>Fornecedor</span>

              <strong>

                {{ selectedContract.supplier }}

              </strong>

            </div>

            <div class="audit-info-item">

              <span>Contrato</span>

              <strong>

                {{ selectedContract.contractNumber }}

              </strong>

            </div>

            <div class="audit-info-item">

              <span>Unidade</span>

              <strong>

                {{

                  selectedContract.unit ||

                  "Não informada"

                }}

              </strong>

            </div>

            <div class="audit-info-item">

              <span>Setor</span>

              <strong>

                {{ selectedContract.sectorName }}

              </strong>

            </div>


            <div class="audit-info-item">

              <span>Vencimento</span>

              <strong>

                {{ dateBr(selectedContract.endDate) }}

              </strong>

            </div>

            <div class="audit-info-item">

              <span>Valor do contrato</span>

              <strong>

                {{ money(selectedContract.totalValue) }}

              </strong>

            </div>

            <div class="audit-info-item audit-stage-control">
              <span>Etapa atual</span>

              <div class="audit-stage-navigation">
                <button
                  type="button"
                  class="audit-stage-arrow"
                  :disabled="!canMoveSelectedBack"
                  aria-label="Retroceder etapa"
                  title="Retroceder etapa"
                  @click="moveSelectedBack"
                >
                  ←
                </button>

                <div class="audit-stage-current">
                  <strong>{{ selectedCurrentStageLabel }}</strong>
                </div>

                <button
                  type="button"
                  class="audit-stage-arrow"
                  :disabled="!canMoveSelectedForward"
                  aria-label="Avançar etapa"
                  title="Avançar etapa"
                  @click="moveSelectedForward"
                >
                  →
                </button>
              </div>
            </div>

            <div
              v-if="selectedStageTimes.length"
              class="audit-info-item audit-leadtime-item"
            >
              <span>Tempo por etapa</span>

              <div class="audit-stage-times">
                <div
                  v-for="stage in selectedStageTimes"
                  :key="stage.key"
                  class="audit-stage-time-row"
                  :class="{ current: stage.isCurrent }"
                >
                  <div>
                    <strong>{{ stage.label }}</strong>
                    <small v-if="stage.isCurrent">Etapa atual</small>
                  </div>

                  <b>{{ formatStageDuration(stage.durationMs) }}</b>
                </div>
              </div>

              <small>
                Contagem iniciada a partir desta versão da Auditoria.
              </small>
            </div>

            <div
              v-else
              class="audit-info-item audit-not-started-info"
            >
              <span>Tempo por etapa</span>

              <template v-if="selectedUiStage === 'NAO_INICIADO'">
                <strong>Ainda não iniciado</strong>
                <small>
                  A contagem começa quando o contrato avançar para
                  Aguardando Análise.
                </small>
              </template>

              <template v-else>
                <strong>Sem histórico nesta versão</strong>
                <small>
                  O contrato já estava finalizado antes do início da contagem
                  local de etapas.
                </small>
              </template>
            </div>

            <div class="audit-info-item">
              <span>Situação</span>

              <strong>

                {{ selectedContract.situation }}

              </strong>

            </div>

          </section>

          <!-- Atualizações -->

          <section class="audit-detail-updates">
            <div class="audit-updates-tabs">
              <button
                type="button"
                :class="{ active: activeAuditTab === 'updates' }"
                @click="activeAuditTab = 'updates'"
              >
                Atualizações
                <span
                  v-if="selectedContractUpdates.length"
                  class="audit-tab-count"
                >
                  {{ selectedContractUpdates.length }}
                </span>
              </button>

              <button
                type="button"
                :class="{ active: activeAuditTab === 'files' }"
                @click="activeAuditTab = 'files'"
              >
                Arquivos
                <span
                  v-if="selectedContractFiles.length"
                  class="audit-tab-count"
                >
                  {{ selectedContractFiles.length }}
                </span>
              </button>

              <button
                type="button"
                :class="{ active: activeAuditTab === 'activity' }"
                @click="activeAuditTab = 'activity'"
              >
                Atividade
                <span
                  v-if="selectedContractActivity.length"
                  class="audit-tab-count"
                >
                  {{ selectedContractActivity.length }}
                </span>
              </button>
            </div>

            <div class="audit-update-body">
              <template v-if="activeAuditTab === 'updates'">
                <div class="audit-update-composer">
                  <textarea
                    ref="updateTextarea"
                    v-model="newUpdateText"
                    placeholder="Escreva uma atualização e mencione outros usuários com @"
                    @keydown.ctrl.enter="publishUpdate"
                  />

                  <div v-if="mentionOpen" class="audit-mention-picker">
                    <input
                      v-model="mentionSearch"
                      type="search"
                      placeholder="Buscar usuário para mencionar"
                    />

                    <button
                      v-for="user in filteredMentionUsers"
                      :key="user.id"
                      type="button"
                      @click="selectMention(user)"
                    >
                      <strong>{{ user.name }}</strong>
                      <span>{{ user.role }}</span>
                    </button>

                    <p v-if="!filteredMentionUsers.length">
                      Nenhum usuário encontrado.
                    </p>
                  </div>

                  <div
                    v-if="pendingAttachments.length"
                    class="audit-pending-files"
                  >
                    <div
                      v-for="attachment in pendingAttachments"
                      :key="attachment.id"
                      class="audit-pending-file"
                    >
                      <span class="audit-file-icon">📎</span>

                      <div>
                        <strong>{{ attachment.name }}</strong>
                        <span>{{ formatFileSize(attachment.size) }}</span>
                      </div>

                      <button
                        type="button"
                        aria-label="Remover anexo"
                        @click="removePendingAttachment(attachment.id)"
                      >
                        ×
                      </button>
                    </div>
                  </div>

                  <input
                    ref="attachmentInput"
                    class="audit-file-input"
                    type="file"
                    multiple
                    @change="onAttachmentSelected"
                  />

                  <div class="audit-update-actions">
                    <button
                      type="button"
                      class="audit-text-action"
                      @click="insertMention"
                    >
                      @ Mencionar
                    </button>

                    <button
                      type="button"
                      class="audit-text-action"
                      @click="openAttachmentPicker"
                    >
                      📎 Anexar
                    </button>

                    <button
                      type="button"
                      class="audit-publish-button"
                      :disabled="!newUpdateText.trim() && pendingAttachments.length === 0"
                      @click="publishUpdate"
                    >
                      Publicar
                    </button>
                  </div>
                </div>

                <div class="audit-timeline">
                  <div
                    v-if="selectedContractUpdates.length === 0"
                    class="audit-empty-updates"
                  >
                    <div class="audit-empty-icon">☰</div>

                    <strong>Nenhuma atualização ainda</strong>

                    <p>
                      Compartilhe o progresso, mencione um colega
                      ou adicione informações sobre este contrato.
                    </p>

                    <div class="audit-empty-summary">
                      <div>
                        <span>Etapa atual</span>
                        <strong>
                          {{
                            STAGES.find(
                              (stage) =>
                                stage.key === selectedUiStage,
                            )?.label
                          }}
                        </strong>
                      </div>

                      <div>
                        <span>Próxima etapa</span>
                        <strong>{{ selectedNextStageLabel }}</strong>
                      </div>

                      <div>
                        <span>Última atividade</span>
                        <strong v-if="selectedLastActivity">
                          {{ formatAuditDate(selectedLastActivity.createdAt) }}
                        </strong>
                        <strong v-else>Nenhuma</strong>
                      </div>
                    </div>
                  </div>

                  <div
                    v-else
                    class="audit-update-list"
                  >
                    <article
                      v-for="update in selectedContractUpdates"
                      :key="update.id"
                      class="audit-update-item"
                    >
                      <div class="audit-update-item-header">
                        <div class="audit-update-author">
                          <strong>{{ update.author }}</strong>
                          <span>{{ formatAuditDate(update.createdAt) }}</span>
                        </div>

                        <div class="audit-update-item-actions">
                          <button
                            v-if="update.canEdit && editingUpdateId !== update.id"
                            type="button"
                            @click="startEditUpdate(update)"
                          >
                            Editar
                          </button>

                          <button
                            v-if="update.canEdit && editingUpdateId !== update.id"
                            type="button"
                            class="danger"
                            @click="deleteUpdate(update.id)"
                          >
                            Excluir
                          </button>
                        </div>
                      </div>

                      <template v-if="editingUpdateId === update.id">
                        <textarea
                          v-model="editingUpdateText"
                          class="audit-edit-textarea"
                        />

                        <div class="audit-edit-actions">
                          <button
                            type="button"
                            class="btn small"
                            @click="cancelEditUpdate"
                          >
                            Cancelar
                          </button>

                          <button
                            type="button"
                            class="btn small"
                            :disabled="!editingUpdateText.trim()"
                            @click="saveEditUpdate(update.id)"
                          >
                            Salvar
                          </button>
                        </div>
                      </template>

                      <p v-else-if="update.text">
                        {{ update.text }}
                      </p>

                      <div
                        v-if="update.attachments.length"
                        class="audit-update-attachments"
                      >
                        <button
                          v-for="attachment in update.attachments"
                          :key="attachment.id"
                          type="button"
                          class="audit-update-attachment"
                          @click="openAttachment(attachment)"
                        >
                          <img
                            v-if="isImageAttachment(attachment)"
                            :src="attachment.url"
                            :alt="attachment.name"
                            class="audit-update-image"
                          />

                          <template v-else>
                            <span class="audit-update-file-icon">📎</span>

                            <div>
                              <strong>{{ attachment.name }}</strong>
                              <small>{{ formatFileSize(attachment.size) }}</small>
                            </div>
                          </template>
                        </button>
                      </div>
                    </article>
                  </div>
                </div>
              </template>

              <template v-else-if="activeAuditTab === 'files'">
                <div
                  v-if="selectedContractFiles.length === 0"
                  class="audit-empty-updates"
                >
                  <div class="audit-empty-icon">📎</div>

                  <strong>Nenhum arquivo anexado</strong>

                  <p>
                    Os arquivos relacionados à regularização
                    deste contrato aparecerão aqui.
                  </p>
                </div>

                <div
                  v-else
                  class="audit-files-list"
                >
                  <button
                    v-for="file in selectedContractFiles"
                    :key="`${file.updateId}-${file.id}`"
                    type="button"
                    class="audit-file-card"
                    @click="openAttachment(file)"
                  >
                    <img
                      v-if="isImageAttachment(file)"
                      :src="file.url"
                      :alt="file.name"
                      class="audit-file-card-preview"
                    />

                    <span
                      v-else
                      class="audit-file-card-icon"
                    >
                      📎
                    </span>

                    <div>
                      <strong>{{ file.name }}</strong>
                      <span>
                        {{ formatFileSize(file.size) }} ·
                        {{ file.author }} ·
                        {{ formatAuditDate(file.createdAt) }}
                      </span>
                    </div>
                  </button>
                </div>
              </template>

              <template v-else>
                <div
                  v-if="selectedContractActivity.length === 0"
                  class="audit-empty-updates"
                >
                  <div class="audit-empty-icon">☰</div>
                  <strong>Nenhuma atividade registrada</strong>
                  <p>
                    Movimentações, comentários, responsáveis e prioridades
                    aparecerão aqui.
                  </p>
                </div>

                <div v-else class="audit-activity-list">
                  <article
                    v-for="activity in selectedContractActivity"
                    :key="activity.id"
                    class="audit-activity-item"
                  >
                    <span class="audit-activity-dot" />
                    <div>
                      <p>
                        <strong>{{ activity.userName || userName(activity.userId) }}</strong>
                        {{ activity.message }}
                      </p>
                      <small>{{ formatAuditDate(activity.createdAt) }}</small>
                    </div>
                  </article>
                </div>
              </template>
            </div>
          </section>

        </div>

      </aside>
    </div>


  </div>

</template>

<style scoped>

.audit-board-page {

  display: grid;

  gap: 16px;

}

.audit-toolbar {

  display: grid;

  grid-template-columns:

    minmax(260px, 1fr)

    minmax(300px, 1fr)

    auto;

  gap: 12px;

  align-items: end;

  padding: 16px;

}

.audit-toolbar label {

  display: grid;

  gap: 6px;

}

.audit-toolbar label > span {

  color: #52657f;

  font-size: 10px;

  font-weight: 800;

  letter-spacing: 0.04em;

  text-transform: uppercase;

}

.audit-toolbar select,

.audit-toolbar input {

  width: 100%;

  height: 42px;

  border: 1px solid #dbe3ee;

  border-radius: 10px;

  outline: none;

  background: #fff;

  color: #20324a;

  font-size: 13px;

}

.audit-toolbar select {

  padding: 0 12px;

}

.audit-search > div {

  position: relative;

}

.audit-search svg {

  position: absolute;

  top: 13px;

  left: 12px;

  color: #8190a5;

}

.audit-search input {

  padding: 0 12px 0 38px;

}

.audit-toolbar select:focus,

.audit-toolbar input:focus {

  border-color: #5b7fb2;

  box-shadow: 0 0 0 3px rgba(48, 79, 126, 0.12);

}

.audit-toolbar-summary {

  display: flex;

  align-items: center;

  padding-bottom: 1px;

}

.audit-summary {

  display: flex;

  align-items: center;

  justify-content: space-between;

  gap: 18px;

  padding: 12px 15px;

  border: 1px solid #e0e6ee;

  border-radius: 11px;

  background: #fff;

  box-shadow: 0 5px 18px rgb(35 55 80 / 4%);

}

.audit-summary-main {

  display: flex;

  align-items: center;

  gap: 10px;

}

.audit-summary-icon {

  display: grid;

  width: 32px;

  height: 32px;

  flex: 0 0 32px;

  place-items: center;

  border-radius: 8px;

  background: #edf2f8;

  color: #304f7e;

}

.audit-summary-main > div {

  display: grid;

  gap: 1px;

}

.audit-summary-main strong {

  color: #2b3e58;

  font-size: 11.5px;

  font-weight: 750;

}

.audit-summary-main span {

  color: #8793a4;

  font-size: 10px;

}

.audit-summary-badge {

  display: inline-flex;

  align-items: center;

  gap: 6px;

  padding: 5px 9px;

  border: 1px solid #dbe3ed;

  border-radius: 999px;

  background: #f7f9fc;

  color: #66758a;

  font-size: 9.5px;

  font-weight: 700;

}

.audit-board-scroll {

  width: 100%;

  overflow-x: auto;

  overflow-y: hidden;

  padding: 1px 1px 10px;

  scrollbar-color: #aab3bf #edf1f5;

  scrollbar-width: thin;

}

.audit-board-scroll::-webkit-scrollbar {

  height: 9px;

}

.audit-board-scroll::-webkit-scrollbar-track {

  border-radius: 999px;

  background: #edf1f5;

}

.audit-board-scroll::-webkit-scrollbar-thumb {

  border: 2px solid #edf1f5;

  border-radius: 999px;

  background: #aab3bf;

}

.audit-kanban {

  display: flex;

  width: max-content;

  min-width: 100%;

  align-items: stretch;

  gap: 12px;

}

.audit-column {

  --column-accent: #7890ad;

  display: flex;

  width: 286px;

  min-width: 286px;

  height: clamp(500px, calc(100vh - 360px), 720px);

  flex-direction: column;

  overflow: hidden;

  border: 1px solid #dfe5ed;

  border-radius: 11px;

  background: #f4f6f9;

  box-shadow: 0 4px 14px rgb(31 49 73 / 3%);

  transition:

    border-color 0.15s ease,

    box-shadow 0.15s ease;

}

.audit-column.is-over {

  border-color: #5b7fb2;

  box-shadow: inset 0 0 0 2px rgba(48, 79, 126, 0.12);

}

.audit-column > header {

  display: flex;

  min-height: 48px;

  align-items: center;

  justify-content: space-between;

  gap: 10px;

  padding: 0 12px;

  background: #fff;

}

.audit-column-heading {

  display: flex;

  min-width: 0;

  align-items: center;

  gap: 7px;

}

.audit-column-heading h3 {

  overflow: hidden;

  margin: 0;

  color: #243953;

  font-size: 11.5px;

  font-weight: 780;

  line-height: 1.25;

  text-overflow: ellipsis;

  white-space: nowrap;

}

.audit-column-stage {

  display: grid;

  width: 22px;

  height: 22px;

  flex: 0 0 22px;

  place-items: center;

  border-radius: 6px;

  background: color-mix(

    in srgb,

    var(--column-accent) 14%,

    white

  );

  color: var(--column-accent);

  font-size: 9px;

  font-weight: 800;

}

.audit-column-count {

  display: inline-flex;

  min-width: 24px;

  min-height: 24px;

  align-items: center;

  justify-content: center;

  padding: 2px 7px;

  border: 1px solid #e0e6ee;

  border-radius: 999px;

  background: #f8fafc;

  color: #6f7e91;

  font-size: 9.5px;

  font-weight: 760;

}

.audit-column-accent {

  width: 100%;

  height: 4px;

  flex: 0 0 4px;

  background: var(--column-accent);

}

.audit-column-body {

  display: flex;

  min-height: 0;

  flex: 1;

  flex-direction: column;

  gap: 9px;

  overflow-y: auto;

  padding: 10px;

  scrollbar-color: #aeb7c2 transparent;

  scrollbar-width: thin;

}

.audit-column-body::-webkit-scrollbar {

  width: 7px;

}

.audit-column-body::-webkit-scrollbar-thumb {

  border: 2px solid transparent;

  border-radius: 999px;

  background: #aeb7c2;

  background-clip: content-box;

}

.audit-contract-card {

  flex: 0 0 auto;

  overflow: hidden;

  border: 1px solid #dde4ec;

  border-radius: 10px;

  background: #fff;

  box-shadow: 0 3px 9px rgb(31 48 70 / 3%);

  transition:

    opacity 0.15s ease,

    transform 0.15s ease,

    box-shadow 0.15s ease,

    border-color 0.15s ease;

}

.audit-contract-card[draggable="true"] {

  cursor: grab;

}

.audit-contract-card[draggable="true"]:active {

  cursor: grabbing;

}

.audit-contract-card:hover {

  border-color: #bcc9d8;

  transform: translateY(-1px);

  box-shadow: 0 7px 18px rgb(31 48 70 / 8%);

}

.audit-contract-card.is-dragging {

  opacity: 0.45;

}

.audit-contract-card.is-moving {

  opacity: 0.65;

  pointer-events: none;

}

.audit-card-main {

  display: grid;

  gap: 9px;

  width: 100%;

  padding: 12px;

  border: 0;

  background: transparent;

  color: #20324a;

  text-align: left;

}

.audit-card-main:focus-visible {

  outline: 2px solid #5b7fb2;

  outline-offset: -2px;

}

.audit-card-topline {

  display: flex;

  align-items: center;

  justify-content: space-between;

  gap: 6px;

}

.audit-card-topline strong {

  color: #536b88;

  font-size: 10px;

  font-weight: 800;

  letter-spacing: 0.025em;

  text-transform: uppercase;

}

.audit-card-topline svg {

  flex: 0 0 auto;

  color: #8c98a9;

}

.audit-card-supplier {

  display: -webkit-box;

  overflow: hidden;

  color: #243953;

  font-size: 12.5px;

  font-weight: 750;

  line-height: 1.4;

  -webkit-box-orient: vertical;

  -webkit-line-clamp: 3;

}

.audit-card-meta {

  display: flex;

  align-items: flex-start;

  gap: 5px;

  color: #77869a;

  font-size: 10px;

  font-weight: 550;

  line-height: 1.4;

}

.audit-card-meta svg {

  flex: 0 0 auto;

  margin-top: 1px;

  color: #7890ae;

}

.audit-card-move {

  display: grid;

  gap: 4px;

  padding: 9px 12px 11px;

  border-top: 1px solid #eef1f5;

}

.audit-card-move span,

.audit-card-readonly {

  color: #8a97ab;

  font-size: 8.5px;

  font-weight: 800;

  letter-spacing: 0.04em;

  text-transform: uppercase;

}

.audit-card-move select {

  width: 100%;

  height: 31px;

  padding: 0 8px;

  border: 1px solid #dce3ec;

  border-radius: 7px;

  background: #f9fafc;

  color: #34465f;

  font-size: 10px;

}

.audit-card-readonly {

  display: block;

  padding: 0 10px 10px;

}

.audit-column-empty {

  display: inline-flex;

  align-items: center;

  align-self: center;

  gap: 7px;

  margin-top: 12px;

  padding: 7px 9px;

  color: #9aa5b4;

  font-size: 10px;

  font-weight: 500;

}

.audit-column-empty span {

  width: 6px;

  height: 6px;

  border-radius: 50%;

  background: #c8d0da;

}

.audit-board-help {

  margin: 0;

  color: #7b8798;

  font-size: 11px;

  text-align: right;

}

/* PAINEL DO CONTRATO */

.audit-detail-backdrop {

  position: fixed;

  inset: 0;

  z-index: 1000;

  display: flex;

  justify-content: flex-end;

  background: rgba(20, 32, 50, 0.34);

  backdrop-filter: blur(2px);

}

.audit-detail-panel {

  width: min(1080px, 88vw);

  height: 100vh;

  overflow: hidden;

  background: #fff;

  box-shadow: -14px 0 45px rgba(25, 42, 64, 0.18);

}

.audit-detail-header {

  display: flex;

  min-height: 84px;

  align-items: center;

  justify-content: space-between;

  gap: 20px;

  padding: 18px 26px;

  border-bottom: 1px solid #e2e7ee;

  background: #fff;

}

.audit-detail-header > div {

  min-width: 0;

}

.audit-detail-header span {

  display: block;

  margin-bottom: 4px;

  color: #6f8096;

  font-size: 10px;

  font-weight: 800;

  letter-spacing: 0.05em;

  text-transform: uppercase;

}

.audit-detail-header h2 {

  overflow: hidden;

  margin: 0;

  color: #20324a;

  font-size: 18px;

  font-weight: 750;

  line-height: 1.3;

  text-overflow: ellipsis;

  white-space: nowrap;

}

.audit-detail-close {

  display: grid;

  width: 36px;

  height: 36px;

  flex: 0 0 36px;

  place-items: center;

  border: 1px solid #dfe5ed;

  border-radius: 9px;

  background: #fff;

  color: #66758a;

  font-size: 23px;

  line-height: 1;

  cursor: pointer;

}

.audit-detail-close:hover {

  border-color: #bdc9d8;

  background: #f5f7fa;

  color: #20324a;

}

.audit-detail-content {

  display: grid;

  grid-template-columns: 330px minmax(0, 1fr);

  height: calc(100vh - 84px);

}

/* INFORMAÇÕES */

.audit-detail-info {

  overflow-y: auto;

  padding: 24px;

  border-right: 1px solid #e2e7ee;

  background: #f8fafc;

}

.audit-section-heading {

  display: flex;

  align-items: center;

  justify-content: space-between;

  gap: 12px;

  margin-bottom: 10px;

}

.audit-section-heading h3 {

  margin: 0;

  color: #20324a;

  font-size: 14px;

  font-weight: 800;

}

.audit-status-badge {

  padding: 5px 9px;

  border: 1px solid #f1c5c5;

  border-radius: 999px;

  background: #fff1f1;

  color: #b84b52;

  font-size: 8.5px;

  font-weight: 800;

  letter-spacing: 0.03em;

  text-transform: uppercase;

}

.audit-info-item {

  display: grid;

  gap: 5px;

  padding: 14px 0;

  border-bottom: 1px solid #e5eaf0;

}

.audit-info-item > span {

  color: #8491a3;

  font-size: 9px;

  font-weight: 800;

  letter-spacing: 0.05em;

  text-transform: uppercase;

}

.audit-info-item > strong {

  color: #2c3f58;

  font-size: 12px;

  font-weight: 650;

  line-height: 1.45;

}


.audit-stage-control {
  gap: 8px;
}

.audit-stage-navigation {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) 38px;
  align-items: center;
  gap: 8px;
}

.audit-stage-current {
  display: grid;
  min-height: 38px;
  place-items: center;
  padding: 7px 10px;
  border: 1px solid #dce3ec;
  border-radius: 9px;
  background: #fff;
}

.audit-stage-current strong {
  color: #2c3f58;
  font-size: 11px;
  font-weight: 750;
  line-height: 1.3;
  text-align: center;
}

.audit-stage-arrow {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border: 1px solid #cfd9e6;
  border-radius: 9px;
  background: #fff;
  color: #304f7e;
  font-size: 20px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease,
    transform 0.15s ease;
}

.audit-stage-arrow:hover:not(:disabled) {
  border-color: #9fb1c8;
  background: #eef3f8;
  transform: translateY(-1px);
}

.audit-stage-arrow:disabled {
  border-color: #e5eaf0;
  background: #f7f9fb;
  color: #b8c2cf;
  cursor: not-allowed;
  opacity: 1;
}

.audit-leadtime-item {
  gap: 8px;
}

.audit-stage-times {
  display: grid;
  gap: 6px;
}

.audit-stage-time-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 9px;
  border: 1px solid #e2e7ee;
  border-radius: 8px;
  background: #fff;
}

.audit-stage-time-row.current {
  border-color: #b9c8da;
  background: #f2f6fa;
}

.audit-stage-time-row > div {
  display: grid;
  min-width: 0;
  gap: 1px;
}

.audit-stage-time-row strong {
  overflow: hidden;
  color: #40546d;
  font-size: 9.5px;
  font-weight: 750;
  line-height: 1.3;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-stage-time-row small {
  color: #7890ae;
  font-size: 8px;
  font-weight: 700;
}

.audit-stage-time-row b {
  flex: 0 0 auto;
  color: #304f7e;
  font-size: 10px;
  font-weight: 800;
}

.audit-leadtime-item > small {
  color: #8a97a8;
  font-size: 9px;
  line-height: 1.4;
}

/* ATUALIZAÇÕES */

.audit-detail-updates {

  min-width: 0;

  overflow-y: auto;

  background: #fff;

}

.audit-updates-tabs {

  position: sticky;

  top: 0;

  z-index: 2;

  display: flex;

  gap: 6px;

  padding: 0 24px;

  border-bottom: 1px solid #e5eaf0;

  background: #fff;

}

.audit-updates-tabs button {

  position: relative;

  padding: 18px 10px 14px;

  border: 0;

  background: transparent;

  color: #8491a3;

  font-size: 11px;

  font-weight: 700;

  cursor: pointer;

}

.audit-updates-tabs button:hover {

  color: #435a78;

}

.audit-updates-tabs button.active {

  color: #304f7e;

}

.audit-updates-tabs button.active::after {

  position: absolute;

  right: 8px;

  bottom: -1px;

  left: 8px;

  height: 2px;

  border-radius: 2px;

  background: #304f7e;

  content: "";

}

.audit-update-body {

  padding-bottom: 40px;

}

/* NOVA ATUALIZAÇÃO */

.audit-update-composer {

  margin: 22px 24px;

  overflow: hidden;

  border: 1px solid #dce3ec;

  border-radius: 11px;

  background: #fff;

  box-shadow: 0 3px 12px rgba(31, 48, 70, 0.04);

}

.audit-update-composer:focus-within {

  border-color: #9eb0c7;

  box-shadow: 0 0 0 3px rgba(48, 79, 126, 0.07);

}

.audit-update-composer textarea {

  display: block;

  box-sizing: border-box;

  width: 100%;

  min-height: 115px;

  resize: vertical;

  padding: 15px 16px;

  border: 0;

  outline: 0;

  background: #fff;

  color: #263a53;

  font: inherit;

  font-size: 12px;

  line-height: 1.6;

}

.audit-update-composer textarea::placeholder {

  color: #9aa6b5;

}

.audit-update-actions {

  display: flex;

  align-items: center;

  gap: 5px;

  padding: 9px 10px;

  border-top: 1px solid #edf0f4;

  background: #fafbfd;

}

.audit-text-action {

  padding: 7px 8px;

  border: 0;

  border-radius: 6px;

  background: transparent;

  color: #6f7f93;

  font-size: 10px;

  font-weight: 650;

  cursor: pointer;

}

.audit-text-action:hover {

  background: #eef2f7;

  color: #304f7e;

}

.audit-publish-button {

  margin-left: auto;

  padding: 8px 16px;

  border: 0;

  border-radius: 7px;

  background: #304f7e;

  color: #fff;

  font-size: 10px;

  font-weight: 750;

  cursor: pointer;

}

.audit-publish-button:hover {

  background: #263f65;

}

/* TIMELINE */

.audit-timeline {

  padding: 0 24px 40px;

}

.audit-empty-updates {

  display: grid;

  max-width: 420px;

  justify-items: center;

  gap: 7px;

  margin: 60px auto 0;

  padding: 30px;

  color: #8491a3;

  text-align: center;

}

.audit-empty-icon {

  display: grid;

  width: 44px;

  height: 44px;

  margin-bottom: 5px;

  place-items: center;

  border-radius: 50%;

  background: #eef2f7;

  color: #607794;

  font-size: 18px;

}

.audit-empty-updates strong {

  color: #43566f;

  font-size: 12px;

}

.audit-empty-updates p {

  max-width: 330px;

  margin: 0;

  color: #8a97a8;

  font-size: 10.5px;

  line-height: 1.6;

}


.audit-tab-count {
  display: inline-flex;
  min-width: 17px;
  height: 17px;
  align-items: center;
  justify-content: center;
  margin-left: 4px;
  padding: 0 5px;
  border-radius: 999px;
  background: #edf2f8;
  color: #304f7e;
  font-size: 8px;
  font-weight: 800;
}

.audit-file-input {
  display: none;
}

.audit-pending-files {
  display: grid;
  gap: 7px;
  padding: 0 12px 10px;
  background: #fff;
}

.audit-pending-file {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 10px;
  border: 1px solid #e2e7ee;
  border-radius: 8px;
  background: #f8fafc;
}

.audit-pending-file > div {
  display: grid;
  min-width: 0;
  flex: 1;
  gap: 2px;
}

.audit-pending-file strong {
  overflow: hidden;
  color: #324761;
  font-size: 10.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-pending-file span {
  color: #8a97a8;
  font-size: 9px;
}

.audit-pending-file > button {
  width: 26px;
  height: 26px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #8491a3;
  font-size: 18px;
  cursor: pointer;
}

.audit-pending-file > button:hover {
  background: #eef2f7;
  color: #304f7e;
}

.audit-file-icon {
  flex: 0 0 auto;
}

.audit-update-item-header {
  margin-bottom: 9px;
}

.audit-update-item-header strong,
.audit-update-item-header span {
  display: block;
}

.audit-update-item-header span {
  flex: 0 0 auto;
}

.audit-update-attachments {
  display: grid;
  gap: 6px;
  margin-top: 10px;
}

.audit-update-attachment {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 9px;
  border: 1px solid #e4e9ef;
  border-radius: 8px;
  background: #f8fafc;
}

.audit-update-attachment > div {
  display: grid;
  min-width: 0;
  gap: 1px;
}

.audit-update-attachment strong {
  overflow: hidden;
  color: #40546d;
  font-size: 10.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-update-attachment small {
  color: #8a97a8;
  font-size: 9px;
}

.audit-files-list {
  display: grid;
  gap: 9px;
  padding: 22px 24px;
}

.audit-file-card {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 12px 13px;
  border: 1px solid #e1e7ef;
  border-radius: 10px;
  background: #fff;
}

.audit-file-card-icon {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  place-items: center;
  border-radius: 8px;
  background: #eef2f7;
}

.audit-file-card > div {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.audit-file-card strong {
  overflow: hidden;
  color: #31465f;
  font-size: 11.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-file-card span {
  color: #8a97a8;
  font-size: 9.5px;
}


.audit-update-author {
  display: grid;
  gap: 2px;
}

.audit-update-item-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.audit-update-item-actions button {
  padding: 5px 8px;
  border: 0;
  border-radius: 6px;
  background: #eef2f7;
  color: #53657d;
  font-size: 9.5px;
  font-weight: 700;
  cursor: pointer;
}

.audit-update-item-actions button:hover {
  background: #e2e8f0;
  color: #304f7e;
}

.audit-update-item-actions button.danger {
  background: #fff1f1;
  color: #b84b52;
}

.audit-update-item-actions button.danger:hover {
  background: #fde5e5;
}

.audit-edit-textarea {
  box-sizing: border-box;
  width: 100%;
  min-height: 90px;
  resize: vertical;
  padding: 10px 11px;
  border: 1px solid #dce3ec;
  border-radius: 8px;
  outline: 0;
  background: #fff;
  color: #263a53;
  font: inherit;
  font-size: 12px;
  line-height: 1.5;
}

.audit-edit-textarea:focus {
  border-color: #9eb0c7;
  box-shadow: 0 0 0 3px rgba(48, 79, 126, 0.07);
}

.audit-edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 7px;
  margin-top: 8px;
}


.audit-update-attachment {
  display: flex;
  width: 100%;
  align-items: center;
  gap: 8px;
  overflow: hidden;
  padding: 0;
  border: 1px solid #e4e9ef;
  border-radius: 9px;
  background: #f8fafc;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.audit-update-attachment:hover {
  border-color: #c7d2df;
  background: #f3f6fa;
}

.audit-update-image {
  display: block;
  width: 100%;
  max-height: 320px;
  object-fit: contain;
  background: #eef2f6;
}

.audit-update-file-icon {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  margin: 7px 0 7px 8px;
  border-radius: 7px;
  background: #eef2f7;
}

.audit-update-attachment > div {
  display: grid;
  min-width: 0;
  gap: 2px;
  padding: 8px 10px 8px 0;
}

.audit-update-attachment strong {
  overflow: hidden;
  color: #40546d;
  font-size: 10.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-update-attachment small {
  color: #8a97a8;
  font-size: 9px;
}

.audit-file-card {
  width: 100%;
  border: 1px solid #e1e7ef;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.audit-file-card:hover {
  border-color: #c7d2df;
  background: #f8fafc;
}

.audit-file-card-preview {
  width: 64px;
  height: 52px;
  flex: 0 0 64px;
  border-radius: 7px;
  object-fit: cover;
  background: #eef2f6;
}


.audit-toolbar-advanced {
  grid-template-columns: repeat(5, minmax(150px, 1fr)) minmax(280px, 1.5fr);
}

.audit-toolbar-actions {
  display: flex;
  grid-column: 1 / -1;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 2px;
}

.audit-toolbar-actions .btn.active {
  border-color: #9fb1c8;
  background: #edf3f8;
  color: #304f7e;
}

.audit-action-count {
  display: inline-flex;
  min-width: 18px;
  height: 18px;
  align-items: center;
  justify-content: center;
  margin-left: 4px;
  padding: 0 5px;
  border-radius: 999px;
  background: #304f7e;
  color: #fff;
  font-size: 8px;
}

.audit-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(130px, 1fr)) minmax(260px, 1.4fr);
  gap: 10px;
}

.audit-kpi,
.audit-kpi-note {
  padding: 13px 14px;
  border: 1px solid #e0e6ee;
  border-radius: 11px;
  background: #fff;
  box-shadow: 0 5px 18px rgb(35 55 80 / 4%);
}

.audit-kpi {
  display: grid;
  gap: 4px;
}

.audit-kpi span {
  color: #8491a3;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: .04em;
  text-transform: uppercase;
}

.audit-kpi strong {
  color: #2b3e58;
  font-size: 20px;
  font-weight: 800;
}

.audit-kpi.danger {
  border-color: #f0c8c8;
  background: #fff8f8;
}

.audit-kpi.danger strong {
  color: #b84b52;
}

.audit-kpi-note {
  display: flex;
  align-items: center;
  color: #66758a;
  font-size: 10.5px;
  line-height: 1.5;
}

.audit-contract-card.is-bottleneck-warning {
  border-color: #e8d7a7;
}

.audit-contract-card.is-bottleneck-critical {
  border-color: #e5b3b3;
  box-shadow: 0 4px 14px rgb(184 75 82 / 8%);
}

.audit-contract-card.is-compact .audit-card-main {
  gap: 6px;
  padding: 9px 10px;
}

.audit-contract-card.is-compact .audit-card-meta:nth-of-type(n + 2) {
  display: none;
}

.audit-contract-card.is-compact .audit-card-quickmeta {
  display: none;
}

.audit-card-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.audit-stage-age {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 4px 7px;
  border-radius: 999px;
  background: #f3f5f8;
  color: #6c7b90;
  font-size: 8.5px;
  font-weight: 800;
}

.audit-stage-age {
  background: #f3f5f8;
  color: #6c7b90;
}

.audit-stage-age.level-warning {
  background: #fff6df;
  color: #977026;
}

.audit-stage-age.level-critical {
  background: #fff0f0;
  color: #b84b52;
}

.audit-detail-select {
  width: 100%;
  height: 38px;
  padding: 0 9px;
  border: 1px solid #dce3ec;
  border-radius: 8px;
  background: #fff;
  color: #34465f;
  font-size: 11px;
}

.audit-mention-picker {
  display: grid;
  gap: 4px;
  max-height: 230px;
  overflow-y: auto;
  padding: 10px;
  border-top: 1px solid #edf0f4;
  background: #f8fafc;
}

.audit-mention-picker > input {
  height: 34px;
  margin-bottom: 4px;
  padding: 0 10px;
  border: 1px solid #dce3ec;
  border-radius: 7px;
  background: #fff;
  font-size: 10.5px;
}

.audit-mention-picker > button {
  display: grid;
  gap: 2px;
  padding: 8px 9px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.audit-mention-picker > button:hover {
  background: #edf2f7;
}

.audit-mention-picker strong {
  color: #31465f;
  font-size: 10.5px;
}

.audit-mention-picker span,
.audit-mention-picker p {
  color: #8793a4;
  font-size: 9px;
}

.audit-activity-list {
  display: grid;
  gap: 0;
  padding: 22px 24px;
}

.audit-activity-item {
  display: grid;
  grid-template-columns: 12px minmax(0, 1fr);
  gap: 9px;
  padding: 0 0 18px;
}

.audit-activity-dot {
  width: 8px;
  height: 8px;
  margin-top: 5px;
  border: 2px solid #fff;
  border-radius: 50%;
  background: #5b7fb2;
  box-shadow: 0 0 0 1px #b9c8da;
}

.audit-activity-item p {
  margin: 0;
  color: #52657f;
  font-size: 11px;
  line-height: 1.5;
}

.audit-activity-item p strong {
  color: #2f435c;
}

.audit-activity-item small {
  display: block;
  margin-top: 3px;
  color: #95a0af;
  font-size: 9px;
}

.audit-users-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(20, 32, 50, .42);
  backdrop-filter: blur(2px);
}

.audit-users-modal {
  width: min(760px, 95vw);
  max-height: 88vh;
  overflow-y: auto;
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 24px 70px rgba(25, 42, 64, .24);
}

.audit-users-modal > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-bottom: 1px solid #e5eaf0;
}

.audit-users-modal > header span {
  color: #8290a3;
  font-size: 9px;
  font-weight: 800;
  text-transform: uppercase;
}

.audit-users-modal > header h3 {
  margin: 3px 0 0;
  color: #253a53;
  font-size: 17px;
}

.audit-users-modal > header > button {
  width: 34px;
  height: 34px;
  border: 1px solid #dde4ec;
  border-radius: 8px;
  background: #fff;
  color: #66758a;
  font-size: 20px;
  cursor: pointer;
}

.audit-users-current,
.audit-user-form,
.audit-users-list,
.audit-local-warning {
  margin: 16px 20px;
}

.audit-users-current label {
  display: grid;
  gap: 6px;
}

.audit-users-current label span {
  color: #708096;
  font-size: 9px;
  font-weight: 800;
  text-transform: uppercase;
}

.audit-users-current select,
.audit-user-form input {
  height: 38px;
  padding: 0 10px;
  border: 1px solid #dce3ec;
  border-radius: 8px;
  background: #fff;
  color: #34465f;
  font-size: 11px;
}

.audit-user-form {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 14px;
  border-radius: 10px;
  background: #f8fafc;
}

.audit-user-form .btn {
  grid-column: 1 / -1;
  justify-self: end;
}

.audit-users-list {
  display: grid;
  gap: 8px;
}

.audit-users-list article {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 10px 11px;
  border: 1px solid #e3e8ef;
  border-radius: 9px;
}

.audit-user-avatar {
  display: grid;
  width: 38px;
  height: 38px;
  place-items: center;
  border-radius: 10px;
  background: #edf2f8;
  color: #304f7e;
  font-size: 10px;
  font-weight: 800;
}

.audit-users-list article > div:nth-child(2) {
  display: grid;
  min-width: 0;
  gap: 2px;
}

.audit-users-list strong {
  color: #31465f;
  font-size: 11px;
}

.audit-users-list span,
.audit-users-list small {
  overflow: hidden;
  color: #8793a4;
  font-size: 9px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-local-warning {
  padding: 10px 12px;
  border-radius: 8px;
  background: #fff7e7;
  color: #866526;
  font-size: 9.5px;
  line-height: 1.5;
}



.audit-flow-overview {
  overflow: hidden;
  padding: 0;
}

.audit-flow-overview-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 15px 9px;
}

.audit-flow-overview-head > div:first-child {
  display: grid;
  gap: 2px;
}

.audit-flow-overview-head > div:first-child > span {
  color: #8794a6;
  font-size: 7.8px;
  font-weight: 850;
  letter-spacing: .055em;
  text-transform: uppercase;
}

.audit-flow-overview-head > div:first-child > strong {
  color: #2d435d;
  font-size: 12px;
  font-weight: 850;
}

.audit-flow-total {
  display: flex;
  align-items: baseline;
  gap: 5px;
}

.audit-flow-total strong {
  color: #31578a;
  font-size: 17px;
  font-weight: 900;
}

.audit-flow-total span {
  color: #8a97a8;
  font-size: 8.5px;
  font-weight: 700;
}

.audit-flow-segments {
  display: flex;
  width: calc(100% - 30px);
  min-height: 22px;
  margin: 0 15px;
  overflow: hidden;
  border-radius: 7px;
  background: #edf1f5;
  box-shadow: inset 0 0 0 1px rgb(40 62 88 / 4%);
}

.audit-flow-segment {
  display: grid;
  min-width: 7px;
  height: 22px;
  place-items: center;
  border: 0;
  border-right: 2px solid #fff;
  color: #fff;
  font-size: 8.5px;
  font-weight: 900;
  line-height: 1;
  cursor: pointer;
  transition:
    filter .15s ease,
    opacity .15s ease;
}

.audit-flow-segment:last-of-type {
  border-right: 0;
}

.audit-flow-segment:hover {
  filter: brightness(.92);
}

.audit-flow-empty {
  display: grid;
  width: 100%;
  min-height: 22px;
  place-items: center;
  color: #8a97a8;
  font-size: 8.5px;
}

.audit-flow-legend {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 0;
  margin-top: 9px;
  border-top: 1px solid #edf1f5;
}

.audit-flow-legend-item {
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto;
  grid-template-rows: auto auto;
  align-items: center;
  column-gap: 6px;
  row-gap: 1px;
  min-width: 0;
  padding: 8px 10px 9px;
  border: 0;
  border-left: 1px solid #edf1f5;
  background: #fff;
  text-align: left;
  cursor: pointer;
  transition: background .15s ease;
}

.audit-flow-legend-item:first-child {
  border-left: 0;
}

.audit-flow-legend-item:hover {
  background: #f8fafc;
}

.audit-flow-legend-item.empty {
  opacity: .55;
}

.audit-flow-dot {
  grid-row: 1 / 3;
  width: 7px;
  height: 7px;
  border-radius: 50%;
}

.audit-flow-legend-label {
  overflow: hidden;
  color: #52667f;
  font-size: 8px;
  font-weight: 750;
  line-height: 1.25;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-flow-legend-item strong {
  grid-column: 3;
  grid-row: 1 / 3;
  color: #30465f;
  font-size: 10px;
  font-weight: 900;
}

.audit-flow-legend-item small {
  grid-column: 2;
  color: #9aa5b3;
  font-size: 7.2px;
}

.audit-filter-row-simple {
  grid-template-columns: minmax(135px, 190px) minmax(180px, 230px) minmax(360px, 1fr);
}

.audit-overview-strip-compact {
  grid-template-columns: minmax(300px, 2fr) minmax(140px, .65fr) minmax(140px, .65fr);
}

.audit-overview-strip-compact .audit-overview-main {
  padding-left: 16px;
}



.audit-all-contracts-note {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-top: -4px;
  color: #7f8da0;
  font-size: 8.5px;
}

.audit-all-contracts-note strong {
  color: #52677f;
  font-weight: 800;
}

/* REFINOS DE USABILIDADE */

.audit-toolbar-refined {
  padding: 12px 14px;
}

.audit-toolbar-bottom {
  padding-top: 8px;
}

.audit-toolbar-actions .btn {
  min-height: 34px;
}

.btn-subtle {
  border-color: transparent !important;
  background: #f7f9fb !important;
  color: #607188 !important;
  box-shadow: none !important;
}

.btn-subtle:hover {
  border-color: #dbe3ec !important;
  background: #f0f4f8 !important;
}

.audit-card-quickmeta {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 5px;
  margin-top: 2px;
  color: #8794a6;
  font-size: 8.4px;
  font-weight: 650;
  line-height: 1.25;
}

.audit-card-quickmeta span:first-child,
.audit-card-quickmeta span:last-child {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.audit-stage-age.level-normal {
  background: #f1f4f7;
  color: #65758a;
}

.audit-stage-age.level-warning {
  background: #fff4d6;
  color: #8f6a19;
}

.audit-stage-age.level-critical {
  background: #ffeded;
  color: #af4850;
}

.audit-board {
  scroll-snap-type: x proximity;
  scroll-behavior: smooth;
}

.audit-column {
  scroll-snap-align: start;
}

.audit-column-header {
  position: sticky;
  top: 0;
  z-index: 3;
  box-shadow: 0 1px 0 #e7edf3;
}

.audit-column-body {
  scrollbar-width: thin;
}

.audit-flow-segment {
  position: relative;
  overflow: visible;
}

.audit-flow-segment::after {
  content: attr(data-count);
  position: absolute;
  top: 50%;
  right: -8px;
  display: grid;
  min-width: 16px;
  height: 16px;
  place-items: center;
  padding: 0 3px;
  transform: translate(50%, -50%);
  border: 2px solid #fff;
  border-radius: 999px;
  background: #fff;
  color: #52667f;
  box-shadow: 0 1px 5px rgb(35 55 80 / 15%);
  font-size: 7.5px;
  font-weight: 900;
  pointer-events: none;
}

.audit-flow-segment[data-count=""]::after {
  display: none;
}


/* AUDITORIA REFINADA */

.audit-toolbar-refined {
  display: grid;
  gap: 12px;
  padding: 14px 16px;
}

.audit-filter-row {
  display: grid;
  grid-template-columns: minmax(150px, .85fr) minmax(170px, 1fr) minmax(160px, .9fr) minmax(340px, 1.8fr);
  gap: 10px;
  align-items: end;
}

.audit-filter-row > label {
  min-width: 0;
}

.audit-filter-row > label > span {
  display: block;
  margin-bottom: 6px;
  color: #64758b;
  font-size: 8.5px;
  font-weight: 800;
  letter-spacing: .055em;
  text-transform: uppercase;
}

.audit-filter-row select,
.audit-filter-row input {
  height: 38px;
}

.audit-toolbar-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-top: 10px;
  border-top: 1px solid #edf1f5;
}

.audit-toolbar-hint {
  display: flex;
  align-items: center;
  gap: 7px;
  color: #718096;
  font-size: 9.5px;
}

.audit-live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #55a26f;
  box-shadow: 0 0 0 3px rgba(85, 162, 111, .12);
}

.audit-toolbar-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 7px;
  padding: 0;
}

.btn-primary-soft {
  border-color: #c4d2e3 !important;
  background: #edf3fa !important;
  color: #2f5687 !important;
}

.audit-overview-strip {
  display: grid;
  grid-template-columns: minmax(260px, 1.5fr) minmax(130px, .65fr) minmax(130px, .65fr) minmax(260px, 1.2fr);
  align-items: center;
  gap: 0;
  overflow: hidden;
  border: 1px solid #e1e7ee;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 5px 18px rgb(35 55 80 / 4%);
}

.audit-overview-main,
.audit-overview-stat,
.audit-overview-tip {
  min-height: 72px;
  padding: 12px 15px;
}

.audit-overview-main {
  display: flex;
  align-items: center;
  gap: 11px;
}

.audit-overview-icon {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  border-radius: 10px;
  background: #edf3fa;
  color: #2f5687;
}

.audit-overview-icon span {
  font-size: 12px;
  font-weight: 850;
}

.audit-overview-main > div:last-child {
  display: grid;
  gap: 3px;
}

.audit-overview-main strong {
  color: #2e435d;
  font-size: 11px;
  font-weight: 800;
}

.audit-overview-main small {
  color: #8794a6;
  font-size: 9px;
}

.audit-overview-stat {
  display: grid;
  align-content: center;
  gap: 4px;
  border-left: 1px solid #edf1f5;
}

.audit-overview-stat span {
  color: #8995a6;
  font-size: 8.5px;
  font-weight: 800;
  letter-spacing: .035em;
  text-transform: uppercase;
}

.audit-overview-stat strong {
  color: #31465f;
  font-size: 18px;
  font-weight: 850;
}

.audit-overview-stat strong.danger {
  color: #b84b52;
}

.audit-overview-tip {
  display: flex;
  align-items: center;
  border-left: 1px solid #edf1f5;
  background: #fafbfd;
  color: #718096;
  font-size: 9.5px;
  line-height: 1.5;
}

.audit-card-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-top: 1px;
}

.audit-contract-card {
  transition:
    border-color .15s ease,
    box-shadow .15s ease,
    transform .15s ease;
}

.audit-contract-card:hover {
  transform: translateY(-1px);
  border-color: #c7d4e3;
  box-shadow: 0 8px 20px rgb(37 57 83 / 7%);
}

.audit-column {
  border-color: #e0e6ed;
  background: #f8fafc;
}

.audit-column-body {
  background:
    linear-gradient(#f8fafc, #f8fafc) padding-box,
    linear-gradient(to bottom, rgba(225, 232, 240, .35), rgba(225, 232, 240, 0)) border-box;
}

.audit-column-header {
  background: #fff;
}

.audit-detail-select {
  display: none;
}



@media (max-width: 1100px) {
  .audit-flow-legend {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .audit-flow-legend-item:nth-child(5) {
    border-left: 0;
  }
}

@media (max-width: 700px) {
  .audit-flow-overview-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .audit-flow-legend {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .audit-flow-legend-item:nth-child(odd) {
    border-left: 0;
  }
}


.audit-stage-age.level-not-started {
  background: #eef2f6;
  color: #65758a;
}

.audit-stage-age.level-finalized {
  background: #edf6eb;
  color: #557a49;
}

.audit-column-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 9px;
  border-top: 1px solid #e7edf3;
  background: #fff;
  color: #8491a3;
  font-size: 8px;
}

.audit-column-pagination > div {
  display: flex;
  gap: 5px;
}

.audit-column-pagination button {
  min-height: 27px;
  padding: 0 7px;
  border: 1px solid #dce4ed;
  border-radius: 6px;
  background: #fff;
  color: #52677f;
  font-size: 8px;
  font-weight: 750;
  cursor: pointer;
}

.audit-column-pagination button:hover {
  border-color: #bac9da;
  background: #f5f8fb;
}

.audit-not-started-info {
  gap: 5px;
}

.audit-not-started-info > strong {
  color: #52677f;
  font-size: 10.5px;
}

.audit-not-started-info > small {
  color: #8a97a8;
  font-size: 9px;
  line-height: 1.45;
}

.audit-empty-summary {
  display: grid;
  width: min(560px, 100%);
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 7px;
  margin-top: 15px;
}

.audit-empty-summary > div {
  display: grid;
  gap: 3px;
  padding: 9px 10px;
  border: 1px solid #e3e9f0;
  border-radius: 8px;
  background: #fafbfd;
  text-align: left;
}

.audit-empty-summary span {
  color: #8c98a8;
  font-size: 7.8px;
  font-weight: 800;
  letter-spacing: .03em;
  text-transform: uppercase;
}

.audit-empty-summary strong {
  overflow: hidden;
  color: #435970;
  font-size: 9px;
  font-weight: 800;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 760px) {
  .audit-empty-summary {
    grid-template-columns: 1fr;
  }
}

/* RESPONSIVIDADE */

@media (max-width: 900px) {

  .audit-toolbar {

    grid-template-columns: 1fr;

  }

  .audit-toolbar-summary {

    justify-content: space-between;

    white-space: normal;

  }

  .audit-column {

    width: 260px;

    min-width: 260px;

  }

  .audit-detail-panel {

    width: 95vw;

  }

  .audit-detail-content {

    grid-template-columns: 275px minmax(0, 1fr);

  }

}

@media (max-width: 700px) {

  .audit-summary {

    align-items: flex-start;

    flex-direction: column;

  }

  .audit-column {

    width: 238px;

    min-width: 238px;

    height: 62vh;

  }

  .audit-detail-panel {

    width: 100vw;

  }

  .audit-detail-content {

    display: block;

    overflow-y: auto;

  }

  .audit-detail-info {

    border-right: 0;

    border-bottom: 1px solid #e2e7ee;

  }

  .audit-detail-updates {

    overflow: visible;

  }

}

</style>
