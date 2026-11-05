<script setup lang="ts">
import { Clock } from "lucide-vue-next";
import type { DeadlineBucket } from "~/types/api";
import { formatNumber } from "~/utils/format";

/** Faixas de prazo dos contratos não finalizados (estrutura do card do Painel de Equipamentos). */
const props = defineProps<{ deadlines: DeadlineBucket[]; total?: number; regularization?: number }>();
const emit = defineEmits<{ select: [key: DeadlineBucket["key"]]; regularization: [] }>();

type VisibleDeadlineKey = Exclude<DeadlineBucket["key"], "withoutDate">;
type Tone = "critical" | "warning" | "safe";

const TONE: Record<VisibleDeadlineKey, Tone> = {
  overdue: "critical",
  today: "critical",
  next7: "warning",
  next30: "warning",
  next60: "safe",
  next90: "safe",
  later: "safe",
};

// "Sem data" não entra nos gráficos de prazo: só contratos com vigência têm faixa.
const visibleDeadlines = computed(() =>
  props.deadlines.filter(
    (item): item is DeadlineBucket & { key: VisibleDeadlineKey } => item.key !== "withoutDate",
  ),
);
const total = computed(
  () => props.total ?? visibleDeadlines.value.reduce((sum, item) => sum + item.count, 0),
);
const byTone = computed(() => {
  const acc: Record<Tone, number> = { critical: 0, warning: 0, safe: 0 };
  for (const item of visibleDeadlines.value) acc[TONE[item.key]] += item.count;
  return acc;
});
const percentage = (value: number) => (total.value ? (value / total.value) * 100 : 0);
const max = computed(() => Math.max(1, ...visibleDeadlines.value.map((item) => item.count)));
</script>

<template>
  <DashboardCard title="Situação de prazos" subtitle="Vencimentos pendentes e contratos em regularização." :icon="Clock">
    <div class="deadlines">
      <div class="deadlines-summary">
        <div><strong>{{ formatNumber(total, 0) }}</strong><span>contratos em aberto</span></div>
        <div class="critical"><strong>{{ formatNumber(byTone.critical, 0) }}</strong><span>vencidos ou vencem hoje</span></div>
        <div class="warning"><strong>{{ formatNumber(byTone.warning, 0) }}</strong><span>vencem em até 30 dias</span></div>
      </div>
      <div class="deadlines-track" role="img" :aria-label="`${byTone.critical} críticos, ${byTone.warning} em atenção, ${byTone.safe} com prazo seguro`">
        <span v-for="tone in (['critical', 'warning', 'safe'] as const)" :key="tone" :class="`part-${tone}`" :style="{ width: `${percentage(byTone[tone])}%` }" />
      </div>
      <ul class="deadlines-rows">
        <li v-for="item in visibleDeadlines" :key="item.key">
          <button type="button" @click="emit('select', item.key)">
            <span class="dot" :class="`part-${TONE[item.key]}`" />
            <span class="label">{{ item.label }}</span>
            <span class="bar"><span :class="`part-${TONE[item.key]}`" :style="{ width: `${(item.count / max) * 100}%` }" /></span>
            <strong>{{ item.count }}</strong>
          </button>
        </li>
      </ul>
      <button v-if="regularization" type="button" class="regularization-callout" @click="emit('regularization')">
        <span class="regularization-callout-value">{{ formatNumber(regularization, 0) }}</span>
        <span class="regularization-callout-text">
          <strong>Em regularização</strong>
          <small>recorte sobre os prazos — não soma ao total</small>
        </span>
      </button>
    </div>
  </DashboardCard>
</template>

<style scoped>
.deadlines { display: grid; gap: 14px; }
.deadlines-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.deadlines-summary > div { border: 1px solid #e4e9f0; border-radius: 9px; padding: 10px 12px; background: #fafbfd; }
.deadlines-summary strong { display: block; color: #20324a; font-size: 22px; line-height: 1.1; }
.deadlines-summary span { color: #78869a; font-size: 10.5px; font-weight: 700; }
.deadlines-summary .critical strong { color: #a83128; }
.deadlines-summary .warning strong { color: #a76b11; }
.deadlines-track { display: flex; height: 10px; overflow: hidden; border-radius: 999px; background: #eef1f5; }
.deadlines-track span { height: 100%; }
.part-critical { background: #c0392b; }
.part-warning { background: #eaa239; }
.part-safe { background: #609346; }
.deadlines-rows { display: grid; gap: 2px; margin: 0; padding: 0; list-style: none; }
.deadlines-rows button { display: grid; grid-template-columns: 10px 130px 1fr 34px; align-items: center; gap: 10px; width: 100%; border: 0; border-radius: 8px; background: transparent; padding: 6px 4px; text-align: left; color: #31445c; font-size: 12px; }
.deadlines-rows button:hover { background: #f5f8fb; }
.dot { width: 9px; height: 9px; border-radius: 999px; }
.bar { height: 6px; border-radius: 999px; background: #eef1f5; overflow: hidden; }
.bar span { display: block; height: 100%; border-radius: 999px; }
.deadlines-rows strong { text-align: right; color: #20324a; }
.regularization-callout { display: flex; align-items: center; gap: 12px; width: 100%; border: 1px solid #d7e4f5; border-radius: 9px; background: #f3f8fe; padding: 10px 12px; text-align: left; color: #31445c; }
.regularization-callout:hover { background: #eaf3fd; }
.regularization-callout-value { font-size: 22px; font-weight: 750; line-height: 1; color: #2f6cae; }
.regularization-callout-text { display: grid; gap: 2px; }
.regularization-callout-text strong { font-size: 12px; color: #2f4b6e; }
.regularization-callout-text small { font-size: 10px; font-weight: 600; color: #718096; }
</style>
