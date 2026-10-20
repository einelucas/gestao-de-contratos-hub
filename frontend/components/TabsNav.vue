<script setup lang="ts">
import { Bell, Columns3, FileText, LayoutDashboard, Send, Users } from "lucide-vue-next";
import type { Permission } from "~/types/api";
const route = useRoute();
const { store } = useAuth();
const notificationTrigger = useState<number>("contracts-notification-trigger", () => 0);
const { count: attentionCount } = useAttention();
const { unreadCount } = useInternalNotifications();
const notificationCount = computed(() => attentionCount.value + unreadCount.value);
interface TabLink { to: string; label: string; icon: typeof FileText; permission?: Permission }
const mainLinks: TabLink[] = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/dashboard/contratos', label: 'Contratos', icon: FileText },
  { to: '/dashboard/auditoria', label: 'Auditoria', icon: Columns3 },
];
// Permissões administrativas continuam separadas das notificações pessoais.
const adminLinks: TabLink[] = [
  { to: '/dashboard/notificacoes', label: 'Envios', icon: Send, permission: 'alerts:manage' },
  { to: '/dashboard/equipes', label: 'Equipes', icon: Users, permission: 'teams:manage' },
];
const visibleAdmin = computed(() => adminLinks.filter(item => !item.permission || store.can(item.permission)));
</script>
<template>
  <div class="app-toolbar-shell pt-2.5">
    <nav id="tabsNav" class="flex h-[70px] items-center gap-2 rounded-[18px] border border-[#e7ecf3] bg-background px-4 py-3 shadow-[0_10px_30px_rgba(39,69,120,0.08)]" aria-label="Navegação da Gestão de Contratos">
      <div class="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto whitespace-nowrap">
        <NuxtLink v-for="item in mainLinks" :key="item.to" :to="item.to" class="hub-tab shrink-0" :class="{ active: route.path === item.to }">
          <component :is="item.icon" class="size-4" />{{ item.label }}
        </NuxtLink>
        <template v-if="visibleAdmin.length">
          <span class="tabs-divider shrink-0" aria-hidden="true" />
          <span class="tabs-group-label shrink-0">Administração</span>
          <NuxtLink v-for="item in visibleAdmin" :key="item.to" :to="item.to" class="hub-tab shrink-0" :class="{ active: route.path === item.to }">
            <component :is="item.icon" class="size-4" />{{ item.label }}
          </NuxtLink>
        </template>
      </div>
      <button type="button" class="relative flex size-10 shrink-0 items-center justify-center rounded-xl border border-[#e7ecf3] bg-[#f8faff] text-[#304f7e] transition-colors hover:bg-blue-50"
        title="Notificações do Gestão de Contratos" aria-label="Abrir notificações do aplicativo" @click="notificationTrigger++">
        <Bell class="size-[19px]" />
        <span v-if="notificationCount" class="absolute -right-1 -top-1 flex min-h-[19px] min-w-[19px] items-center justify-center rounded-full bg-[#D45B73] px-1 text-[10px] font-bold text-white">
          {{ notificationCount > 99 ? "99+" : notificationCount }}
        </span>
      </button>
    </nav>
  </div>
</template>
