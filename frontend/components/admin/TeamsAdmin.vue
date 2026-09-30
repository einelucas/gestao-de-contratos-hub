<script setup lang="ts">
import { CheckCircle2, ClipboardPaste, Plus, RefreshCw, Save, Trash2, Users } from "lucide-vue-next";
import type { NotificationTeam, Sector } from "~/types/api";
import { EMAIL_PATTERN } from "~/utils/notifications";

/** Administração das equipes de notificação por setor (somente ADMIN). */
interface MemberRow {
  key: string;
  id: string | null;
  name: string;
  email: string;
  active: boolean;
}
interface Draft {
  id: string | null;
  name: string;
  sectorId: string;
  active: boolean;
  members: MemberRow[];
}

const api = useApi();
const teams = ref<NotificationTeam[]>([]);
const sectors = ref<Sector[]>([]);
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const success = ref("");
const sectorFilter = ref("");
const draft = ref<Draft | null>(null);
const original = ref("");
const pasteOpen = ref(false);
const pasteText = ref("");
let keySeq = 0;

const filteredTeams = computed(() =>
  teams.value.filter((team) => !sectorFilter.value || team.sectorId === sectorFilter.value),
);
const dirty = computed(() => Boolean(draft.value) && JSON.stringify(draft.value) !== original.value);

function toDraft(team: NotificationTeam | null): Draft {
  return {
    id: team?.id ?? null,
    name: team?.name ?? "",
    sectorId: team?.sectorId ?? (sectorFilter.value || sectors.value[0]?.id || ""),
    active: team?.active ?? true,
    members: (team?.members ?? []).map((member) => ({
      key: `m${keySeq++}`,
      id: member.id,
      name: member.name ?? "",
      email: member.email,
      active: member.active,
    })),
  };
}

function confirmDiscard(): boolean {
  return !dirty.value || window.confirm("Há alterações não salvas nesta equipe. Descartar?");
}

function open(team: NotificationTeam | null): void {
  if (!confirmDiscard()) return;
  draft.value = toDraft(team);
  original.value = JSON.stringify(draft.value);
  error.value = "";
  success.value = "";
  pasteOpen.value = false;
}

async function load(selectId?: string): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    // Setores e equipes carregam de forma independente: uma falha nas equipes não esvazia os setores.
    const [teamResult, sectorResult] = await Promise.allSettled([
      api.get<{ items: NotificationTeam[] }>("/equipes-notificacao"),
      api.get<{ items: Sector[] }>("/setores"),
    ]);
    if (sectorResult.status === "fulfilled") sectors.value = sectorResult.value.items;
    if (teamResult.status === "fulfilled") teams.value = teamResult.value.items;
    const failed = [teamResult, sectorResult].find((result) => result.status === "rejected");
    if (failed?.status === "rejected") {
      error.value =
        failed.reason instanceof Error
          ? `Não foi possível carregar ${failed === teamResult ? "as equipes" : "os setores"}: ${failed.reason.message}`
          : "Não foi possível carregar as equipes.";
    }
    if (selectId) {
      const team = teams.value.find((item) => item.id === selectId) ?? null;
      draft.value = toDraft(team);
      original.value = JSON.stringify(draft.value);
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível carregar as equipes.";
  } finally {
    loading.value = false;
  }
}

function addMember(email = "", name = ""): void {
  draft.value?.members.push({ key: `m${keySeq++}`, id: null, name, email, active: true });
}

function removeMember(row: MemberRow): void {
  if (!draft.value) return;
  draft.value.members = draft.value.members.filter((member) => member.key !== row.key);
}

/** "Colar lista": um e-mail por linha (ou separados por vírgula/ponto e vírgula), opcionalmente "Nome <email>". */
function applyPaste(): void {
  if (!draft.value) return;
  const existing = new Set(draft.value.members.map((member) => member.email.trim().toLowerCase()));
  let added = 0;
  for (const raw of pasteText.value.split(/[\n;,]+/)) {
    const match = raw.match(/^\s*(.*?)\s*<([^>]+)>\s*$/);
    const email = (match?.[2] ?? raw).trim().toLowerCase();
    const name = match?.[1]?.trim() ?? "";
    if (!email || existing.has(email)) continue;
    existing.add(email);
    addMember(email, name);
    added++;
  }
  pasteText.value = "";
  pasteOpen.value = false;
  success.value = added ? `${added} membro(s) adicionado(s) à lista — salve para confirmar.` : "Nenhum e-mail novo na lista colada.";
}

function validate(value: Draft): string {
  if (!value.name.trim()) return "Informe o nome da equipe.";
  if (!value.sectorId) return "Selecione o setor da equipe.";
  const seen = new Set<string>();
  for (const member of value.members) {
    const email = member.email.trim().toLowerCase();
    if (!email) return "Há membro sem e-mail. Preencha ou remova a linha.";
    if (!EMAIL_PATTERN.test(email)) return `E-mail inválido: ${member.email}`;
    if (seen.has(email)) return `E-mail repetido na equipe: ${email}`;
    seen.add(email);
  }
  return "";
}

function membersPayload(value: Draft) {
  return value.members.map((member) => ({
    id: member.id ?? undefined,
    name: member.name.trim() || null,
    email: member.email.trim().toLowerCase(),
    active: member.active,
  }));
}

async function save(): Promise<void> {
  const value = draft.value;
  if (!value) return;
  error.value = validate(value);
  success.value = "";
  if (error.value) return;
  saving.value = true;
  try {
    let saved: NotificationTeam;
    if (!value.id) {
      saved = await api.post<NotificationTeam>("/equipes-notificacao", {
        name: value.name.trim(),
        sectorId: value.sectorId,
        active: value.active,
        members: membersPayload(value),
      });
    } else {
      const before = JSON.parse(original.value) as Draft;
      const teamChanges: Record<string, unknown> = {};
      if (value.name.trim() !== before.name) teamChanges.name = value.name.trim();
      if (value.sectorId !== before.sectorId) teamChanges.sectorId = value.sectorId;
      if (value.active !== before.active) teamChanges.active = value.active;
      if (Object.keys(teamChanges).length) await api.patch(`/equipes-notificacao/${value.id}`, teamChanges);
      if (JSON.stringify(value.members) !== JSON.stringify(before.members)) {
        await api.put(`/equipes-notificacao/${value.id}/membros`, { members: membersPayload(value) });
      }
      saved = { id: value.id } as NotificationTeam;
    }
    await load(saved.id);
    success.value = "Equipe salva.";
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível salvar a equipe.";
  } finally {
    saving.value = false;
  }
}

onMounted(() => load());
onBeforeRouteLeave(() => confirmDiscard());
</script>

<template>
  <div class="admin-split">
    <section class="surface admin-card">
      <header class="admin-card-head">
        <div><h2>Equipes de notificação</h2><p>Cada membro ativo recebe os alertas dos contratos vinculados à equipe.</p></div>
        <div class="admin-card-actions">
          <button type="button" class="drawer-icon-button" title="Atualizar" :disabled="loading" @click="load()"><RefreshCw class="size-4" /></button>
          <button type="button" class="btn primary" @click="open(null)"><Plus class="size-4" />Nova equipe</button>
        </div>
      </header>
      <label class="inline-field admin-filter"><span>Setor</span>
        <select v-model="sectorFilter"><option value="">Todos os setores</option><option v-for="sector in sectors" :key="sector.id" :value="sector.id">{{ sector.name }}</option></select>
      </label>
      <p v-if="error && !draft" class="form-error" role="alert">{{ error }}</p>
      <p v-if="loading && !teams.length" class="history-empty">Carregando equipes…</p>
      <p v-else-if="!filteredTeams.length" class="history-empty">Nenhuma equipe cadastrada{{ sectorFilter ? " neste setor" : "" }}.</p>
      <ul v-else class="team-list">
        <li v-for="team in filteredTeams" :key="team.id">
          <button type="button" :class="{ active: draft?.id === team.id }" @click="open(team)">
            <strong>{{ team.name }}</strong>
            <span>{{ team.sectorName }}</span>
            <span class="team-meta">
              <span class="pill" :class="team.active ? 'tone-success' : 'tone-muted'">{{ team.active ? "Ativa" : "Desativada" }}</span>
              <span :class="{ 'warning-text': team.active && !team.activeMemberCount }"><Users class="size-3.5" />{{ team.activeMemberCount }} destinatário(s)</span>
              <span>{{ team.contractCount }} contrato(s)</span>
            </span>
          </button>
        </li>
      </ul>
    </section>

    <section class="surface admin-card">
      <p v-if="!draft" class="history-empty">Selecione uma equipe para editar ou crie uma nova.</p>
      <template v-else>
        <header class="admin-card-head">
          <div>
            <h2>{{ draft.id ? "Editar equipe" : "Nova equipe" }}</h2>
            <p v-if="dirty" class="warning-text">Alterações não salvas.</p>
          </div>
          <button type="button" class="btn primary" :disabled="saving || !dirty" @click="save">
            <Save class="size-4" />{{ saving ? "Salvando…" : "Salvar alterações" }}
          </button>
        </header>
        <div class="form-grid">
          <label class="span-2"><span>Nome da equipe</span><input v-model="draft.name" maxlength="180" placeholder="Equipe Contratos — Projetos e Arquitetura" /></label>
          <label><span>Setor</span>
            <select v-model="draft.sectorId"><option value="" disabled>Selecione</option><option v-for="sector in sectors" :key="sector.id" :value="sector.id">{{ sector.name }}</option></select>
          </label>
          <label class="checkbox-field"><input v-model="draft.active" type="checkbox" /><span>Equipe ativa</span></label>
        </div>
        <p v-if="!draft.active" class="form-hint warning-text">Equipe desativada: nenhum contrato vinculado a ela recebe alertas.</p>

        <div class="members-head">
          <h3>Membros ({{ draft.members.length }})</h3>
          <div class="admin-card-actions">
            <button type="button" class="btn small" @click="pasteOpen = !pasteOpen"><ClipboardPaste class="size-3.5" />Colar lista</button>
            <button type="button" class="btn small" @click="addMember()"><Plus class="size-3.5" />Adicionar membro</button>
          </div>
        </div>
        <div v-if="pasteOpen" class="paste-box">
          <textarea v-model="pasteText" rows="4" placeholder="Um e-mail por linha — ou “Nome <email@empresa.com.br>”" />
          <button type="button" class="btn small primary" @click="applyPaste">Adicionar à lista</button>
        </div>
        <p v-if="!draft.members.length" class="history-empty">Nenhum membro. Sem membros ativos, nenhum e-mail é enviado.</p>
        <table v-else class="admin-table members-table">
          <thead><tr><th>Nome</th><th>E-mail</th><th>Ativo</th><th /></tr></thead>
          <tbody>
            <tr v-for="member in draft.members" :key="member.key" :class="{ inactive: !member.active }">
              <td><input v-model="member.name" maxlength="180" placeholder="Opcional" /></td>
              <td><input v-model="member.email" type="email" maxlength="320" placeholder="nome@empresa.com.br" /></td>
              <td><input v-model="member.active" type="checkbox" :aria-label="`Membro ${member.email} ativo`" /></td>
              <td><button type="button" class="drawer-icon-button" title="Remover da equipe" @click="removeMember(member)"><Trash2 class="size-3.5" /></button></td>
            </tr>
          </tbody>
        </table>
        <p class="form-hint">Remover ou desativar um membro só afeta os próximos alertas; o histórico de envios é preservado. Novos membros não recebem marcos já enviados.</p>
      </template>
      <p v-if="error && draft" class="form-error" role="alert">{{ error }}</p>
      <p v-if="success" class="flash-success" role="status"><CheckCircle2 class="size-4" />{{ success }}</p>
    </section>
  </div>
</template>
