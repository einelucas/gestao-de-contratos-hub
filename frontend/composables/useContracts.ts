import type { Contract, Sector } from "~/types/api";

export function useContracts() {
  const api = useApi();
  const contracts = ref<Contract[]>([]);
  const sectors = ref<Sector[]>([]);
  const loading = ref(false);
  const error = ref("");
  const lastUpdated = ref<Date | null>(null);

  async function loadSectors() {
    const response = await api.get<{ items: Sector[] }>("/setores");
    sectors.value = response.items;
  }

  async function loadContracts(sectorId?: string) {
    loading.value = true; error.value = "";
    try {
      const response = await api.get<{ items: Contract[]; total: number }>("/contratos", sectorId ? { sectorId } : undefined);
      contracts.value = response.items;
      lastUpdated.value = new Date();
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : "Não foi possível carregar os contratos.";
      contracts.value = [];
    } finally { loading.value = false; }
  }

  async function bootstrap(sectorId?: string) {
    await Promise.all([loadSectors(), loadContracts(sectorId)]);
  }

  return { contracts, sectors, loading, error, lastUpdated, loadSectors, loadContracts, bootstrap };
}
