import { hubAutocompleteDefaults } from "./config/vuetifyDefaults";

export default defineNuxtConfig({
  compatibilityDate: "2025-07-15",
  devtools: { enabled: true },
  // SPA: a sessão de homologação é um cookie HttpOnly que só o navegador envia; sem SSR
  // não há renderização no servidor tentando ler a API sem esse cookie.
  ssr: false,
  modules: ["@pinia/nuxt", "@nuxtjs/tailwindcss", "@nuxt/eslint", "vuetify-nuxt-module"],
  components: [{ path: "~/components", pathPrefix: false }],
  css: [
    "~/assets/css/vue.css",
    "~/assets/css/vuetify.css",
    "~/assets/css/vuetify-hub.css",
  ],
  vuetify: {
    moduleOptions: {
      styles: true,
      prefixComposables: ["useLayout"],
    },
    vuetifyOptions: {
      theme: {
        defaultTheme: "light",
        themes: {
          light: {
            dark: false,
            colors: {
              background: "#f4f5f7",
              surface: "#ffffff",
              primary: "#304f7e",
              "primary-darken-1": "#213758",
              secondary: "#6b7280",
              "secondary-darken-1": "#4b5563",
              accent: "#eaa239",
              error: "#c0392b",
              info: "#007cc5",
              success: "#609346",
              warning: "#eaa239",
            },
          },
        },
      },
      icons: { defaultSet: "mdi-svg" },
      locale: { locale: "pt", fallback: "en" },
      localeMessages: ["en", "pt"],
      defaults: {
        VBtn: {
          color: "secondary",
          variant: "outlined",
          rounded: "lg",
          elevation: 0,
        },
        VTextField: {
          variant: "outlined",
          density: "comfortable",
          hideDetails: "auto",
        },
        VTextarea: {
          variant: "outlined",
          density: "comfortable",
          hideDetails: "auto",
        },
        VSelect: {
          variant: "outlined",
          density: "comfortable",
          hideDetails: "auto",
        },
        VAutocomplete: hubAutocompleteDefaults,
      },
    },
  },
  runtimeConfig: {
    // Só no servidor Nuxt: para onde o proxy /api/** encaminha (sobrescreva com NUXT_API_PROXY_TARGET).
    apiProxyTarget: process.env.NUXT_API_PROXY_TARGET || "http://localhost:8000",
    public: {
      // Padrão "/api/v1": o navegador fala com o próprio Nuxt, que faz proxy para o FastAPI
      // (cookie de sessão de mesma origem). NUXT_PUBLIC_API_BASE_URL aponta direto para a API se preciso.
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || "/api/v1",
      oidcIssuer: process.env.NUXT_PUBLIC_OIDC_ISSUER || "",
      oidcClientId: process.env.NUXT_PUBLIC_OIDC_CLIENT_ID || "",
      oidcRedirectUri: process.env.NUXT_PUBLIC_OIDC_REDIRECT_URI || "http://localhost:3000/auth/callback",
      oidcPostLogoutRedirectUri:
        process.env.NUXT_PUBLIC_OIDC_POST_LOGOUT_REDIRECT_URI || "http://localhost:3000/login",
      devAuthEnabled: process.env.NUXT_PUBLIC_DEV_AUTH_ENABLED !== "false",
    },
  },
  typescript: {
    strict: true,
    typeCheck: true,
  },
  app: {
    head: {
      htmlAttrs: { lang: "pt-BR" },
      title: "Gestão de Contratos | Hub",
      meta: [
        { name: "description", content: "Gestão de Contratos no Hub corporativo." },
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        { name: "theme-color", content: "#304f7e" },
      ],
      link: [
        { rel: "icon", type: "image/png", href: "/brand/favicon.png" },
        { rel: "preconnect", href: "https://fonts.googleapis.com" },
        { rel: "preconnect", href: "https://fonts.gstatic.com", crossorigin: "anonymous" },
        {
          rel: "stylesheet",
          href: "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap",
        },
      ],
    },
  },
});
