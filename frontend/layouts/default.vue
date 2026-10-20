<script setup lang="ts">
const route = useRoute();
const showShell = computed(() => !route.meta.publicLayout);

// Sino global: aberto pelo AppHeader em qualquer página; dados sempre do backend.
const notificationTrigger = useState<number>("contracts-notification-trigger", () => 0);
const notificationsOpen = ref(false);
const { store } = useAuth();
const { load } = useAttention();
const { load: loadInbox } = useInternalNotifications();
let notificationsTimer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  notificationsTimer = setInterval(() => {
    if (store.user?.id && showShell.value) void Promise.all([loadInbox(), load()]);
  }, 60_000);
});
onBeforeUnmount(() => clearInterval(notificationsTimer));

watch(notificationTrigger, () => (notificationsOpen.value = true));
watch(
  () => store.user?.id,
  (id) => {
    if (id && showShell.value) void Promise.all([load(), loadInbox()]);
  },
  { immediate: true },
);

async function openAuditContract(contractId: string): Promise<void> {
  notificationsOpen.value = false;
  await navigateTo({ path: "/dashboard/auditoria", query: { contrato: contractId } });
}

async function openContract(contractId: string): Promise<void> {
  notificationsOpen.value = false;
  await navigateTo({ path: "/dashboard/contratos", query: { contrato: contractId } });
}
</script>

<template>
  <div v-if="showShell" class="min-h-screen bg-[#f4f5f7]">
    <AppHeader />
    <TabsNav />
    <main class="nuxt-app-main"><slot /></main>
    <footer class="p-6 text-center text-[11.5px] text-[#9aa1ac]">Gestão de Contratos · Hub - 2026</footer>
    <ContractNotifications :open="notificationsOpen" @close="notificationsOpen = false" @select="openContract" @select-audit="openAuditContract" />
  </div>
  <slot v-else />
</template>
