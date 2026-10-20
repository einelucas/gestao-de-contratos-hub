<script setup lang="ts">
import { Download, Image as ImageIcon, LoaderCircle, RotateCw, X } from "lucide-vue-next";
import type { AuditAttachment } from "~/types/api";

/**
 * Prévia autenticada. O URL relativo da API requer sessão/token, portanto NÃO
 * pode ser usado diretamente em <img src>. Baixamos via useApi e geramos um
 * object URL local, revogado ao desmontar o componente.
 */
const props = withDefaults(defineProps<{
  attachment: AuditAttachment;
  variant?: "timeline" | "file";
}>(), { variant: "timeline" });

const api = useApi();
const previewUrl = ref<string | null>(null);
const loading = ref(true);
const failed = ref(false);
const expanded = ref(false);
let requestSerial = 0;

async function loadImage(): Promise<void> {
  if (!import.meta.client) return;
  const request = ++requestSerial;
  loading.value = true;
  failed.value = false;
  const previous = previewUrl.value;
  previewUrl.value = null;
  if (previous) URL.revokeObjectURL(previous);

  try {
    const blob = await api.request<Blob>(props.attachment.url, {
      method: "GET",
      responseType: "blob",
    });
    if (request !== requestSerial) return;
    previewUrl.value = URL.createObjectURL(blob);
  } catch {
    if (request === requestSerial) failed.value = true;
  } finally {
    if (request === requestSerial) loading.value = false;
  }
}

watch(() => props.attachment.id, () => { void loadImage(); }, { immediate: true });

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") expanded.value = false;
}
watch(expanded, (open) => {
  if (!import.meta.client) return;
  if (open) window.addEventListener("keydown", onKeydown);
  else window.removeEventListener("keydown", onKeydown);
});
onBeforeUnmount(() => {
  requestSerial++;
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value);
  if (import.meta.client) window.removeEventListener("keydown", onKeydown);
});
</script>

<template>
  <div class="audit-image" :class="{ 'audit-image--file': variant === 'file' }">
    <div v-if="loading" class="audit-image-state" role="status">
      <LoaderCircle class="size-4 animate-spin" />
      Carregando imagem…
    </div>
    <div v-else-if="failed || !previewUrl" class="audit-image-state">
      <ImageIcon class="size-4" />
      <span>Não foi possível carregar a imagem.</span>
      <button type="button" class="audit-image-retry" @click="loadImage">
        <RotateCw class="size-3.5" /> Tentar novamente
      </button>
    </div>
    <button v-else type="button" class="audit-image-open"
      :aria-label="'Ampliar imagem ' + attachment.name"
      :title="'Ampliar ' + attachment.name"
      @click="expanded = true">
      <img :src="previewUrl" :alt="attachment.name" loading="lazy" />
    </button>
    <div class="audit-image-caption">
      <span :title="attachment.name">{{ attachment.name }}</span>
      <small>Imagem · clique para ampliar</small>
    </div>
  </div>

  <Teleport to="body">
    <div v-if="expanded && previewUrl" class="audit-image-lightbox"
      role="dialog" aria-modal="true" :aria-label="'Imagem ' + attachment.name"
      @click.self="expanded = false">
      <div class="audit-image-lightbox-toolbar">
        <strong>{{ attachment.name }}</strong>
        <div class="audit-image-lightbox-actions">
          <a :href="previewUrl" :download="attachment.name" title="Baixar imagem">
            <Download class="size-4" /> <span>Baixar</span>
          </a>
          <button type="button" aria-label="Fechar imagem" @click="expanded = false">
            <X class="size-5" />
          </button>
        </div>
      </div>
      <img :src="previewUrl" :alt="attachment.name" class="audit-image-lightbox-full" />
    </div>
  </Teleport>
</template>

<style scoped>
.audit-image {
  min-width: 0;
  overflow: hidden;
  border: 1px solid #dfe7f0;
  border-radius: 12px;
  background: #f7f9fc;
}
.audit-image-open {
  display: block;
  width: 100%;
  padding: 6px;
  background: transparent;
  cursor: zoom-in;
}
.audit-image-open img {
  display: block;
  width: 100%;
  max-height: 380px;
  object-fit: contain;
  border-radius: 6px;
  background: #eef2f7;
}
.audit-image-open:focus-visible, .audit-image-retry:focus-visible {
  outline: 2px solid #304f7e;
  outline-offset: -2px;
}
.audit-image-caption {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 10px;
  background: white;
  color: #40546d;
  font-size: 11px;
}
.audit-image-caption span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.audit-image-caption small { flex-shrink: 0; color: #8795a7; font-size: 10px; }
.audit-image-state {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-height: 92px;
  padding: 12px;
  color: #62758e;
  font-size: 11px;
}
.audit-image-retry {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 8px;
  border: 1px solid #ccd7e4;
  border-radius: 7px;
  background: white;
  color: #304f7e;
}
.audit-image--file .audit-image-open img { max-height: 175px; }
.audit-image-lightbox {
  position: fixed;
  z-index: 5000;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 70px 18px 22px;
  background: rgba(13, 22, 38, 0.94);
}
.audit-image-lightbox-toolbar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  min-height: 60px;
  padding: 10px 20px;
  color: #fff;
}
.audit-image-lightbox-toolbar strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.audit-image-lightbox-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.audit-image-lightbox-actions > a,
.audit-image-lightbox-actions > button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 9px;
  border: 1px solid rgba(255,255,255,.25);
  border-radius: 8px;
  color: #fff;
  background: rgba(255,255,255,.08);
  cursor: pointer;
  font-size: 12px;
}
.audit-image-lightbox-full {
  display: block;
  max-width: 100%;
  max-height: calc(100vh - 100px);
  object-fit: contain;
}
@media (max-width: 600px) {
  .audit-image-caption { flex-direction: column; align-items: flex-start; gap: 2px; }
  .audit-image-lightbox-toolbar { padding-inline: 10px; }
  .audit-image-lightbox-actions > a span { display: none; }
}
</style>
