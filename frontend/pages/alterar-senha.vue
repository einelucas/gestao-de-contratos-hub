<script setup lang="ts">
import { Eye, EyeOff, KeyRound, LogOut, ShieldCheck } from "lucide-vue-next";

definePageMeta({ middleware: "auth", publicLayout: true });

const { store } = useAuth();
const currentPassword = ref("");
const newPassword = ref("");
const confirmation = ref("");
const showPasswords = ref(false);
const saving = ref(false);
const error = ref("");

const rules = computed(() => ({
  length: newPassword.value.length >= 8,
  upper: /[A-Z]/.test(newPassword.value),
  lower: /[a-z]/.test(newPassword.value),
  number: /\d/.test(newPassword.value),
  special: /[^A-Za-z0-9]/.test(newPassword.value),
  different: Boolean(newPassword.value) && newPassword.value !== "INP@2026",
  matches: Boolean(confirmation.value) && newPassword.value === confirmation.value,
}));
const valid = computed(() => Object.values(rules.value).every(Boolean));

async function submit(): Promise<void> {
  if (!currentPassword.value || !valid.value || saving.value) return;
  saving.value = true;
  error.value = "";
  try {
    await store.changePassword(currentPassword.value, newPassword.value);
    await navigateTo("/dashboard", { replace: true });
  } catch (cause) {
    const status = (cause as { status?: number }).status;
    error.value = status === 401
      ? "A senha atual está incorreta."
      : cause instanceof Error ? cause.message : "Não foi possível alterar a senha.";
  } finally {
    saving.value = false;
  }
}

async function logout(): Promise<void> {
  await store.logoutSession();
  await navigateTo("/login", { replace: true });
}
</script>

<template>
  <div class="password-change-page">
    <img src="/brand/usina.jpg" alt="" class="password-change-background" />
    <section class="password-change-card" role="dialog" aria-modal="true" aria-labelledby="password-change-title">
      <div class="password-change-icon"><KeyRound class="size-6" /></div>
      <span class="required-badge"><ShieldCheck class="size-3.5" />Primeiro acesso</span>
      <h1 id="password-change-title">Crie uma nova senha</h1>
      <p>Olá, {{ store.user?.name }}. Por segurança, substitua a senha inicial antes de acessar o Hub.</p>

      <form @submit.prevent="submit">
        <label><span>Senha atual</span><input v-model="currentPassword" :type="showPasswords ? 'text' : 'password'" autocomplete="current-password" required /></label>
        <label><span>Nova senha</span><input v-model="newPassword" :type="showPasswords ? 'text' : 'password'" autocomplete="new-password" required /></label>
        <label><span>Confirme a nova senha</span><input v-model="confirmation" :type="showPasswords ? 'text' : 'password'" autocomplete="new-password" required /></label>
        <button type="button" class="password-visibility" @click="showPasswords = !showPasswords"><component :is="showPasswords ? EyeOff : Eye" class="size-4" />{{ showPasswords ? 'Ocultar senhas' : 'Mostrar senhas' }}</button>

        <ul class="password-rules" aria-label="Requisitos da nova senha">
          <li :class="{ valid: rules.length }">Mínimo de 8 caracteres</li>
          <li :class="{ valid: rules.upper && rules.lower }">Letras maiúscula e minúscula</li>
          <li :class="{ valid: rules.number }">Pelo menos um número</li>
          <li :class="{ valid: rules.special }">Pelo menos um caractere especial</li>
          <li :class="{ valid: rules.different }">Diferente da senha inicial</li>
          <li :class="{ valid: rules.matches }">As senhas coincidem</li>
        </ul>

        <p v-if="error" class="login-error" role="alert">{{ error }}</p>
        <button type="submit" class="btn primary password-submit" :disabled="saving || !currentPassword || !valid">
          <KeyRound class="size-4" />{{ saving ? 'Salvando…' : 'Salvar nova senha' }}
        </button>
      </form>
      <button type="button" class="password-logout" :disabled="saving" @click="logout"><LogOut class="size-4" />Sair e voltar ao login</button>
    </section>
  </div>
</template>

<style scoped>
.password-change-page { position: relative; display: grid; min-height: 100vh; place-items: center; padding: 24px; overflow: hidden; }
.password-change-background { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; filter: saturate(.75); }
.password-change-page::after { content: ''; position: absolute; inset: 0; background: rgba(17, 31, 50, .64); }
.password-change-card { position: relative; z-index: 1; width: min(480px, 100%); border-radius: 18px; padding: 30px; background: #fff; box-shadow: 0 28px 80px rgba(0, 0, 0, .28); }
.password-change-icon { display: grid; width: 48px; height: 48px; place-items: center; border-radius: 13px; background: #edf3fb; color: #304f7e; }
.required-badge { display: inline-flex; align-items: center; gap: 5px; margin-top: 18px; border-radius: 999px; padding: 5px 9px; background: #fff5df; color: #9a6517; font-size: 10.5px; font-weight: 800; text-transform: uppercase; letter-spacing: .04em; }
h1 { margin: 12px 0 6px; color: #20324a; font-size: 25px; }
.password-change-card > p { margin: 0 0 20px; color: #68778b; font-size: 13px; line-height: 1.55; }
form { display: grid; gap: 13px; }
label { display: grid; gap: 6px; }
label span { color: #56657a; font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .03em; }
input { min-height: 42px; border: 1px solid #d8e0ea; border-radius: 9px; padding: 8px 11px; outline: none; }
input:focus { border-color: #6687b8; box-shadow: 0 0 0 3px rgba(48, 79, 126, .12); }
.password-visibility, .password-logout { display: inline-flex; align-items: center; gap: 6px; justify-self: start; border: 0; padding: 0; background: transparent; color: #526b8f; font-size: 11.5px; font-weight: 700; }
.password-rules { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px 12px; margin: 2px 0; padding: 12px 12px 12px 28px; border-radius: 10px; background: #f7f9fc; color: #7a8798; font-size: 10.5px; }
.password-rules li.valid { color: #4a7b36; font-weight: 700; }
.password-submit { width: 100%; }
.password-logout { margin-top: 18px; color: #6b7280; }
@media (max-width: 520px) { .password-change-card { padding: 23px 19px; } .password-rules { grid-template-columns: 1fr; } }
</style>
