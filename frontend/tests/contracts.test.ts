import { describe, expect, it } from "vitest";
import { daysToEndLabel, overdueDays, overdueLabel } from "~/utils/contracts";

describe("daysToEndLabel", () => {
  it("nunca mostra '0 dias' — usa 'Vence hoje'", () => {
    expect(daysToEndLabel(0)).toBe("Vence hoje");
  });
  it("mostra 'Vence amanhã' para 1 dia", () => {
    expect(daysToEndLabel(1)).toBe("Vence amanhã");
  });
  it("mostra dias restantes acima de 1", () => {
    expect(daysToEndLabel(10)).toBe("Vence em 10 dias");
  });
  it("mostra singular para 1 dia de atraso", () => {
    expect(daysToEndLabel(-1)).toBe("Vencido há 1 dia");
  });
  it("mostra plural para mais de 1 dia de atraso", () => {
    expect(daysToEndLabel(-10)).toBe("Vencido há 10 dias");
  });
  it("mostra '—' quando não há data", () => {
    expect(daysToEndLabel(null)).toBe("—");
  });
});

describe("overdueDays", () => {
  it("retorna os dias em atraso de contrato vencido em aberto", () => {
    expect(overdueDays({ daysToEnd: -12, finalized: false })).toBe(12);
  });
  it("ignora contratos não vencidos, sem data ou finalizados", () => {
    expect(overdueDays({ daysToEnd: 0, finalized: false })).toBeNull();
    expect(overdueDays({ daysToEnd: 5, finalized: false })).toBeNull();
    expect(overdueDays({ daysToEnd: null, finalized: false })).toBeNull();
    expect(overdueDays({ daysToEnd: -3, finalized: true })).toBeNull();
  });
  it("usa singular para 1 dia", () => {
    expect(overdueLabel(1)).toBe("1 dia em atraso");
    expect(overdueLabel(4)).toBe("4 dias em atraso");
  });
});
