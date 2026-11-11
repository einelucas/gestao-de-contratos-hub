<script setup lang="ts">
import { Smile } from "lucide-vue-next";

const props = defineProps<{ disabled?: boolean }>();
const emit = defineEmits<{ pick: [emoji: string] }>();

const choices = [
  { emoji: "✅", label: "Concluído" },
  { emoji: "👍", label: "Aprovado" },
  { emoji: "👌", label: "De acordo" },
  { emoji: "⚠️", label: "Atenção" },
  { emoji: "❌", label: "Pendente ou rejeitado" },
  { emoji: "❓", label: "Dúvida" },
  { emoji: "🔎", label: "Em análise" },
  { emoji: "👀", label: "Acompanhar" },
  { emoji: "📌", label: "Importante" },
  { emoji: "📋", label: "Lista de tarefas" },
  { emoji: "📄", label: "Documento" },
  { emoji: "📎", label: "Anexo" },
  { emoji: "✍️", label: "Assinatura" },
  { emoji: "📅", label: "Data" },
  { emoji: "⏳", label: "Aguardando" },
  { emoji: "⏰", label: "Prazo" },
  { emoji: "📨", label: "Mensagem enviada" },
  { emoji: "☎️", label: "Contato por telefone" },
  { emoji: "🔄", label: "Em andamento" },
  { emoji: "🔔", label: "Lembrete" },
  { emoji: "🙂", label: "Sorriso" },
  { emoji: "🙌", label: "Comemoração" },
  { emoji: "🤝", label: "Acordo" },
  { emoji: "🎉", label: "Parabéns" },
];

const panelId = useId();
const open = ref(false);
const trigger = ref<HTMLButtonElement | null>(null);
const panel = ref<HTMLDivElement | null>(null);

watch(() => props.disabled, (disabled) => {
  if (disabled) open.value = false;
});

async function toggle(): Promise<void> {
  open.value = !open.value;
  if (open.value) {
    await nextTick();
    panel.value?.querySelector("button")?.focus();
  }
}

function closeOnEscape(event: KeyboardEvent): void {
  if (!open.value) return;
  event.stopPropagation();
  open.value = false;
  trigger.value?.focus();
}

function pick(emoji: string): void {
  open.value = false;
  emit("pick", emoji);
}
</script>

<template>
  <div class="emoji-picker" @keydown.esc="closeOnEscape">
    <button
      ref="trigger"
      type="button"
      class="emoji-trigger"
      :disabled="disabled"
      :aria-expanded="open"
      :aria-controls="panelId"
      @click="toggle"
    >
      <Smile :size="14" aria-hidden="true" />
      Emojis
    </button>
    <div v-show="open" :id="panelId" ref="panel" class="emoji-panel" role="group" aria-label="Escolher emoji">
      <button
        v-for="choice in choices"
        :key="choice.emoji"
        type="button"
        class="emoji-option"
        :title="choice.label"
        :aria-label="choice.label"
        @click="pick(choice.emoji)"
      >
        {{ choice.emoji }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.emoji-picker {
  display: contents;
}

.emoji-trigger {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 7px 9px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #536982;
  font: inherit;
  font-size: 10px;
  font-weight: 650;
  cursor: pointer;
}

.emoji-trigger:hover:not(:disabled),
.emoji-trigger[aria-expanded="true"],
.emoji-option:hover {
  background: #e8eff8;
  color: #304f7e;
}

.emoji-trigger:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.emoji-panel {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(36px, 1fr));
  gap: 4px;
  order: 1;
  flex-basis: 100%;
  padding: 8px;
  border: 1px solid #dce3ec;
  border-radius: 9px;
  background: #fff;
}

.emoji-option {
  min-height: 36px;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  font-size: 19px;
  cursor: pointer;
}

.emoji-trigger:focus-visible,
.emoji-option:focus-visible {
  outline: 2px solid #304f7e;
  outline-offset: 1px;
}
</style>
