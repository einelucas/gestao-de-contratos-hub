import { describe, expect, it } from "vitest";
import { formatNumber } from "~/utils/format";

describe("formatNumber", () => {
  it("formata números no padrão pt-BR", () => {
    expect(formatNumber(1234.5, 1)).toBe("1.234,5");
  });
});
