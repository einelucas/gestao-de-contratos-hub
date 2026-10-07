<script setup lang="ts">
import { LogIn, ShieldCheck } from "lucide-vue-next";
import type { Role } from "~/types/api";

definePageMeta({ publicLayout: true });

const route = useRoute();
const { store, login, devAuthEnabled } = useAuth();
const loading = ref(false);
const checking = ref(true);
const error = ref("");
const username = ref("");
const password = ref("");

/** Só volta para caminhos internos (evita redirecionamento aberto para outro site). */
const redirectTo = computed(() => {
  const target = typeof route.query.redirect === "string" ? route.query.redirect : "";
  return target.startsWith("/") && !target.startsWith("//") && !target.startsWith("/login") ? target : "/dashboard";
});

async function detectMode(): Promise<void> {
  checking.value = true;
  await store.loadProvider();
  if (store.providerError) {
    checking.value = false;
    return;
  }
  // Sessão ainda válida: não mostra o login de novo.
  if (await store.loadUser()) {
    await navigateTo(redirectTo.value, { replace: true });
    return;
  }
  checking.value = false;
}

onMounted(detectMode);

async function submitPassword() {
  if (!username.value.trim() || !password.value) {
    error.value = "Informe usuário e senha.";
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    await store.loginPassword(username.value.trim(), password.value);
    password.value = "";
    await navigateTo(redirectTo.value, { replace: true });
  } catch (cause) {
    const status = (cause as { status?: number }).status;
    error.value =
      status === 429
        ? "Muitas tentativas. Aguarde alguns minutos e tente novamente."
        : status === 401
          ? "Usuário ou senha inválidos."
          : "Não foi possível entrar agora. Tente novamente.";
    password.value = "";
  } finally {
    loading.value = false;
  }
}

async function oidc() {
  loading.value = true;
  error.value = "";
  try {
    await login();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Não foi possível iniciar o login.";
  } finally {
    loading.value = false;
  }
}

async function dev(role: Role) {
  loading.value = true;
  error.value = "";
  try {
    await store.loginDev(role);
    await navigateTo(redirectTo.value);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Falha na autenticação de desenvolvimento.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <img src="/brand/usina.jpg" alt="" class="login-background" />
    <section class="login-card">
      <img src="/brand/logo-inpasa.png" alt="Inpasa" class="login-logo" />
      <p class="login-hub">Hub · Projetos e Arquitetura</p>
      <h1>Gestão de Contratos</h1>

      <p v-if="checking" class="login-checking">Verificando sessão…</p>

      <!-- Sem resposta da API: não adivinha o modo (nada de botões de SSO/Dev por engano). -->
      <template v-else-if="store.providerError">
        <p class="login-error" role="alert">Não foi possível conectar ao servidor. Verifique se a API está no ar.</p>
        <button type="button" class="btn login-submit" @click="detectMode">Tentar novamente</button>
      </template>

      <!-- Login temporário de homologação (AUTH_PROVIDER=homologation) -->
      <template v-else-if="store.provider === 'homologation'">
        <span class="homolog-badge"><ShieldCheck class="size-3.5" />Ambiente de Homologação</span>
        <form class="login-form" @submit.prevent="submitPassword">
          <label>
            <span>Usuário ou e-mail</span>
            <input v-model="username" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" required />
          </label>
          <label>
            <span>Senha</span>
            <input v-model="password" name="password" type="password" autocomplete="current-password" required />
          </label>
          <button type="submit" class="btn primary login-submit" :disabled="loading">
            <LogIn class="size-4" />{{ loading ? "Entrando…" : "Entrar" }}
          </button>
        </form>
      </template>

      <!-- SSO corporativo (AUTH_PROVIDER=keycloak) -->
      <template v-else>
        <p>Acesse com sua conta corporativa.</p>
        <button class="btn primary login-submit" :disabled="loading" @click="oidc">
          {{ loading ? "Aguarde…" : "Entrar com conta corporativa" }}
        </button>
        <template v-if="devAuthEnabled">
          <div class="my-4 flex items-center gap-3 text-xs text-slate-400">
            <span class="h-px flex-1 bg-slate-200" />Desenvolvimento<span class="h-px flex-1 bg-slate-200" />
          </div>
          <div class="grid grid-cols-3 gap-2">
            <button class="btn small" :disabled="loading" @click="dev('VIEWER')">Viewer</button>
            <button class="btn small" :disabled="loading" @click="dev('ANALYST')">Analyst</button>
            <button class="btn small" :disabled="loading" @click="dev('ADMIN')">Admin</button>
          </div>
        </template>
      </template>
      <p v-if="error" class="login-error" role="alert">{{ error }}</p>
    </section>
  </div>
</template>
