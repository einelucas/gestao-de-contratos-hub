<script setup lang="ts">
import { formatCurrencyInput, parseCurrencyInput } from "~/utils/contracts";

/**
 * Campo de moeda pt-BR: exibe "1.234,56" e mantém o model como número.
 * Enquanto o campo está em foco, o texto digitado é preservado para não
 * atrapalhar a edição; ao sair, volta ao formato completo.
 */
const model = defineModel<number>({ default: 0 });
const props = defineProps<{
  required?: boolean;
  placeholder?: string;
  ariaLabel?: string;
}>();

const focused = ref(false);
const draft = ref("");

const display = computed(() =>
  focused.value ? draft.value : formatCurrencyInput(model.value ?? 0),
);

watch(model, (value) => {
  if (!focused.value) draft.value = formatCurrencyInput(value ?? 0);
});

function onFocus(event: FocusEvent): void {
  focused.value = true;
  draft.value = formatCurrencyInput(model.value ?? 0);
  nextTick(() => (event.target as HTMLInputElement | null)?.select());
}

function onInput(event: Event): void {
  const input = event.target as HTMLInputElement;
  draft.value = input.value;
  model.value = parseCurrencyInput(input.value);
}

function onBlur(): void {
  focused.value = false;
  draft.value = formatCurrencyInput(model.value ?? 0);
}
</script>

<template>
  <div class="currency-input">
    <span class="currency-input-prefix" aria-hidden="true">R$</span>
    <input
      :value="display"
      type="text"
      inputmode="decimal"
      autocomplete="off"
      :required="props.required"
      :placeholder="props.placeholder ?? '0,00'"
      :aria-label="props.ariaLabel"
      @focus="onFocus"
      @input="onInput"
      @blur="onBlur"
    />
  </div>
</template>
