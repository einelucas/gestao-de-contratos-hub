<script setup lang="ts">
definePageMeta({ middleware: "admin" });
</script>

<template>
  <ModuleWorkspace eyebrow="Projetos e Arquitetura · Administração" title="Permissões por setor" description="Em quais setores cada usuário pode consultar e editar contratos.">
    <SectorAccessAdmin />
  </ModuleWorkspace>
</template>
