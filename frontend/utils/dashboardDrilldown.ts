import type { AuditStage, Contract, ContractAlert, DeadlineBucket } from "~/types/api";

function effectiveEndDate(item: Contract): string | null {
  return item.effectiveEndDate ?? item.endDate;
}

function isEffectivelyFinalized(item: Contract): boolean {
  return item.effectiveFinalized || item.finalized;
}

/** Mesmas etapas de `REGULARIZATION_AUDIT_STAGES` em `backend/app/modules/contracts/rules.py`. */
const REGULARIZATION_AUDIT_STAGES: AuditStage[] = [
  "AGUARDANDO_ANALISE",
  "ANALISE_INTERNA_INPASA",
  "FORNECEDOR_CONTATADO",
  "EM_TRATATIVA",
];

/**
 * "Em regularização" no Dashboard é aditivo: inclui a regularização explícita
 * (`alert`) e também contratos em etapa de Auditoria, sem reclassificá-los —
 * eles continuam sendo "Vencido"/"Atenção" nos demais lugares do app.
 */
function isRegularization(item: Contract): boolean {
  if (item.alert === "Regularizacao") return true;
  if (isEffectivelyFinalized(item)) return false;
  return item.auditStage !== null && REGULARIZATION_AUDIT_STAGES.includes(item.auditStage);
}

/**
 * Status exclusivo do contrato, ignorando a sobreposição de regularização —
 * mesma semântica de `_status` no `summary.py` do backend. Assim os status dos
 * gráficos somam o total e "Em regularização" é um recorte à parte.
 */
function alertWithoutRegularization(item: Contract): ContractAlert {
  if (isEffectivelyFinalized(item) || item.situation === "Finalizado") return "Finalizado";
  if (item.situation === "Sem data") return "SemData";
  if (item.situation === "Vencido") return "Vencido";
  if (item.daysToEnd !== null && item.daysToEnd <= 20) return "Atencao";
  return "Regular";
}

function matchesAlert(item: Contract, alert: ContractAlert): boolean {
  return alert === "Regularizacao" ? isRegularization(item) : alertWithoutRegularization(item) === alert;
}

/**
 * Filtros-base do Dashboard (mesma semântica de `build_summary` no backend:
 * `unit` é igualdade exata; `de`/`ate` recortam pelo fim de vigência efetivo e excluem
 * contratos sem data quando algum dos dois está preenchido).
 */
export interface DashboardBaseFilters {
  de?: string | null;
  ate?: string | null;
  unit?: string | null;
}

export function applyDashboardBaseFilters(contracts: Contract[], filters: DashboardBaseFilters): Contract[] {
  let items = contracts;
  if (filters.unit) items = items.filter((item) => item.unit === filters.unit);
  if (filters.de || filters.ate) {
    items = items.filter((item) => {
      const endDate = effectiveEndDate(item);
      return (
        endDate !== null &&
        (!filters.de || endDate >= filters.de) &&
        (!filters.ate || endDate <= filters.ate)
      );
    });
  }
  return items;
}

export function filterByAlert(contracts: Contract[], alert: ContractAlert): Contract[] {
  return contracts.filter((item) => matchesAlert(item, alert));
}

export function filterByUnit(contracts: Contract[], unit: string, alert?: ContractAlert): Contract[] {
  return contracts.filter((item) => item.unit === unit && (!alert || matchesAlert(item, alert)));
}

/** Mesmos limites de `_DEADLINE_BUCKETS` em `backend/app/modules/contracts/summary.py`. */
const DEADLINE_TESTS: Record<DeadlineBucket["key"], (item: Contract) => boolean> = {
  overdue: (item) => !isEffectivelyFinalized(item) && item.daysToEnd !== null && item.daysToEnd < 0,
  today: (item) => !isEffectivelyFinalized(item) && item.daysToEnd === 0,
  next7: (item) => !isEffectivelyFinalized(item) && item.daysToEnd !== null && item.daysToEnd >= 1 && item.daysToEnd <= 7,
  next30: (item) => !isEffectivelyFinalized(item) && item.daysToEnd !== null && item.daysToEnd >= 8 && item.daysToEnd <= 30,
  next60: (item) => !isEffectivelyFinalized(item) && item.daysToEnd !== null && item.daysToEnd >= 31 && item.daysToEnd <= 60,
  next90: (item) => !isEffectivelyFinalized(item) && item.daysToEnd !== null && item.daysToEnd >= 61 && item.daysToEnd <= 90,
  later: (item) => !isEffectivelyFinalized(item) && item.daysToEnd !== null && item.daysToEnd > 90,
  withoutDate: (item) => !isEffectivelyFinalized(item) && item.daysToEnd === null,
};

export function filterByDeadlineBucket(contracts: Contract[], key: DeadlineBucket["key"]): Contract[] {
  return contracts.filter((item) => DEADLINE_TESTS[key](item));
}

/** Recorte de "Em regularização" por status exclusivo (para a composição do card). */
export function filterByRegularizationStatus(contracts: Contract[], alert: ContractAlert): Contract[] {
  return contracts.filter((item) => isRegularization(item) && alertWithoutRegularization(item) === alert);
}

export type MonthSegment = "regularization" | "upcoming" | "overdue" | "finalized";

/** `month` no formato `AAAA-MM`. */
export function filterByMonth(contracts: Contract[], month: string, segment?: MonthSegment): Contract[] {
  const inMonth = contracts.filter((item) => {
    const endDate = effectiveEndDate(item);
    return endDate !== null && endDate.slice(0, 7) === month;
  });
  if (!segment) return inMonth;
  if (segment === "finalized") return inMonth.filter((item) => isEffectivelyFinalized(item));
  const active = inMonth.filter((item) => !isEffectivelyFinalized(item));
  if (segment === "regularization") return active.filter((item) => isRegularization(item));
  if (segment === "overdue") return active.filter((item) => alertWithoutRegularization(item) === "Vencido");
  return active.filter((item) => alertWithoutRegularization(item) === "Regular" || alertWithoutRegularization(item) === "Atencao");
}
