/**
 * TEMPORÁRIO — remover antes da versão final.
 *
 * Guarda a foto de perfil escolhida no navegador (localStorage), sem backend.
 * A escolha e o ajuste (zoom/posição) ficam em `TemporaryAvatarEditor.vue`,
 * acionado por Ctrl+clique no botão "Registro de Atividades".
 *
 * Para remover a funcionalidade: apague este arquivo, apague
 * `components/TemporaryAvatarEditor.vue` e os blocos marcados com
 * "TEMP-AVATAR" em AppHeader.vue, UserMenu.vue e ContractAuditKanban.vue.
 */
const STORAGE_KEY = "gc-temporary-avatar";

let hydrated = false;

export function useTemporaryAvatar() {
  const store = useAuthStore();
  const image = useState<string | null>("gc-temporary-avatar", () => null);

  if (import.meta.client && !hydrated) {
    hydrated = true;
    image.value = window.localStorage.getItem(STORAGE_KEY);
  }

  /** Só sobrescreve o avatar do próprio usuário logado. */
  function imageFor(
    userId: string | null | undefined,
    fallback?: string | null,
  ): string | undefined {
    if (!image.value || !userId || store.user?.id !== userId) {
      return fallback ?? undefined;
    }
    return image.value;
  }

  function setImage(dataUrl: string): void {
    image.value = dataUrl;
    window.localStorage.setItem(STORAGE_KEY, dataUrl);
  }

  function clear(): void {
    image.value = null;
    window.localStorage.removeItem(STORAGE_KEY);
  }

  return { image, imageFor, setImage, clear };
}
