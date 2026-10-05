import type { Contract, Sector } from "~/types/api";
import { createLatestRequest } from "~/utils/latestRequest";

export function useContracts() {
  const api = useApi();
  const contracts = ref<Contract[]>([]);
  const sectors = ref<Sector[]>([]);
  const loading = ref(false);
  const error = ref("");
  const sectorsError = ref("");
  const lastUpdated = ref<Date | null>(null);

  const contractsRequest = createLatestRequest();

  // Cada recurso trata o próprio erro: /setores fora do ar não derruba a lista de contratos
  // (e vice-versa). Em falha, mantém os setores já carregados.
  async function loadSectors() {
    try {
      const response = await api.get<{ items: Sector[] }>("/setores");
      sectors.value = response.items;
      sectorsError.value = "";
    } catch (cause) {
      sectorsError.value = cause instanceof Error ? cause.message : "Não foi possível carregar os setores.";
    }
  }

  async function loadContracts(sectorId?: string) {
    const request = contractsRequest.begin();
    loading.value = true; error.value = "";
    try {
      const response = await api.request<{ items: Contract[]; total: number }>("/contratos", {
        method: "GET", query: sectorId ? { sectorId } : undefined, signal: request.signal,
      });
      if (!request.isCurrent()) return;
      contracts.value = response.items;
      lastUpdated.value = new Date();
    } catch (cause) {
      if (!request.isCurrent()) return;
      error.value = cause instanceof Error ? cause.message : "Não foi possível carregar os contratos.";
      contracts.value = [];
    } finally { if (request.isCurrent()) loading.value = false; }
  }

  async function bootstrap(sectorId?: string) {
    await Promise.all([loadSectors(), loadContracts(sectorId)]);
  }

  return { contracts, sectors, loading, error, sectorsError, lastUpdated, loadSectors, loadContracts, bootstrap };
}
