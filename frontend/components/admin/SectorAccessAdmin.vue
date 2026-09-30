<script setup lang="ts">
import { CheckCircle2, Save, ShieldCheck } from "lucide-vue-next";
import type { Role, Sector, UserListItem, UserSectorPermission } from "~/types/api";

/**
 * Permissões por setor (somente ADMIN). Mesmo desenho do UnitAccessAdmin do Painel:
 * o perfil define o que o usuário pode fazer; esta tela define em quais setores.
 * Usa só os endpoints auditados GET/PUT /usuarios/{id}/setores.
 */
const ROLE_LABEL: Record<Role, string> = { VIEWER: "Visualizador", ANALYST: "Analista", ADMIN: "Administrador" };

interface Row {
  sectorId: string;
  sectorName: string;
  canView: boolean;
  canEdit: boolean;
}

const api = useApi();
const users = ref<UserListItem[]>([]);
const sectors = ref<Sector[]>([]);
const selectedUserId = ref("");
const rows = ref<Row[]>([]);
const original = ref("");
const loading = ref(true);
const loadingUser = ref(false);
const saving = ref(false);
const error = ref("");
const success = ref("");

const selectedUser = computed(() => users.value.find((user) => user.id === selectedUserId.value) ?? null);
const isAdmin = computed(() => selectedUser.value?.role === "ADMIN");
const isViewer = computed(() => selectedUser.value?.role === "VIEWER");
const dirty = computed(() => Boolean(selectedUser.value) && JSON.stringify(rows.value) !== original.value);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [userResult, sectorResult] = await Promise.all([
      api.get<{ items: UserListItem[] }>("/usuarios"),
      api.get<{ items: Sector[] }>("/setores"),
    ]);
    users.value = userResult.items.filter((user) => user.active);
    sectors.value = sectorResult.items;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível carregar usuários e setores.";
  } finally {
    loading.value = false;
  }
}

function applyPermissions(items: UserSectorPermission[]): void {
  const bySector = new Map(items.map((item) => [item.sectorId, item]));
  rows.value = sectors.value.map((sector) => {
    const permission = bySector.get(sector.id);
    return {
      sectorId: sector.id,
      sectorName: sector.name,
      canView: Boolean(permission?.canView || permission?.canEdit),
      canEdit: Boolean(permission?.canEdit),
    };
  });
  original.value = JSON.stringify(rows.value);
}

async function selectUser(userId: string): Promise<void> {
  if (dirty.value && !window.confirm("Há alterações não salvas. Descartar?")) return;
  selectedUserId.value = userId;
  success.value = "";
  error.value = "";
  rows.value = [];
  if (!userId || isAdmin.value) return;
  loadingUser.value = true;
  try {
    const response = await api.get<{ items: UserSectorPermission[] }>(`/usuarios/${userId}/setores`);
    applyPermissions(response.items);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível carregar as permissões.";
  } finally {
    loadingUser.value = false;
  }
}

function toggleView(row: Row): void {
  row.canView = !row.canView;
  if (!row.canView) row.canEdit = false; // sem visualizar não há como editar
}

function toggleEdit(row: Row): void {
  row.canEdit = !row.canEdit;
  if (row.canEdit) row.canView = true; // editar implica visualizar
}

async function save(): Promise<void> {
  if (!selectedUser.value || isAdmin.value) return;
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    const response = await api.put<{ items: UserSectorPermission[] }>(`/usuarios/${selectedUser.value.id}/setores`, {
      items: rows.value
        .filter((row) => row.canView || row.canEdit)
        // VIEWER nunca edita: não grava configuração sem efeito.
        .map((row) => ({ sectorId: row.sectorId, canView: true, canEdit: isViewer.value ? false : row.canEdit })),
    });
    applyPermissions(response.items);
    success.value = "Permissões salvas. A listagem de contratos do usuário já reflete a mudança.";
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível salvar as permissões.";
  } finally {
    saving.value = false;
  }
}

onMounted(load);
onBeforeRouteLeave(() => !dirty.value || window.confirm("Há alterações não salvas. Descartar?"));
</script>

<template>
  <section class="surface admin-card">
    <header class="admin-card-head">
      <div>
        <h2>Permissões por setor</h2>
        <p>O perfil define o que o usuário pode fazer; aqui você define em quais setores.</p>
      </div>
      <button v-if="selectedUser && !isAdmin" type="button" class="btn primary" :disabled="saving || !dirty" @click="save">
        <Save class="size-4" />{{ saving ? "Salvando…" : "Salvar alterações" }}
      </button>
    </header>

    <p v-if="loading" class="history-empty">Carregando usuários…</p>
    <template v-else>
      <p v-if="!users.length" class="history-empty">Nenhum usuário ativo cadastrado.</p>
      <label v-else class="inline-field admin-filter">
        <span>Usuário</span>
        <select :value="selectedUserId" @change="selectUser(($event.target as HTMLSelectElement).value)">
          <option value="">Selecione um usuário</option>
          <option v-for="user in users" :key="user.id" :value="user.id">{{ user.name }} · {{ user.email }} · {{ ROLE_LABEL[user.role] }}</option>
        </select>
      </label>

      <template v-if="selectedUser">
        <p class="role-line">Perfil: <span class="pill tone-info">{{ ROLE_LABEL[selectedUser.role] }}</span></p>
        <p v-if="isAdmin" class="admin-global"><ShieldCheck class="size-4" />Administrador — acesso a todos os setores. Não depende de permissões por setor.</p>
        <p v-else-if="loadingUser" class="history-empty">Carregando permissões…</p>
        <template v-else>
          <p v-if="isViewer" class="form-hint">Visualizadores só consultam; a edição não se aplica a este perfil.</p>
          <p v-if="!sectors.length" class="history-empty">Nenhum setor cadastrado.</p>
          <table v-else class="admin-table">
            <thead><tr><th>Setor</th><th>Pode visualizar</th><th>Pode editar</th></tr></thead>
            <tbody>
              <tr v-for="row in rows" :key="row.sectorId">
                <td>{{ row.sectorName }}</td>
                <td><input type="checkbox" :checked="row.canView" :aria-label="`Visualizar ${row.sectorName}`" @change="toggleView(row)" /></td>
                <td>
                  <input
                    type="checkbox"
                    :checked="row.canEdit && !isViewer"
                    :disabled="isViewer"
                    :aria-label="`Editar ${row.sectorName}`"
                    @change="toggleEdit(row)"
                  />
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="dirty" class="form-hint warning-text">Alterações não salvas.</p>
          <p v-if="!rows.some((row) => row.canView)" class="form-hint">Sem nenhum setor marcado, o usuário não vê contratos.</p>
        </template>
      </template>
    </template>
    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <p v-if="success" class="flash-success" role="status"><CheckCircle2 class="size-4" />{{ success }}</p>
  </section>
</template>
