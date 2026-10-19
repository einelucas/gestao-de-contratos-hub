export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuthStore();
  // Guarda a URL original (ex.: ?contrato=ID do link do e-mail) para voltar depois do login.
  if (!auth.user && !(await auth.loadUser())) return navigateTo({ path: "/login", query: { redirect: to.fullPath } });
  if (auth.user?.passwordChangeRequired && to.path !== "/alterar-senha") {
    return navigateTo("/alterar-senha");
  }
  if (!auth.user?.passwordChangeRequired && to.path === "/alterar-senha") {
    return navigateTo("/dashboard");
  }
});
