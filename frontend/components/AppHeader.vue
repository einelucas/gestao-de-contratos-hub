<script setup lang="ts">
import { ArrowLeft, CloudDownload, History, Search } from "lucide-vue-next";
const router = useRouter(); const { store } = useAuth();
const search = useState<string>('contracts-global-search', () => '');
const exportTrigger = useState<number>('contracts-export-trigger', () => 0);
// Exportação só existe na aba Contratos (exporta a lista filtrada); nas demais o botão some.
const route = useRoute();
const canExport = computed(() => route.path === "/dashboard/contratos");
function exportContracts(){ exportTrigger.value++; }

// TEMP-AVATAR (remover na versão final): Ctrl+clique no botão "Registro de Atividades"
// abre o ajuste da foto de perfil; Ctrl+Shift+clique remove. A foto fica só neste
// navegador (localStorage) e não passa pelo backend.
const temporaryAvatar = useTemporaryAvatar();
const avatarInput = ref<HTMLInputElement | null>(null);
const avatarFile = ref<File | null>(null);
const avatarEditorOpen = ref(false);
const avatarToast = ref("");
const hasTemporaryAvatar = computed(() => Boolean(temporaryAvatar.image.value));
let avatarToastTimer: ReturnType<typeof setTimeout> | undefined;

function handleRegistroClick(event: MouseEvent): void {
  if (!event.ctrlKey) return;
  event.preventDefault();
  if (event.shiftKey) {
    temporaryAvatar.clear();
    showAvatarToast("Foto de perfil removida (temporário).");
    return;
  }
  avatarInput.value?.click();
}

function onAvatarSelected(event: Event): void {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  avatarFile.value = file;
  avatarEditorOpen.value = true;
}

function closeAvatarEditor(): void {
  avatarEditorOpen.value = false;
  avatarFile.value = null;
}

function onAvatarSaved(): void {
  closeAvatarEditor();
  showAvatarToast("Foto de perfil atualizada (temporário).");
}

function onAvatarRemoved(): void {
  closeAvatarEditor();
  showAvatarToast("Foto de perfil removida (temporário).");
}

function showAvatarToast(message: string): void {
  avatarToast.value = message;
  if (avatarToastTimer) clearTimeout(avatarToastTimer);
  avatarToastTimer = setTimeout(() => { avatarToast.value = ""; }, 4000);
}

onBeforeUnmount(() => {
  if (avatarToastTimer) clearTimeout(avatarToastTimer);
});
</script>
<template>
  <header class="flex h-16 items-center gap-4 border-b border-black/[0.07] bg-background px-4 sm:px-6">
    <div class="flex shrink-0 items-center gap-3">
      <NuxtLink to="/dashboard" aria-label="Gestão de Contratos"><img src="/brand/hub-logo.png" alt="Hub" class="h-9 w-auto" /></NuxtLink>
      <button type="button" class="flex h-[34px] items-center gap-1.5 rounded-lg border border-[#e5e7eb] bg-white px-3 text-[13.6px] font-medium text-[#374151] transition-colors hover:bg-muted" @click="router.back()"><ArrowLeft class="size-[18px]" />Voltar</button>
      <div class="hidden sm:block"><p class="text-[9.92px] font-extrabold uppercase leading-none tracking-[0.08em] text-[#8a97ab]">Projetos e Arquitetura</p><p class="mt-1 text-[16px] font-extrabold leading-none tracking-tight text-[#20324a]">Gestão de Contratos</p></div>
    </div>
    <label class="relative mx-auto hidden w-[480px] max-w-full shrink items-center sm:flex"><Search class="pointer-events-none absolute left-3.5 size-4 text-muted-foreground" /><input v-model="search" type="search" placeholder="Buscar contrato ou fornecedor" aria-label="Buscar no módulo" class="h-10 w-full rounded-full bg-white pl-10 pr-4 text-[15px] text-foreground shadow-[0_2px_4px_rgba(15,23,42,0.12)] outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/40" /></label>
    <div class="flex shrink-0 items-center gap-1.5">
      <!-- TEMP-AVATAR: wrapper só existe para capturar o Ctrl+clique antes do NuxtLink navegar. -->
      <span class="contents" @click.capture="handleRegistroClick">
        <NuxtLink v-if="store.user?.role === 'ADMIN'" to="/dashboard/registro-atividades" class="flex h-[34px] items-center gap-1.5 rounded-[4px] bg-primary/10 px-3.5 text-[13px] font-medium text-primary transition-colors hover:bg-primary/15"><History class="size-[15px]" />Registro de Atividades</NuxtLink>
      </span>
      <button v-if="canExport" type="button" aria-label="Exportar dados" title="Exportar contratos filtrados para Excel" class="flex size-[38px] items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground" @click="exportContracts"><CloudDownload class="size-[18px]" /></button>
      <UserMenu />
    </div>

    <!-- TEMP-AVATAR (remover na versão final): input escondido, editor de recorte e aviso. -->
    <input ref="avatarInput" type="file" accept="image/*" class="hidden" @change="onAvatarSelected" />
    <TemporaryAvatarEditor
      v-if="avatarEditorOpen && avatarFile"
      :file="avatarFile"
      :has-avatar="hasTemporaryAvatar"
      @close="closeAvatarEditor"
      @saved="onAvatarSaved"
      @removed="onAvatarRemoved"
    />
    <div v-if="avatarToast" class="fixed bottom-5 right-5 z-50 rounded-lg bg-[#20324a] px-4 py-2.5 text-xs font-semibold text-white shadow-lg">
      {{ avatarToast }}
    </div>
  </header>
</template>
