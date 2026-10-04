import { describe, expect, it } from "vitest";
import { daysToEndLabel } from "~/utils/contracts";

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
