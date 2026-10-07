<script setup lang="ts">
import { FileText, LayoutDashboard, Send, Users } from "lucide-vue-next";
import type { Permission } from "~/types/api";
const route = useRoute();
const { store } = useAuth();
interface TabLink { to: string; label: string; icon: typeof FileText; permission?: Permission }
const mainLinks: TabLink[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/dashboard/contratos', label: 'Contratos', icon: FileText },
];
// Área administrativa (ADMIN). "Registro de Atividades" continua no cabeçalho.
// "Permissões" fica fora do fluxo atual (homologação), mas a infraestrutura (rota, componente,
// permissões de backend) continua pronta para reativação futura.
const adminLinks: TabLink[] = [
  { to: '/dashboard/notificacoes', label: 'Envios', icon: Send, permission: 'alerts:manage' },
  { to: '/dashboard/equipes', label: 'Equipes', icon: Users, permission: 'teams:manage' },
];
const visibleAdmin = computed(() => adminLinks.filter(item => !item.permission || store.can(item.permission)));
</script>
<template>
  <div class="app-toolbar-shell pt-2.5"><nav id="tabsNav" class="flex h-[70px] items-center gap-2 overflow-x-auto rounded-[18px] border border-[#e7ecf3] bg-background px-4 py-3 shadow-[0_10px_30px_rgba(39,69,120,0.08)]" aria-label="Navegação da Gestão de Contratos">
    <NuxtLink v-for="item in mainLinks" :key="item.to" :to="item.to" class="hub-tab" :class="{ active: route.path === item.to }"><component :is="item.icon" class="size-4" />{{ item.label }}</NuxtLink>
    <template v-if="visibleAdmin.length">
      <span class="tabs-divider" aria-hidden="true" />
      <span class="tabs-group-label">Administração</span>
      <NuxtLink v-for="item in visibleAdmin" :key="item.to" :to="item.to" class="hub-tab" :class="{ active: route.path === item.to }"><component :is="item.icon" class="size-4" />{{ item.label }}</NuxtLink>
    </template>
  </nav></div>
</template>
