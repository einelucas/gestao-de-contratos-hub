import { describe, expect, it } from "vitest";
import { daysToEndLabel, matchesValueComposition, overdueDays, overdueLabel } from "~/utils/contracts";

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

describe("matchesValueComposition", () => {
  const serviceOnly = { serviceValue: "1500.50", ownMaterialValue: "0", thirdPartyMaterialValue: 0 };
  const withOwn = { serviceValue: 100, ownMaterialValue: "2500", thirdPartyMaterialValue: "0" };
  const withThirdParty = { serviceValue: "100", ownMaterialValue: "0", thirdPartyMaterialValue: 750 };
  const mixed = { serviceValue: 100, ownMaterialValue: 200, thirdPartyMaterialValue: 300 };
  const empty = { serviceValue: 0, ownMaterialValue: "0", thirdPartyMaterialValue: "0" };

  it("'Todos' aceita qualquer composição", () => {
    for (const contract of [serviceOnly, withOwn, withThirdParty, mixed, empty]) {
      expect(matchesValueComposition(contract, "Todos")).toBe(true);
    }
  });

  it("filtra contratos com material próprio", () => {
    expect(matchesValueComposition(withOwn, "MaterialProprio")).toBe(true);
    expect(matchesValueComposition(mixed, "MaterialProprio")).toBe(true);
    expect(matchesValueComposition(serviceOnly, "MaterialProprio")).toBe(false);
    expect(matchesValueComposition(withThirdParty, "MaterialProprio")).toBe(false);
  });

  it("filtra contratos com material de terceiros", () => {
    expect(matchesValueComposition(withThirdParty, "MaterialTerceiros")).toBe(true);
    expect(matchesValueComposition(mixed, "MaterialTerceiros")).toBe(true);
    expect(matchesValueComposition(serviceOnly, "MaterialTerceiros")).toBe(false);
    expect(matchesValueComposition(withOwn, "MaterialTerceiros")).toBe(false);
  });

  it("filtra contratos somente de serviços (sem nenhum material)", () => {
    expect(matchesValueComposition(serviceOnly, "SomenteServicos")).toBe(true);
    expect(matchesValueComposition(withOwn, "SomenteServicos")).toBe(false);
    expect(matchesValueComposition(withThirdParty, "SomenteServicos")).toBe(false);
    expect(matchesValueComposition(mixed, "SomenteServicos")).toBe(false);
    expect(matchesValueComposition(empty, "SomenteServicos")).toBe(false);
  });

  it("normaliza valores numéricos e textuais da API", () => {
    expect(matchesValueComposition({ serviceValue: "0", ownMaterialValue: 10.5, thirdPartyMaterialValue: "0" }, "MaterialProprio")).toBe(true);
  });
});
