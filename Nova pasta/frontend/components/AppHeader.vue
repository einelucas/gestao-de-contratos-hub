<script setup lang="ts">
import { ArrowLeft, Bell, CloudDownload, History, Search } from "lucide-vue-next";
const router = useRouter(); const { store } = useAuth();
const search = useState<string>('contracts-global-search', () => '');
const notificationTrigger = useState<number>('contracts-notification-trigger', () => 0);
const exportTrigger = useState<number>('contracts-export-trigger', () => 0);
const { count: attentionCount } = useAttention();
function openNotifications(){ notificationTrigger.value++; }
// Exportação só existe na aba Contratos (exporta a lista filtrada); nas demais o botão some.
const route = useRoute();
const canExport = computed(() => route.path === "/dashboard/contratos");
function exportContracts(){ exportTrigger.value++; }
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
      <button type="button" aria-label="Notificações" class="relative flex size-[38px] items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground" @click="openNotifications"><Bell class="size-[18px]" /><span v-if="attentionCount" class="header-bell-count">{{ attentionCount > 99 ? "99+" : attentionCount }}</span></button>
      <NuxtLink v-if="store.user?.role === 'ADMIN'" to="/dashboard/auditoria" class="flex h-[34px] items-center gap-1.5 rounded-[4px] bg-primary/10 px-3.5 text-[13px] font-medium text-primary transition-colors hover:bg-primary/15"><History class="size-[15px]" />Registro de Atividades</NuxtLink>
      <button v-if="canExport" type="button" aria-label="Exportar dados" title="Exportar contratos filtrados para Excel" class="flex size-[38px] items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground" @click="exportContracts"><CloudDownload class="size-[18px]" /></button>
      <UserMenu />
    </div>
  </header>
</template>
