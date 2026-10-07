/**
 * "Última requisição vence": cada `begin()` cancela a anterior (AbortController)
 * e devolve um `isCurrent()` que só continua verdadeiro enquanto nenhuma outra
 * requisição tiver começado. Quem aplica a resposta no estado da tela checa
 * `isCurrent()` antes — assim uma resposta antiga que chegue depois (filtro
 * trocado rápido, página alterada, modal reaberto) nunca sobrescreve a atual.
 */
export interface LatestRequestTicket {
  signal: AbortSignal;
  isCurrent: () => boolean;
}

export function createLatestRequest() {
  let sequence = 0;
  let controller: AbortController | null = null;

  return {
    begin(): LatestRequestTicket {
      controller?.abort();
      const current = new AbortController();
      controller = current;
      const id = ++sequence;
      return { signal: current.signal, isCurrent: () => id === sequence };
    },
    /** Invalida a requisição em andamento sem iniciar outra (ex.: modal fechado). */
    cancel(): void {
      controller?.abort();
      controller = null;
      sequence++;
    },
  };
}
