import { describe, expect, it } from "vitest";
import type { Contract } from "~/types/api";
import {
  applyDashboardBaseFilters,
  filterByAlert,
  filterByDeadlineBucket,
  filterByMonth,
  filterByUnit,
} from "~/utils/dashboardDrilldown";

function makeContract(overrides: Partial<Contract>): Contract {
  return {
    id: overrides.id ?? Math.random().toString(36),
    sectorId: "s1",
    sectorName: "Setor",
    contractNumber: "1",
    supplierId: "f1",
    supplier: "Fornecedor",
    serviceDescription: "",
    serviceValue: 0,
    ownMaterialValue: 0,
    thirdPartyMaterialValue: 0,
    totalValue: 0,
    startDate: null,
    endDate: null,
    unit: "LEM",
    finalized: false,
    auditStage: null,
    situation: "Vigente",
    alert: "Regular",
    daysToEnd: null,
    source: "",
    notify: false,
    notifyEnabledOn: null,
    notificationTeamId: null,
    notificationTeamName: null,
    notificationRecipients: [],
    notificationProblem: null,
    noticeDays: 0,
    responsibleUserId: null,
    responsibleUserName: null,
    responsibleEmail: null,
    autoRenewal: false,
    criticality: null,
    canEdit: true,
    createdAt: "",
    updatedAt: "",
    ...overrides,
  };
}

describe("filterByDeadlineBucket", () => {
  const contracts = [
    makeContract({ id: "overdue", daysToEnd: -3, finalized: false }),
    makeContract({ id: "today", daysToEnd: 0, finalized: false }),
    makeContract({ id: "next7", daysToEnd: 5, finalized: false }),
    makeContract({ id: "next30", daysToEnd: 20, finalized: false }),
    makeContract({ id: "later", daysToEnd: 200, finalized: false }),
    makeContract({ id: "withoutDate", daysToEnd: null, finalized: false }),
    makeContract({ id: "finalizedToday", daysToEnd: 0, finalized: true }),
  ];

  it("vencidos: daysToEnd < 0 e não finalizado", () => {
    expect(filterByDeadlineBucket(contracts, "overdue").map((c) => c.id)).toEqual(["overdue"]);
  });

  it("hoje: exclui finalizados mesmo com daysToEnd 0", () => {
    expect(filterByDeadlineBucket(contracts, "today").map((c) => c.id)).toEqual(["today"]);
  });

  it("sem data: daysToEnd null e não finalizado", () => {
    expect(filterByDeadlineBucket(contracts, "withoutDate").map((c) => c.id)).toEqual(["withoutDate"]);
  });
});

describe("filterByAlert e filterByUnit", () => {
  const contracts = [
    makeContract({ id: "a", alert: "Vencido", unit: "LEM" }),
    makeContract({ id: "b", alert: "Regular", unit: "LEM" }),
    makeContract({ id: "c", alert: "Vencido", unit: "CAMPUS" }),
  ];

  it("filtra por status (alert)", () => {
    expect(filterByAlert(contracts, "Vencido").map((c) => c.id)).toEqual(["a", "c"]);
  });

  it("filtra por unidade + status combinados (clique num segmento empilhado)", () => {
    expect(filterByUnit(contracts, "LEM", "Vencido").map((c) => c.id)).toEqual(["a"]);
  });

  it("filtra só por unidade quando o status não é informado", () => {
    expect(filterByUnit(contracts, "LEM").map((c) => c.id)).toEqual(["a", "b"]);
  });
});

describe("filterByMonth", () => {
  const contracts = [
    makeContract({ id: "upcoming", endDate: "2026-10-15", finalized: false, alert: "Atencao" }),
    makeContract({ id: "overdue", endDate: "2026-10-05", finalized: false, alert: "Vencido" }),
    makeContract({ id: "finalized", endDate: "2026-10-20", finalized: true, alert: "Finalizado" }),
    makeContract({ id: "otherMonth", endDate: "2026-11-01", finalized: false, alert: "Regular" }),
  ];

  it("retorna todos os contratos do mês quando nenhum segmento é informado", () => {
    expect(filterByMonth(contracts, "2026-10").map((c) => c.id).sort()).toEqual(["finalized", "overdue", "upcoming"]);
  });

  it("segmento 'overdue': alert === Vencido", () => {
    expect(filterByMonth(contracts, "2026-10", "overdue").map((c) => c.id)).toEqual(["overdue"]);
  });

  it("segmento 'upcoming': não finalizados fora do segmento overdue", () => {
    expect(filterByMonth(contracts, "2026-10", "upcoming").map((c) => c.id)).toEqual(["upcoming"]);
  });

  it("segmento 'finalized': contratos finalizados do mês", () => {
    expect(filterByMonth(contracts, "2026-10", "finalized").map((c) => c.id)).toEqual(["finalized"]);
  });
});

describe("applyDashboardBaseFilters + drilldown combinados", () => {
  const contracts = [
    makeContract({ id: "inRange", endDate: "2026-10-10", unit: "LEM", alert: "Vencido" }),
    makeContract({ id: "outOfRange", endDate: "2026-12-10", unit: "LEM", alert: "Vencido" }),
    makeContract({ id: "noDate", endDate: null, unit: "LEM", alert: "SemData" }),
    makeContract({ id: "otherUnit", endDate: "2026-10-10", unit: "CAMPUS", alert: "Vencido" }),
  ];

  it("combina filtro-base do Dashboard (unidade + período) com o drilldown de status", () => {
    const base = applyDashboardBaseFilters(contracts, { de: "2026-10-01", ate: "2026-10-31", unit: "LEM" });
    expect(filterByAlert(base, "Vencido").map((c) => c.id)).toEqual(["inRange"]);
  });
});
