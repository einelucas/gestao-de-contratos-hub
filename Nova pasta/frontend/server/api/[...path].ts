/**
 * Proxy do Nuxt para o FastAPI: o navegador só conversa com a origem do frontend,
 * então o cookie de sessão (HttpOnly) é de primeira parte e o CORS não entra em jogo.
 * Não expõe nada além da própria API (Mailpit e outros serviços locais ficam de fora).
 */
export default defineEventHandler((event) => {
  const target = useRuntimeConfig().apiProxyTarget.replace(/\/$/, "");
  const ip = getRequestIP(event, { xForwardedFor: true });
  return proxyRequest(event, `${target}${event.path}`, {
    headers: ip ? { "x-forwarded-for": ip } : {},
  });
});
