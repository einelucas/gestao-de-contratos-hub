<script setup lang="ts">
import { Clock } from "lucide-vue-next";
import type { DeadlineBucket } from "~/types/api";
import { formatNumber } from "~/utils/format";

/** Faixas de prazo dos contratos não finalizados (estrutura do card do Painel de Equipamentos). */
const props = defineProps<{ deadlines: DeadlineBucket[] }>();
const emit = defineEmits<{ select: [key: DeadlineBucket["key"]] }>();

const TONE: Record<DeadlineBucket["key"], "critical" | "warning" | "safe" | "muted"> = {
  overdue: "critical",
  today: "critical",
  next7: "warning",
  next30: "warning",
  next60: "safe",
  next90: "safe",
  later: "safe",
  withoutDate: "muted",
};

const total = computed(() => props.deadlines.reduce((sum, item) => sum + item.count, 0));
const byTone = computed(() => {
  const acc = { critical: 0, warning: 0, safe: 0, muted: 0 };
  for (const item of props.deadlines) acc[TONE[item.key]] += item.count;
  return acc;
});
const percentage = (value: number) => (total.value ? (value / total.value) * 100 : 0);
const max = computed(() => Math.max(1, ...props.deadlines.map((item) => item.count)));
</script>

<template>
  <DashboardCard title="Situação de prazos" subtitle="Contratos não finalizados por faixa de vencimento." :icon="Clock">
    <div class="deadlines">
      <div class="deadlines-summary">
        <div><strong>{{ formatNumber(total, 0) }}</strong><span>contratos em aberto</span></div>
        <div class="critical"><strong>{{ formatNumber(byTone.critical, 0) }}</strong><span>vencidos ou vencem hoje</span></div>
        <div class="warning"><strong>{{ formatNumber(byTone.warning, 0) }}</strong><span>vencem em até 30 dias</span></div>
      </div>
      <div class="deadlines-track" role="img" :aria-label="`${byTone.critical} críticos, ${byTone.warning} em atenção, ${byTone.safe} com prazo seguro, ${byTone.muted} sem data`">
        <span v-for="tone in (['critical', 'warning', 'safe', 'muted'] as const)" :key="tone" :class="`part-${tone}`" :style="{ width: `${percentage(byTone[tone])}%` }" />
      </div>
      <ul class="deadlines-rows">
        <li v-for="item in deadlines" :key="item.key">
          <button type="button" @click="emit('select', item.key)">
            <span class="dot" :class="`part-${TONE[item.key]}`" />
            <span class="label">{{ item.label }}</span>
            <span class="bar"><span :class="`part-${TONE[item.key]}`" :style="{ width: `${(item.count / max) * 100}%` }" /></span>
            <strong>{{ item.count }}</strong>
          </button>
        </li>
      </ul>
    </div>
  </DashboardCard>
</template>

<style scoped>
.deadlines { display: grid; gap: 14px; }
.deadlines-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.deadlines-summary > div { border: 1px solid #e7edf4; border-radius: 11px; padding: 10px 12px; background: #fbfcfe; }
.deadlines-summary strong { display: block; color: #20324a; font-size: 22px; line-height: 1.1; }
.deadlines-summary span { color: #78869a; font-size: 10.5px; font-weight: 700; }
.deadlines-summary .critical strong { color: #a83128; }
.deadlines-summary .warning strong { color: #a76b11; }
.deadlines-track { display: flex; height: 10px; overflow: hidden; border-radius: 999px; background: #eef1f5; }
.deadlines-track span { height: 100%; }
.part-critical { background: #c0392b; }
.part-warning { background: #eaa239; }
.part-safe { background: #609346; }
.part-muted { background: #bdbfc1; }
.deadlines-rows { display: grid; gap: 2px; margin: 0; padding: 0; list-style: none; }
.deadlines-rows button { display: grid; grid-template-columns: 10px 130px 1fr 34px; align-items: center; gap: 10px; width: 100%; border: 0; border-radius: 8px; background: transparent; padding: 6px 4px; text-align: left; color: #31445c; font-size: 12px; }
.deadlines-rows button:hover { background: #f5f8fb; }
.dot { width: 9px; height: 9px; border-radius: 999px; }
.bar { height: 6px; border-radius: 999px; background: #eef1f5; overflow: hidden; }
.bar span { display: block; height: 100%; border-radius: 999px; }
.deadlines-rows strong { text-align: right; color: #20324a; }
</style>
