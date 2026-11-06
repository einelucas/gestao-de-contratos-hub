import type { Contract, ContractAlert } from "~/types/api";

export type StatusFilter = "Todos" | "Regularizacao" | "Vencido" | "Atencao" | "Regular" | "Finalizado";
export type SortMode = "Status e vencimento" | "Vencimento mais próximo";
export type ValueCompositionFilter = "Todos" | "MaterialProprio" | "MaterialTerceiros" | "SomenteServicos";

export const VALUE_COMPOSITION_OPTIONS: Array<{ value: ValueCompositionFilter; label: string }> = [
  { value: "Todos", label: "Todos" },
  { value: "MaterialProprio", label: "Com material próprio" },
  { value: "MaterialTerceiros", label: "Com material de terceiros" },
  { value: "SomenteServicos", label: "Somente serviços" },
];

/** Valores vêm da API como string (Decimal) ou número; normaliza para comparação. */
function numeric(value: string | number | null | undefined): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

/**
 * Filtro por composição do valor do contrato:
 * - MaterialProprio: possui material próprio (pode ter também serviço/terceiros);
 * - MaterialTerceiros: possui material de terceiros (pode ter também os demais);
 * - SomenteServicos: não possui material próprio nem de terceiros e tem serviço.
 */
export function matchesValueComposition(
  contract: Pick<Contract, "serviceValue" | "ownMaterialValue" | "thirdPartyMaterialValue">,
  filter: ValueCompositionFilter,
): boolean {
  if (filter === "Todos") return true;
  const service = numeric(contract.serviceValue);
  const own = numeric(contract.ownMaterialValue);
  const thirdParty = numeric(contract.thirdPartyMaterialValue);
  if (filter === "MaterialProprio") return own > 0;
  if (filter === "MaterialTerceiros") return thirdParty > 0;
  return own === 0 && thirdParty === 0 && service > 0;
}

/**
 * Unidades padronizadas do cadastro de contratos. O formulário usa esta lista
 * como seletor para impedir variações de grafia (ex.: "RIO VERDE" × "Rio Verde").
 */
export const CONTRACT_UNITS = [
  "Balsas",
  "Dourados",
  "LEM",
  "Nova Mutum",
  "Rio Verde",
  "Rondonópolis",
] as const;

export function money(value: string | number): string {
  return Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

/** Formata um valor para o campo de moeda (sem o símbolo, que fica no prefixo). */
export function formatCurrencyInput(value: number): string {
  return Number(value || 0).toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/**
 * Converte o texto digitado no campo de moeda em número.
 * Aceita "1.234,56", "1234,56", "1234.56" e "1234".
 */
export function parseCurrencyInput(value: string): number {
  const cleaned = value.replace(/[^\d,.-]/g, "").trim();
  if (!cleaned) return 0;
  let normalized: string;
  if (cleaned.includes(",")) {
    normalized = cleaned.replace(/\./g, "").replace(",", ".");
  } else {
    const parts = cleaned.split(".");
    const last = parts[parts.length - 1] ?? "";
    normalized = parts.length > 1 && last.length <= 2 ? `${parts.slice(0, -1).join("")}.${last}` : cleaned.replace(/\./g, "");
  }
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? Math.max(0, parsed) : 0;
}

export function dateBr(value: string | null): string {
  if (!value) return "Não informada";
  const [year, month, day] = value.split("-");
  return `${day}/${month}/${year}`;
}

export function statusLabel(alert: ContractAlert): string {
  return alert === "Regularizacao" ? "Em regularização" : alert === "Atencao" ? "Atenção" : alert === "SemData" ? "Sem data" : alert;
}

/** Mesma redação do sino (`attention_message` no backend) — nunca mostra "0 dias"/"faltam 0 d". */
export function daysToEndLabel(days: number | null): string {
  if (days === null) return "—";
  if (days === 0) return "Vence hoje";
  if (days === 1) return "Vence amanhã";
  if (days > 1) return `Vence em ${days} dias`;
  if (days === -1) return "Vencido há 1 dia";
  return `Vencido há ${-days} dias`;
}

/** Dias em atraso de um contrato em aberto; `null` quando não está vencido (ou já foi finalizado). */
export function overdueDays(
  contract: Pick<Contract, "daysToEnd" | "finalized"> & { effectiveFinalized?: boolean },
): number | null {
  if (contract.effectiveFinalized || contract.finalized || contract.daysToEnd === null || contract.daysToEnd >= 0) return null;
  return -contract.daysToEnd;
}

export function overdueLabel(days: number): string {
  return days === 1 ? "1 dia em atraso" : `${days} dias em atraso`;
}

const rank: Record<ContractAlert, number> = { Regularizacao: 2, Vencido: 1, Atencao: 2, SemData: 3, Regular: 4, Finalizado: 5 };
export function sortContracts(items: Contract[], mode: SortMode): Contract[] {
  return [...items].sort((a, b) => {
    const aEnd = a.effectiveEndDate ?? a.endDate;
    const bEnd = b.effectiveEndDate ?? b.endDate;
    const da = aEnd ? new Date(`${aEnd}T00:00:00`).getTime() : Number.MAX_SAFE_INTEGER;
    const db = bEnd ? new Date(`${bEnd}T00:00:00`).getTime() : Number.MAX_SAFE_INTEGER;
    if (mode === "Vencimento mais próximo") return da - db || a.supplier.localeCompare(b.supplier, "pt-BR");
    return rank[a.alert] - rank[b.alert] || da - db || a.supplier.localeCompare(b.supplier, "pt-BR");
  });
}

/** Situação da consulta de equipes de um setor no formulário de contrato. */
export type TeamsLoadStatus = "loading" | "loaded" | "error";

/**
 * Validação de equipe no formulário. Só acusa "equipe de outro setor" quando a
 * lista do setor foi CARREGADA e a equipe não está nela — se a consulta falhou
 * ou ainda está em andamento, não bloqueia: o backend valida ao salvar.
 */
export function contractTeamProblem(input: {
  teamId: string;
  notify: boolean;
  teamsStatus: TeamsLoadStatus | undefined;
  teamFound: boolean;
  teamWarning: string;
}): string {
  const loaded = input.teamsStatus === "loaded";
  if (input.teamId && loaded && !input.teamFound) return "A equipe selecionada não pertence ao setor do contrato.";
  if (input.notify) {
    if (!input.teamId) return "Para ativar os alertas, selecione a equipe de notificação do setor.";
    if (input.teamWarning) return `${input.teamWarning} Ajuste a equipe antes de ativar os alertas.`;
  }
  return "";
}
