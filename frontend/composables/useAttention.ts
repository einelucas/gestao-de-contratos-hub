import type { AttentionList } from "~/types/api";

/**
 * Contratos que exigem atenção (sino). A lista vem do backend — `GET /alertas/contratos` —,
 * que já aplica as permissões de setor e calcula status e mensagens.
 */
export function useAttention() {
  const api = useApi();
  const data = useState<AttentionList | null>("contracts-attention", () => null);
  const loading = useState<boolean>("contracts-attention-loading", () => false);
  const error = useState<string>("contracts-attention-error", () => "");

  async function load(): Promise<void> {
    loading.value = true;
    error.value = "";
    try {
      data.value = await api.get<AttentionList>("/alertas/contratos");
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : "Não foi possível carregar os alertas.";
    } finally {
      loading.value = false;
    }
  }

  const count = computed(() => (data.value ? data.value.overdue + data.value.attention : 0));

  return { data, loading, error, count, load };
}
