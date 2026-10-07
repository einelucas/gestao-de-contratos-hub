export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuthStore();
  if (!auth.user && !(await auth.loadUser())) return navigateTo({ path: "/login", query: { redirect: to.fullPath } });
  if (auth.user?.role !== "ADMIN") return navigateTo("/dashboard");
});
