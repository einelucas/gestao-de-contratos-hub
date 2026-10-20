import type { AuditAttachment } from "~/types/api";

/** Previews suportados pelo navegador; SVG permanece como arquivo por segurança. */
const MIME_TYPES = new Set([
  "image/jpeg",
  "image/jpg",
  "image/png",
  "image/webp",
  "image/gif",
  "image/bmp",
  "image/avif",
]);
const EXTENSION = /\.(?:jpe?g|png|webp|gif|bmp|avif)$/i;

export function isPreviewableImage(
  attachment: Pick<AuditAttachment, "name" | "type">,
): boolean {
  const mime = (attachment.type || "").split(";")[0]?.trim().toLowerCase() ?? "";
  if (MIME_TYPES.has(mime)) return true;
  // Alguns arquivos legados não possuem MIME detectado.
  return (mime === "" || mime === "application/octet-stream") &&
    EXTENSION.test(attachment.name);
}
