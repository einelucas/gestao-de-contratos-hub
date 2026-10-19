<script setup lang="ts">
import { CheckCircle2, KeyRound, RefreshCw, ShieldCheck, UserPlus, Users } from "lucide-vue-next";
import type { UserListItem } from "~/types/api";

definePageMeta({ middleware: "admin" });

const api = useApi();
const users = ref<UserListItem[]>([]);
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const success = ref("");
const name = ref("");
const email = ref("");

async function loadUsers(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    users.value = (await api.get<{ items: UserListItem[] }>("/usuarios")).items;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível carregar os usuários.";
  } finally {
    loading.value = false;
  }
}

async function createUser(): Promise<void> {
  if (!name.value.trim() || !email.value.trim() || saving.value) return;
  saving.value = true;
  error.value = "";
  success.value = "";
  try {
    const response = await api.post<{ user: UserListItem }>("/usuarios", {
      name: name.value.trim(),
      email: email.value.trim(),
    });
    success.value = `${response.user.name} foi criado como administrador. A senha inicial é INP@2026.`;
    name.value = "";
    email.value = "";
    await loadUsers();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível criar o usuário.";
  } finally {
    saving.value = false;
  }
}

await loadUsers();
</script>

<template>
  <ModuleWorkspace
    eyebrow="Projetos e Arquitetura · Administração"
    title="Usuários"
    description="Cadastro interno de administradores do Hub. Esta página não aparece na navegação principal."
  >
    <div class="users-page-grid">
      <section class="surface user-create-card">
        <div class="surface-header">
          <div><h2><UserPlus class="size-5" />Novo usuário</h2><p>Todo novo usuário é criado com perfil de administrador.</p></div>
        </div>
        <form class="surface-body user-create-form" @submit.prevent="createUser">
          <label class="field"><span>Nome completo</span><input v-model="name" required maxlength="180" autocomplete="name" /></label>
          <label class="field"><span>E-mail de acesso</span><input v-model="email" required maxlength="320" type="email" autocomplete="email" /></label>
          <div class="temporary-password-note">
            <KeyRound class="size-5" />
            <div><strong>Senha inicial: INP@2026</strong><p>No primeiro acesso, o usuário será obrigado a cadastrar uma nova senha.</p></div>
          </div>
          <p v-if="error" class="form-error" role="alert">{{ error }}</p>
          <p v-if="success" class="flash-success" role="status"><CheckCircle2 class="size-4" />{{ success }}</p>
          <button type="submit" class="btn primary" :disabled="saving || !name.trim() || !email.trim()">
            <UserPlus class="size-4" />{{ saving ? 'Criando…' : 'Criar administrador' }}
          </button>
        </form>
      </section>

      <section class="surface users-list-card">
        <div class="surface-header">
          <div><h2><Users class="size-5" />Usuários cadastrados</h2><p>{{ users.length }} conta(s) no Hub</p></div>
          <button type="button" class="btn small" :disabled="loading" @click="loadUsers"><RefreshCw class="size-4" />Atualizar</button>
        </div>
        <div v-if="loading" class="users-list-state">Carregando usuários…</div>
        <div v-else-if="!users.length" class="users-list-state">Nenhum usuário cadastrado.</div>
        <div v-else class="users-table-wrap">
          <table class="users-table">
            <thead><tr><th>Usuário</th><th>Perfil</th><th>Acesso</th><th>Status</th></tr></thead>
            <tbody>
              <tr v-for="user in users" :key="user.id">
                <td><strong>{{ user.name }}</strong><span>{{ user.email }}</span></td>
                <td><span class="admin-role"><ShieldCheck class="size-3.5" />{{ user.role === 'ADMIN' ? 'Administrador' : user.role }}</span></td>
                <td>{{ user.authProvider === 'LOCAL' ? 'Senha local' : user.authProvider || 'Corporativo' }}</td>
                <td><span class="user-state" :class="{ pending: user.passwordChangeRequired, inactive: !user.active }">{{ !user.active ? 'Inativo' : user.passwordChangeRequired ? 'Troca de senha pendente' : 'Ativo' }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </ModuleWorkspace>
</template>

<style scoped>
.users-page-grid { display: grid; grid-template-columns: minmax(300px, 430px) minmax(0, 1fr); gap: 16px; align-items: start; }
.surface-header h2 { display: flex; align-items: center; gap: 8px; }
.user-create-form { display: grid; gap: 16px; }
.user-create-form .btn.primary { justify-self: start; }
.temporary-password-note { display: flex; gap: 11px; border: 1px solid #c9dbf2; border-radius: 11px; padding: 13px; background: #f2f7fd; color: #304f7e; }
.temporary-password-note svg { flex: none; margin-top: 1px; }
.temporary-password-note strong { font-size: 13px; }
.temporary-password-note p { margin: 3px 0 0; color: #5f6e82; font-size: 11.5px; line-height: 1.5; }
.users-list-state { padding: 50px 20px; text-align: center; color: #738196; font-size: 13px; }
.users-table-wrap { overflow-x: auto; }
.users-table { width: 100%; border-collapse: collapse; }
.users-table th, .users-table td { padding: 13px 16px; border-bottom: 1px solid #edf1f5; text-align: left; color: #526176; font-size: 12px; }
.users-table th { background: #f8fafc; color: #7a8798; font-size: 10px; text-transform: uppercase; letter-spacing: .04em; }
.users-table td:first-child { display: grid; gap: 2px; }
.users-table td strong { color: #26364d; font-size: 12.5px; }
.users-table td span:not(.admin-role, .user-state) { color: #7a8798; font-size: 11px; }
.admin-role, .user-state { display: inline-flex; align-items: center; gap: 5px; border-radius: 999px; padding: 4px 8px; background: #edf3fb; color: #304f7e; font-size: 10.5px; font-weight: 750; white-space: nowrap; }
.user-state { background: #edf7e9; color: #4a7b36; }
.user-state.pending { background: #fff5df; color: #9a6517; }
.user-state.inactive { background: #eef1f5; color: #667085; }
@media (max-width: 960px) { .users-page-grid { grid-template-columns: 1fr; } }
</style>
