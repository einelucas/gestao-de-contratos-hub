<script setup lang="ts">
import { formatNumber } from "~/utils/format";

interface ProgressItem {
  label: string;
  value: number;
  sublabel?: string;
}

const props = withDefaults(
  defineProps<{
    items: ProgressItem[];
    target?: number | null;
    suffix?: string;
    okColor?: string;
    badColor?: string;
    emptyMessage?: string;
  }>(),
  {
    target: null,
    suffix: "%",
    okColor: "#609346",
    badColor: "#cc5121",
    emptyMessage: "Sem dados disponíveis.",
  },
);

const hoveredLabel = ref<string | null>(null);
const formatValue = (value: number) => formatNumber(value, props.suffix === "%" ? 1 : 2);

const isOk = (value: number) => props.target === null || value >= props.target;
const colorFor = (value: number) => (isOk(value) ? props.okColor : props.badColor);
const widthFor = (value: number) => `${Math.min(100, Math.max(0, value))}%`;
</script>

<template>
  <div class="unit-progress-bars">
    <template v-if="items.length">
      <div
        v-for="item in items"
        :key="item.label"
        class="urow"
        :class="{ 'urow--hovered': hoveredLabel === item.label }"
        @mouseenter="hoveredLabel = item.label"
        @mouseleave="hoveredLabel = null"
      >
        <div class="uname">
          {{ item.label }}
          <span v-if="item.sublabel" class="uname-sub">{{ item.sublabel }}</span>
        </div>

        <div class="utrack">
          <div
            class="ufill"
            :style="{
              width: widthFor(item.value),
              background: colorFor(item.value),
            }"
          />
        </div>

        <div class="uval" :style="{ color: colorFor(item.value) }">
          {{ formatValue(item.value) }}{{ suffix }}
        </div>
      </div>
    </template>

    <p v-else class="ps">{{ emptyMessage }}</p>
  </div>
</template>

<style scoped>
.unit-progress-bars {
  width: 100%;
}

.urow {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.urow:last-child {
  margin-bottom: 0;
}

.uname {
  display: flex;
  width: 170px;
  flex-shrink: 0;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 7px;
  color: #20324a;
  font-size: 13.44px;
  font-weight: 700;
  line-height: 1.3;
}

.uname-sub {
  color: #9aa4b2;
  font-size: 10.5px;
  font-weight: 500;
}

.utrack {
  height: 10px;
  flex: 1;
  overflow: hidden;
  border-radius: 999px;
  background: #edf1f6;
}

.ufill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.6s, filter 0.15s ease;
}

.uval {
  width: 54px;
  flex-shrink: 0;
  text-align: right;
  font-size: 13.44px;
  font-weight: 800;
}

.ps {
  margin: 0;
  color: #778398;
  font-size: 12px;
}

.urow--hovered .ufill {
  filter: brightness(1.08);
}

@media (max-width: 660px) {
  .uname {
    width: 115px;
  }
}
</style>
