<script setup>
import { computed } from "vue";

const props = defineProps({
  chartResult: {
    type: Object,
    default: null,
  },
});

const palette = ["#58d7c4", "#ffb65c", "#ef7d5c", "#5c8fff", "#8fd86f"];

const barData = computed(() => {
  const labels = props.chartResult?.chart_option?.xAxis?.data || [];
  const values = props.chartResult?.chart_option?.series?.[0]?.data || [];
  const maxValue = Math.max(...values, 1);
  return labels.map((label, index) => ({
    label,
    value: Number(values[index] || 0),
    width: `${(Number(values[index] || 0) / maxValue) * 100}%`,
  }));
});

const lineSvg = computed(() => {
  const labels = props.chartResult?.chart_option?.xAxis?.data || [];
  const values = props.chartResult?.chart_option?.series?.[0]?.data || [];
  const width = 420;
  const height = 220;
  const padding = 24;
  const maxValue = Math.max(...values, 1);
  const stepX = labels.length > 1 ? (width - padding * 2) / (labels.length - 1) : 0;

  const points = values.map((value, index) => {
    const x = padding + stepX * index;
    const y =
      height - padding - (Number(value || 0) / maxValue) * (height - padding * 2);
    return {
      x,
      y,
      label: labels[index],
    };
  });

  return {
    width,
    height,
    padding,
    points,
    polyline: points.map((point) => `${point.x},${point.y}`).join(" "),
  };
});

const pieData = computed(() => {
  const data = props.chartResult?.chart_option?.series?.[0]?.data || [];
  const total = data.reduce((sum, item) => sum + Number(item.value || 0), 0) || 1;
  let cursor = 0;

  const segments = data.map((item, index) => {
    const start = cursor;
    const percent = (Number(item.value || 0) / total) * 100;
    cursor += percent;
    return {
      color: palette[index % palette.length],
      name: item.name,
      value: item.value,
      start,
      end: cursor,
      percent: `${percent.toFixed(1)}%`,
    };
  });

  return {
    segments,
    gradient: `conic-gradient(${segments
      .map((segment) => `${segment.color} ${segment.start}% ${segment.end}%`)
      .join(", ")})`,
  };
});
</script>

<template>
  <div v-if="!props.chartResult || !props.chartResult.chart_needed" class="empty-state">
    当前还没有可展示的图表。
  </div>

  <div v-else-if="props.chartResult.chart_type === 'pie'" class="pie-chart">
    <div class="pie-ring" :style="{ background: pieData.gradient }"></div>
    <div class="pie-legend">
      <div v-for="segment in pieData.segments" :key="segment.name" class="legend-item">
        <span>
          <span class="legend-swatch" :style="{ background: segment.color }"></span>
          {{ segment.name }}
        </span>
        <span>{{ segment.value }} ({{ segment.percent }})</span>
      </div>
    </div>
  </div>

  <svg
    v-else-if="props.chartResult.chart_type === 'line'"
    class="line-chart-svg"
    :viewBox="`0 0 ${lineSvg.width} ${lineSvg.height}`"
  >
    <line
      class="line-chart-axis"
      :x1="lineSvg.padding"
      :y1="lineSvg.height - lineSvg.padding"
      :x2="lineSvg.width - lineSvg.padding"
      :y2="lineSvg.height - lineSvg.padding"
    />
    <line
      class="line-chart-axis"
      :x1="lineSvg.padding"
      :y1="lineSvg.padding"
      :x2="lineSvg.padding"
      :y2="lineSvg.height - lineSvg.padding"
    />
    <polyline class="line-chart-path" :points="lineSvg.polyline"></polyline>
    <g v-for="point in lineSvg.points" :key="`${point.label}-${point.x}`">
      <circle class="line-chart-point" :cx="point.x" :cy="point.y" r="4.5"></circle>
      <text
        :x="point.x"
        :y="lineSvg.height - 8"
        fill="#a3bcc4"
        font-size="11"
        text-anchor="middle"
      >
        {{ point.label }}
      </text>
    </g>
  </svg>

  <div v-else class="chart-bars">
    <div v-for="row in barData" :key="row.label" class="bar-row">
      <span class="bar-label">{{ row.label }}</span>
      <div class="bar-track">
        <div class="bar-fill" :style="{ width: row.width }"></div>
      </div>
      <span class="bar-value">{{ row.value }}</span>
    </div>
  </div>
</template>
