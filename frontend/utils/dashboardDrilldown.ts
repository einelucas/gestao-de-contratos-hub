import type { Contract, ContractAlert, DeadlineBucket } from "~/types/api";

/**
 * Filtros-base do Dashboard (mesma semântica de `build_summary` no backend:
 * `unit` é igualdade exata; `de`/`ate` recortam pelo fim de vigência e excluem
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
    items = items.filter(
      (item) =>
        item.endDate !== null &&
        (!filters.de || item.endDate >= filters.de) &&
        (!filters.ate || item.endDate <= filters.ate),
    );
  }
  return items;
}

export function filterByAlert(contracts: Contract[], alert: ContractAlert): Contract[] {
  return contracts.filter((item) => item.alert === alert);
}

export function filterByUnit(contracts: Contract[], unit: string, alert?: ContractAlert): Contract[] {
  return contracts.filter((item) => item.unit === unit && (!alert || item.alert === alert));
}

/** Mesmos limites de `_DEADLINE_BUCKETS` em `backend/app/modules/contracts/summary.py`. */
const DEADLINE_TESTS: Record<DeadlineBucket["key"], (item: Contract) => boolean> = {
  regularization: (item) => item.alert === "Regularizacao",
  overdue: (item) => !item.finalized && item.daysToEnd !== null && item.daysToEnd < 0,
  today: (item) => !item.finalized && item.daysToEnd === 0,
  next7: (item) => !item.finalized && item.daysToEnd !== null && item.daysToEnd >= 1 && item.daysToEnd <= 7,
  next30: (item) => !item.finalized && item.daysToEnd !== null && item.daysToEnd >= 8 && item.daysToEnd <= 30,
  next60: (item) => !item.finalized && item.daysToEnd !== null && item.daysToEnd >= 31 && item.daysToEnd <= 60,
  next90: (item) => !item.finalized && item.daysToEnd !== null && item.daysToEnd >= 61 && item.daysToEnd <= 90,
  later: (item) => !item.finalized && item.daysToEnd !== null && item.daysToEnd > 90,
  withoutDate: (item) => !item.finalized && item.daysToEnd === null,
};

export function filterByDeadlineBucket(contracts: Contract[], key: DeadlineBucket["key"]): Contract[] {
  return contracts.filter(item => key === "regularization" ? item.alert === "Regularizacao" : item.alert !== "Regularizacao" && DEADLINE_TESTS[key](item));
}

export type MonthSegment = "regularization" | "upcoming" | "overdue" | "finalized";

/** `month` no formato `AAAA-MM`. */
export function filterByMonth(contracts: Contract[], month: string, segment?: MonthSegment): Contract[] {
  const inMonth = contracts.filter((item) => item.endDate !== null && item.endDate.slice(0, 7) === month);
  if (!segment) return inMonth;
  if (segment === "finalized") return inMonth.filter((item) => item.finalized);
  const active = inMonth.filter((item) => !item.finalized);
  if (segment === "regularization") return active.filter((item) => item.alert === "Regularizacao");
  if (segment === "overdue") return active.filter((item) => item.alert === "Vencido");
  return active.filter((item) => item.alert !== "Vencido" && item.alert !== "Regularizacao");
}
