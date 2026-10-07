import { defineStore } from "pinia";
import type { CurrentUser, Permission, Role } from "~/types/api";

const MATRIX: Record<Role, Permission[]> = {
  VIEWER: ["contracts:view"],
  ANALYST: ["contracts:view", "contracts:manage"],
  ADMIN: ["contracts:view", "contracts:manage", "contracts:import", "users:manage", "audit:read", "alerts:manage", "teams:manage"],
};

/** Modo de autenticação informado pelo backend (`GET /auth/provider`). */
export type AuthProvider = "keycloak" | "homologation";

export const useAuthStore = defineStore("auth", () => {
  // Keycloak/desenvolvimento: token Bearer. Homologação: sessão em cookie HttpOnly
  // (o frontend nunca vê o token; só pergunta ao backend quem está logado).
  const token = useCookie<string | null>("hub_gestao_contratos_access_token", { sameSite: "lax" });
  const user = ref<CurrentUser | null>(null);
  const loading = ref(false);
  const provider = ref<AuthProvider | null>(null);

  const authenticated = computed(() => Boolean(user.value) && (provider.value === "homologation" || Boolean(token.value)));
  const isAdmin = computed(() => user.value?.role === "ADMIN");
  const can = (permission: Permission) => Boolean(user.value && MATRIX[user.value.role].includes(permission));

  const providerError = ref(false);

  /** Modo do backend. Sem resposta, NÃO assume Keycloak: a tela de login mostra o erro. */
  async function loadProvider(): Promise<AuthProvider | null> {
    if (provider.value) return provider.value;
    try {
      provider.value = (await useApi().get<{ provider: AuthProvider }>("/auth/provider")).provider;
      providerError.value = false;
    } catch {
      providerError.value = true;
    }
    return provider.value;
  }

  async function loadUser(): Promise<boolean> {
    const mode = await loadProvider();
    if (!mode || (mode === "keycloak" && !token.value)) { user.value = null; return false; }
    loading.value = true;
    try {
      user.value = await useApi().get<CurrentUser>("/auth/me");
      return true;
    } catch {
      if (mode === "keycloak") token.value = null;
      user.value = null;
      return false;
    } finally { loading.value = false; }
  }

  async function loginPassword(username: string, password: string): Promise<void> {
    user.value = await useApi().post<CurrentUser>("/auth/login", { username, password });
  }

  async function loginDev(role: Role): Promise<void> {
    token.value = `dev-${role.toLowerCase()}`;
    if (!(await loadUser())) throw new Error("O backend não aceitou a autenticação de desenvolvimento.");
  }

  function acceptToken(accessToken: string): void { token.value = accessToken; }

  async function logoutSession(): Promise<void> {
    if (provider.value === "homologation") {
      try { await useApi().post("/auth/logout"); } catch { /* sessão já inválida: segue limpando o estado local */ }
    }
    clear();
  }

  function clear(): void { token.value = null; user.value = null; }
  return {
    token, user, loading, provider, providerError, authenticated, isAdmin, can,
    loadProvider, loadUser, loginPassword, loginDev, acceptToken, logoutSession, clear,
  };
});
