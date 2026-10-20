import { describe, expect, it } from "vitest";
import { isPreviewableImage } from "../utils/auditAttachments";

describe("prévias de imagens da Auditoria", () => {
  it.each(["image/png", "image/jpeg", "image/webp", "image/gif", "image/avif"])(
    "reconhece MIME %s",
    (type) => expect(isPreviewableImage({ name: "print", type })).toBe(true),
  );

  it("detecta imagens legadas pelo nome se o MIME é genérico", () => {
    expect(isPreviewableImage({ name: "contrato.PNG", type: "application/octet-stream" })).toBe(true);
    expect(isPreviewableImage({ name: "evidencia.jpg", type: "" })).toBe(true);
  });

  it("mantém PDFs e SVGs como documentos baixáveis", () => {
    expect(isPreviewableImage({ name: "contrato.pdf", type: "application/pdf" })).toBe(false);
    expect(isPreviewableImage({ name: "vetor.svg", type: "image/svg+xml" })).toBe(false);
    expect(isPreviewableImage({ name: "script.svg", type: "application/octet-stream" })).toBe(false);
    expect(isPreviewableImage({ name: "contrato.png", type: "application/pdf" })).toBe(false);
  });
});
