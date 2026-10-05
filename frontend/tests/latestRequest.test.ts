import { describe, expect, it } from "vitest";
import { contractTeamProblem } from "~/utils/contracts";
import { createLatestRequest } from "~/utils/latestRequest";

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/** Mesmo padrão do `load()` do Dashboard/EmailPreviewModal/NotificationAdmin. */
function makeLoader() {
  const guard = createLatestRequest();
  const state = { shown: "", loading: false, error: "" };
  async function load(fetcher: () => Promise<string>) {
    const request = guard.begin();
    state.loading = true;
    state.error = "";
    try {
      const value = await fetcher();
      if (!request.isCurrent()) return;
      state.shown = value;
    } catch (cause) {
      if (!request.isCurrent()) return;
      state.error = String(cause);
    } finally {
      if (request.isCurrent()) state.loading = false;
    }
  }
  return { state, load, guard };
}

describe("createLatestRequest — última resposta vence", () => {
  it("resposta antiga que chega depois não sobrescreve a atual (filtro A → B)", async () => {
    const { state, load } = makeLoader();
    const unitA = deferred<string>();
    const unitB = deferred<string>();
    const loadA = load(() => unitA.promise);
    const loadB = load(() => unitB.promise);

    unitB.resolve("unidade B");
    await loadB;
    expect(state.shown).toBe("unidade B");
    expect(state.loading).toBe(false);

    unitA.resolve("unidade A");
    await loadA;
    expect(state.shown).toBe("unidade B");
  });

  it("erro de requisição antiga não aparece sobre o resultado atual", async () => {
    const { state, load } = makeLoader();
    const old = deferred<string>();
    const current = deferred<string>();
    const loadOld = load(() => old.promise);
    const loadCurrent = load(() => current.promise);
    current.resolve("atual");
    await loadCurrent;
    old.reject(new Error("timeout"));
    await loadOld;
    expect(state.error).toBe("");
    expect(state.shown).toBe("atual");
  });

  it("loading só termina quando a requisição mais recente termina", async () => {
    const { state, load } = makeLoader();
    const first = deferred<string>();
    const second = deferred<string>();
    const loadFirst = load(() => first.promise);
    const loadSecond = load(() => second.promise);
    first.resolve("primeiro");
    await loadFirst;
    expect(state.loading).toBe(true);
    second.resolve("segundo");
    await loadSecond;
    expect(state.loading).toBe(false);
    expect(state.shown).toBe("segundo");
  });

  it("aborta o sinal da requisição anterior", () => {
    const guard = createLatestRequest();
    const first = guard.begin();
    const second = guard.begin();
    expect(first.signal.aborted).toBe(true);
    expect(second.signal.aborted).toBe(false);
    expect(first.isCurrent()).toBe(false);
    expect(second.isCurrent()).toBe(true);
  });

  it("cancel() invalida a requisição em andamento", async () => {
    const { state, load, guard } = makeLoader();
    const pending = deferred<string>();
    const run = load(() => pending.promise);
    guard.cancel();
    pending.resolve("tarde demais");
    await run;
    expect(state.shown).toBe("");
  });
});

describe("contractTeamProblem — consulta de equipes", () => {
  const base = { teamId: "t1", notify: true, teamFound: false, teamWarning: "" };

  it("erro ao consultar equipes NÃO invalida a equipe atual (backend decide)", () => {
    expect(contractTeamProblem({ ...base, teamsStatus: "error" })).toBe("");
  });

  it("enquanto carrega não bloqueia o salvamento", () => {
    expect(contractTeamProblem({ ...base, teamsStatus: "loading" })).toBe("");
  });

  it("lista carregada sem a equipe: equipe de outro setor", () => {
    expect(contractTeamProblem({ ...base, teamsStatus: "loaded" })).toMatch(/não pertence ao setor/);
  });

  it("lista carregada com a equipe: ok", () => {
    expect(contractTeamProblem({ ...base, teamsStatus: "loaded", teamFound: true })).toBe("");
  });

  it("alertas ativos exigem equipe", () => {
    expect(contractTeamProblem({ ...base, teamId: "", teamsStatus: "loaded" })).toMatch(/selecione a equipe/);
  });

  it("aviso da equipe bloqueia ativar alertas", () => {
    expect(
      contractTeamProblem({ ...base, teamsStatus: "loaded", teamFound: true, teamWarning: "Equipe desativada." }),
    ).toMatch(/Ajuste a equipe/);
  });

  it("sem alertas e sem equipe: nada a validar", () => {
    expect(contractTeamProblem({ ...base, teamId: "", notify: false, teamsStatus: "error" })).toBe("");
  });
});
