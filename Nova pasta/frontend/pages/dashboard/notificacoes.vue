<script setup lang="ts">
definePageMeta({ middleware: "admin" });
</script>

<template>
  <ModuleWorkspace
    eyebrow="Projetos e Arquitetura · Contratos"
    title="Envios de alertas"
    description="Prévia, execução manual e histórico dos alertas de vencimento enviados por e-mail."
  >
    <NotificationAdmin />
  </ModuleWorkspace>
</template>
