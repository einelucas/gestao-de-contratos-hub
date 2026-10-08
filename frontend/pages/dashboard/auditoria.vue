<script setup lang="ts">
definePageMeta({ middleware: "auth" });
</script>

<template>
  <ModuleWorkspace
    eyebrow="Projetos e Arquitetura · Contratos"
    title="Auditoria"
    description="Acompanhe e conduza a regularização dos contratos vencidos."
  >
    <ContractAuditKanban />
  </ModuleWorkspace>
</template>
