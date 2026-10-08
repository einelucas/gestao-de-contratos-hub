<script setup lang="ts">
definePageMeta({ middleware: "admin" });
</script>

<template>
  <section>
    <NuxtLink class="admin-back" to="/dashboard">← Voltar ao painel</NuxtLink>
    <ReferenceSectionHeader
      title="Registro de Atividades"
      description="Trilha de eventos administrativos e alterações registradas pelo sistema."
    />
    <AuditViewer />
  </section>
</template>
