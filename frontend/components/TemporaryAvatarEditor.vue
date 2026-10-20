<!-- TEMPORÁRIO — remover antes da versão final. -->
<script setup lang="ts">
import { Check, ImagePlus, RotateCcw, Trash2, X } from "lucide-vue-next";

const props = defineProps<{ file: File; hasAvatar: boolean }>();
const emit = defineEmits<{
  close: [];
  saved: [];
  removed: [];
}>();

const { setImage, clear } = useTemporaryAvatar();

const VIEWPORT = 236;
const OUTPUT = 256;

const source = ref("");
const naturalWidth = ref(0);
const naturalHeight = ref(0);
const zoom = ref(1);
const offsetX = ref(0);
const offsetY = ref(0);
const dragging = ref(false);
const saving = ref(false);
const error = ref("");
const fileInput = ref<HTMLInputElement | null>(null);

const baseScale = computed(() => {
  if (!naturalWidth.value || !naturalHeight.value) return 1;
  return VIEWPORT / Math.min(naturalWidth.value, naturalHeight.value);
});
const scale = computed(() => baseScale.value * zoom.value);
const displayWidth = computed(() => naturalWidth.value * scale.value);
const displayHeight = computed(() => naturalHeight.value * scale.value);
const imageStyle = computed(() => ({
  width: `${displayWidth.value}px`,
  height: `${displayHeight.value}px`,
  left: `${(VIEWPORT - displayWidth.value) / 2 + offsetX.value}px`,
  top: `${(VIEWPORT - displayHeight.value) / 2 + offsetY.value}px`,
}));

function clampOffsets(): void {
  const maxX = Math.max(0, (displayWidth.value - VIEWPORT) / 2);
  const maxY = Math.max(0, (displayHeight.value - VIEWPORT) / 2);
  offsetX.value = Math.min(maxX, Math.max(-maxX, offsetX.value));
  offsetY.value = Math.min(maxY, Math.max(-maxY, offsetY.value));
}

watch(scale, clampOffsets);

async function loadFile(file: File): Promise<void> {
  error.value = "";
  try {
    source.value = await fileToDataUrl(file);
    const image = await loadImage(source.value);
    naturalWidth.value = image.naturalWidth;
    naturalHeight.value = image.naturalHeight;
    resetPosition();
  } catch {
    source.value = "";
    error.value = "Não foi possível ler essa imagem. Escolha outro arquivo.";
  }
}

function resetPosition(): void {
  zoom.value = 1;
  offsetX.value = 0;
  offsetY.value = 0;
}

function pickAnotherFile(): void {
  fileInput.value?.click();
}

function onFileSelected(event: Event): void {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (file) void loadFile(file);
}

type DragStart = {
  pointerX: number;
  pointerY: number;
  offsetX: number;
  offsetY: number;
};
let dragStart: DragStart | null = null;

function startDrag(event: PointerEvent): void {
  if (!source.value) return;
  event.preventDefault();
  dragging.value = true;
  dragStart = {
    pointerX: event.clientX,
    pointerY: event.clientY,
    offsetX: offsetX.value,
    offsetY: offsetY.value,
  };
  window.addEventListener("pointermove", onPointerMove);
  window.addEventListener("pointerup", stopDrag, { once: true });
  window.addEventListener("pointercancel", stopDrag, { once: true });
}

function onPointerMove(event: PointerEvent): void {
  if (!dragging.value || !dragStart) return;
  offsetX.value = dragStart.offsetX + (event.clientX - dragStart.pointerX);
  offsetY.value = dragStart.offsetY + (event.clientY - dragStart.pointerY);
  clampOffsets();
}

function stopDrag(): void {
  dragging.value = false;
  dragStart = null;
  window.removeEventListener("pointermove", onPointerMove);
}

async function save(): Promise<void> {
  if (!source.value || saving.value) return;
  saving.value = true;
  error.value = "";
  try {
    const image = await loadImage(source.value);
    const canvas = document.createElement("canvas");
    canvas.width = OUTPUT;
    canvas.height = OUTPUT;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas indisponível");

    const cropSize = VIEWPORT / scale.value;
    const sourceX = (-(VIEWPORT - displayWidth.value) / 2 - offsetX.value) / scale.value;
    const sourceY = (-(VIEWPORT - displayHeight.value) / 2 - offsetY.value) / scale.value;

    context.drawImage(image, sourceX, sourceY, cropSize, cropSize, 0, 0, OUTPUT, OUTPUT);
    setImage(canvas.toDataURL("image/jpeg", 0.9));
    emit("saved");
  } catch {
    error.value = "Não foi possível salvar a foto. Tente outra imagem.";
  } finally {
    saving.value = false;
  }
}

function remove(): void {
  clear();
  emit("removed");
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === "Escape") emit("close");
}

watch(
  () => props.file,
  (file) => {
    void loadFile(file);
  },
  { immediate: true },
);

onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKeydown);
  stopDrag();
});

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error("Falha ao ler a imagem"));
    reader.readAsDataURL(file);
  });
}

function loadImage(sourceUrl: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Imagem inválida"));
    image.src = sourceUrl;
  });
}
</script>

<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-[60] grid place-items-center bg-[#132033]/55 p-4 backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      aria-label="Ajustar foto de perfil"
      @click.self="emit('close')"
    >
      <section
        class="w-full max-w-[340px] rounded-2xl border border-black/[0.06] bg-white p-5 shadow-[0_24px_70px_rgba(15,23,42,0.28)]"
      >
        <header class="mb-4 flex items-start justify-between gap-3">
          <div>
            <p class="text-[9px] font-extrabold uppercase tracking-[0.12em] text-[#8a97ab]">
              Temporário
            </p>
            <h2 class="text-[15px] font-extrabold leading-tight text-[#20324a]">
              Ajustar foto de perfil
            </h2>
          </div>
          <button
            type="button"
            class="flex size-8 items-center justify-center rounded-full text-[#7b8ba0] transition-colors hover:bg-muted hover:text-[#20324a]"
            aria-label="Fechar"
            @click="emit('close')"
          >
            <X class="size-4" />
          </button>
        </header>

        <div class="flex justify-center">
          <div
            class="relative grid size-[236px] place-items-center overflow-hidden rounded-full bg-[#eef2f7] ring-1 ring-inset ring-black/10"
            :style="{ touchAction: 'none', cursor: dragging ? 'grabbing' : 'grab' }"
            @pointerdown="startDrag"
          >
            <img
              v-if="source"
              :src="source"
              alt="Prévia do recorte"
              class="pointer-events-none absolute max-w-none select-none"
              :style="imageStyle"
              draggable="false"
            />
            <span v-else class="px-8 text-center text-[11px] text-[#8a97ab]">
              Carregando imagem…
            </span>
          </div>
        </div>

        <p class="mt-3 text-center text-[10px] leading-relaxed text-[#8a97ab]">
          Arraste a foto para reposicionar. O círculo é exatamente como ela
          aparece no perfil.
        </p>

        <label class="mt-3 grid gap-1.5">
          <span class="flex items-center justify-between text-[9px] font-extrabold uppercase tracking-[0.08em] text-[#8a97ab]">
            <span>Zoom</span>
            <span>{{ Math.round(zoom * 100) }}%</span>
          </span>
          <input
            v-model.number="zoom"
            type="range"
            min="1"
            max="3"
            step="0.01"
            class="h-1.5 w-full cursor-pointer accent-[#304f7e]"
            aria-label="Zoom da foto"
          />
        </label>

        <div class="mt-3 flex items-center justify-center gap-1.5">
          <button
            type="button"
            class="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[10px] font-semibold text-[#6f7f93] transition-colors hover:bg-muted hover:text-[#20324a]"
            @click="resetPosition"
          >
            <RotateCcw class="size-3.5" />
            Centralizar
          </button>
          <button
            type="button"
            class="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-[10px] font-semibold text-[#6f7f93] transition-colors hover:bg-muted hover:text-[#20324a]"
            @click="pickAnotherFile"
          >
            <ImagePlus class="size-3.5" />
            Trocar imagem
          </button>
          <input
            ref="fileInput"
            type="file"
            accept="image/*"
            class="hidden"
            @change="onFileSelected"
          />
        </div>

        <p v-if="error" class="mt-2 text-center text-[10px] font-semibold text-destructive">
          {{ error }}
        </p>

        <footer class="mt-4 flex items-center gap-2 border-t border-black/[0.06] pt-3">
          <button
            v-if="hasAvatar"
            type="button"
            class="flex items-center gap-1 rounded-lg px-2 py-1.5 text-[10px] font-semibold text-destructive transition-colors hover:bg-destructive/10"
            @click="remove"
          >
            <Trash2 class="size-3.5" />
            Remover foto
          </button>
          <div class="ml-auto flex items-center gap-1.5">
            <button
              type="button"
              class="rounded-lg px-3 py-1.5 text-[11px] font-semibold text-[#5d6b7e] transition-colors hover:bg-muted"
              @click="emit('close')"
            >
              Cancelar
            </button>
            <button
              type="button"
              class="flex items-center gap-1.5 rounded-lg bg-[#304f7e] px-3.5 py-1.5 text-[11px] font-bold text-white transition-colors hover:bg-[#263f65] disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="saving || !source"
              @click="save"
            >
              <Check class="size-3.5" />
              {{ saving ? "Salvando…" : "Salvar foto" }}
            </button>
          </div>
        </footer>
      </section>
    </div>
  </Teleport>
</template>
