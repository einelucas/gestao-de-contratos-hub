<script setup lang="ts">
import { Download, FileSpreadsheet, Upload } from "lucide-vue-next";
import type { Sector } from "~/types/api";

interface ImportIssue { line: number; column: string; reason: string }
interface ImportPreview {
  filename: string; fileSha256: string; sectorFingerprint: string;
  currentContracts: number; rowsFound: number; validRows: number; invalidRows: number;
  contractsToImport: number; newSuppliers: number; units: string[];
  overdueContracts: number; finalizedContracts: number; duplicates: number;
  issues: ImportIssue[]; canConfirm: boolean; historyAction: string;
}

const props = defineProps<{ open: boolean; sectors: Sector[] }>();
const emit = defineEmits<{ close: []; imported: [count: number] }>();
const api = useApi();
const sectorId = ref("");
const file = ref<File | null>(null);
const preview = ref<ImportPreview | null>(null);
const busy = ref(false);
const error = ref("");
const confirmation = ref("");
const dragging = ref(false);
const eligibleSectors = computed(() => props.sectors.filter(sector => sector.active));

watch(() => props.open, open => {
  if (!open) return;
  sectorId.value = eligibleSectors.value[0]?.id ?? "";
  file.value = null;
  preview.value = null;
  error.value = "";
  confirmation.value = "";
});
watch(sectorId, () => { preview.value = null; confirmation.value = ""; });
function selectFile(candidate?: File): void {
  if (busy.value) return;
  file.value = candidate ?? null;
  preview.value = null;
  confirmation.value = "";
  error.value = "";
}
function onDrop(event: DragEvent): void {
  dragging.value = false;
  if (busy.value) return;
  selectFile(event.dataTransfer?.files[0]);
}
function formData(): FormData {
  const data = new FormData();
  data.append("sectorId", sectorId.value);
  if (file.value) data.append("file", file.value);
  return data;
}
async function validate(): Promise<void> {
  if (!file.value || !sectorId.value) return;
  busy.value = true; error.value = ""; preview.value = null;
  try {
    preview.value = await api.request<ImportPreview>("/contratos/importacao/preview", { method: "POST", body: formData() });
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Falha ao validar a planilha.";
  } finally { busy.value = false; }
}
async function confirm(): Promise<void> {
  if (!preview.value?.canConfirm || confirmation.value !== "SUBSTITUIR" || !file.value) return;
  busy.value = true; error.value = "";
  try {
    const data = formData();
    data.append("expectedSha256", preview.value.fileSha256);
    data.append("expectedFingerprint", preview.value.sectorFingerprint);
    data.append("confirmReplace", "true");
    const result = await api.request<{ importedCount: number }>("/contratos/importacao/confirmar", { method: "POST", body: data });
    emit("imported", result.importedCount);
    emit("close");
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Falha ao importar. Os contratos anteriores foram preservados.";
    preview.value = null; // novo preview é obrigatório após conflito ou falha
  } finally { busy.value = false; }
}
async function downloadTemplate(): Promise<void> {
  try {
    const blob = await api.request<Blob>("/contratos/importacao/modelo", { responseType: "blob" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url; anchor.download = "modelo-importacao-contratos.csv"; anchor.click();
    URL.revokeObjectURL(url);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível baixar o modelo.";
  }
}
</script>

<template>
  <AppModal :open="open" title="Importar contratos" wide @close="!busy && emit('close')">
    <div class="import-flow">
      <p>Valide a planilha antes de substituir a base de um setor. Apenas contratos desse setor serão afetados.</p>
      <div class="import-controls">
        <label>Setor
          <select v-model="sectorId" :disabled="busy"><option value="" disabled>Selecione um setor</option><option v-for="sector in eligibleSectors" :key="sector.id" :value="sector.id">{{ sector.name }}</option></select>
        </label>
        <button type="button" class="btn" :disabled="busy" @click="downloadTemplate"><Download class="size-4" /> Baixar modelo</button>
      </div>
      <label class="import-drop" :class="{ dragging }" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false" @drop.prevent="onDrop">
        <Upload class="size-4" />
        <span>{{ file?.name || "Selecione ou arraste um arquivo .xlsx ou .csv (até 5 MB)" }}</span>
        <input type="file" accept=".xlsx,.csv" :disabled="busy" @change="selectFile(($event.target as HTMLInputElement).files?.[0])" />
      </label>
      <button type="button" class="btn" :disabled="busy || !sectorId || !file" @click="validate"><FileSpreadsheet class="size-4" /> {{ busy ? "Aguarde..." : "Validar planilha" }}</button>
      <p v-if="error" class="import-error" role="alert">{{ error }}</p>
      <section v-if="preview" class="import-preview" aria-label="Prévia da importação">
        <h3>Prévia: {{ preview.filename }}</h3>
        <div class="import-stats">
          <p><strong>{{ preview.currentContracts }}</strong><span>Contratos atuais</span></p>
          <p><strong>{{ preview.rowsFound }}</strong><span>Linhas encontradas</span></p>
          <p><strong>{{ preview.validRows }}</strong><span>Linhas válidas</span></p>
          <p><strong>{{ preview.invalidRows }}</strong><span>Linhas inválidas</span></p>
          <p><strong>{{ preview.contractsToImport }}</strong><span>A importar</span></p>
          <p><strong>{{ preview.newSuppliers }}</strong><span>Fornecedores novos</span></p>
          <p><strong>{{ preview.overdueContracts }}</strong><span>Vencidos</span></p>
          <p><strong>{{ preview.finalizedContracts }}</strong><span>Finalizados</span></p>
          <p><strong>{{ preview.duplicates }}</strong><span>Duplicidades</span></p>
        </div>
        <p><strong>Unidades:</strong> {{ preview.units.join(", ") || "Nenhuma" }}</p>
        <p v-if="preview.historyAction === 'reset_baseline'">O histórico corporativo de vencidos será reiniciado com a nova base.</p>
        <p v-if="preview.historyAction === 'create_baseline'">Uma nova baseline de vencidos será criada sem apagar dados de outros setores.</p>
        <div v-if="preview.issues.length" class="import-errors" role="alert">
          <strong>Corrija os erros e valide novamente:</strong>
          <ul><li v-for="(issue, index) in preview.issues" :key="index">Linha {{ issue.line || "—" }} · {{ issue.column }}: {{ issue.reason }}</li></ul>
        </div>
        <div v-else class="import-confirm">
          <p><strong>Esta operação substituirá todos os contratos atuais deste setor pelos contratos válidos desta planilha.</strong></p>
          <label>Digite <strong>SUBSTITUIR</strong> para confirmar
            <input v-model="confirmation" autocomplete="off" :disabled="busy" />
          </label>
          <button type="button" class="btn import-danger" :disabled="busy || confirmation !== 'SUBSTITUIR'" @click="confirm">Confirmar substituição</button>
        </div>
      </section>
    </div>
  </AppModal>
</template>

<style scoped>
.import-flow { display: grid; gap: 16px; }
.import-controls { display: flex; align-items: end; gap: 12px; flex-wrap: wrap; }
.import-controls label, .import-confirm label { display: grid; gap: 6px; font-weight: 700; }
.import-controls select, .import-confirm input { min-height: 38px; padding: 7px 10px; border: 1px solid #cbd5e1; border-radius: 8px; }
.import-drop { display: flex; align-items: center; gap: 9px; padding: 18px; border: 2px dashed #9baec8; border-radius: 10px; cursor: pointer; }
.import-drop.dragging { background: #edf4fb; }
.import-drop input { max-width: 230px; }
.import-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(125px, 1fr)); gap: 8px; }
.import-stats p { display: grid; margin: 0; padding: 10px; background: #f4f7fa; border-radius: 8px; }
.import-stats strong { font-size: 20px; }
.import-stats span { font-size: 12px; }
.import-error, .import-errors { color: #9b1c1c; }
.import-confirm { display: grid; gap: 12px; border: 1px solid #e9aaa3; background: #fff5f4; border-radius: 9px; padding: 14px; }
.import-danger { background: #a62727; color: #fff; justify-self: start; }
</style>
