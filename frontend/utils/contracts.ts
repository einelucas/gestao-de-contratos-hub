import type { Contract, ContractAlert } from "~/types/api";

export type StatusFilter = "Todos" | "Regularizacao" | "Vencido" | "Atencao" | "Regular" | "Finalizado";
export type SortMode = "Status e vencimento" | "Vencimento mais próximo";

export function money(value: string | number): string {
  return Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
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

const rank: Record<ContractAlert, number> = { Regularizacao: 2, Vencido: 1, Atencao: 2, SemData: 3, Regular: 4, Finalizado: 5 };
export function sortContracts(items: Contract[], mode: SortMode): Contract[] {
  return [...items].sort((a, b) => {
    const da = a.endDate ? new Date(`${a.endDate}T00:00:00`).getTime() : Number.MAX_SAFE_INTEGER;
    const db = b.endDate ? new Date(`${b.endDate}T00:00:00`).getTime() : Number.MAX_SAFE_INTEGER;
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
