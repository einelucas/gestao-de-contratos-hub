<script setup lang="ts">
import { VProgressLinear } from "vuetify/components";

const routeLoading = ref(false);
const nuxtApp = useNuxtApp();
const removePageStartHook = nuxtApp.hook("page:start", () => {
  routeLoading.value = true;
});
const removePageFinishHook = nuxtApp.hook("page:finish", () => {
  routeLoading.value = false;
});
const removeErrorHook = nuxtApp.hook("vue:error", () => {
  routeLoading.value = false;
});
onBeforeUnmount(() => {
  removePageStartHook();
  removePageFinishHook();
  removeErrorHook();
});
</script>

<template>
  <VProgressLinear
    v-if="routeLoading"
    class="app-route-progress"
    color="primary"
    height="3"
    indeterminate
    aria-label="Carregando página"
  />
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>

<style>
.app-route-progress {
  position: fixed !important;
  inset: 0 0 auto;
  z-index: 9999;
}
</style>
