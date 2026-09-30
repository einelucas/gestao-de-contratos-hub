<script setup lang="ts">
definePageMeta({ middleware: "admin" });
</script>

<template>
  <ModuleWorkspace eyebrow="Projetos e Arquitetura · Administração" title="Equipes de notificação" description="Equipes que recebem os alertas de vencimento de cada setor.">
    <TeamsAdmin />
  </ModuleWorkspace>
</template>
