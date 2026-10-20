import type { InternalNotification, InternalNotificationList } from "~/types/api";

/** Central própria do módulo, independente dos alertas por e-mail do Hub. */
export function useInternalNotifications() {
  const api = useApi();
  const data = useState<InternalNotificationList | null>("contracts-internal-inbox", () => null);
  const loading = useState<boolean>("contracts-internal-inbox-loading", () => false);
  const error = useState<string>("contracts-internal-inbox-error", () => "");
  const unreadCount = computed(() => data.value?.unreadCount ?? 0);

  async function load(): Promise<void> {
    loading.value = true;
    try {
      data.value = await api.get<InternalNotificationList>("/notificacoes-internas");
      error.value = "";
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : "Não foi possível carregar as notificações internas.";
    } finally {
      loading.value = false;
    }
  }

  async function markRead(item: InternalNotification): Promise<void> {
    if (item.readAt) return;
    data.value = await api.patch<InternalNotificationList>(
      "/notificacoes-internas/" + encodeURIComponent(item.id) + "/lida", {},
    );
  }

  return { data, loading, error, unreadCount, load, markRead };
}
