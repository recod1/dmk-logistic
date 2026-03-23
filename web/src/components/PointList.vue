<script setup lang="ts">
import { computed } from "vue";

import { nextStatus, statusLabel } from "../status";
import type { PointDto } from "../types";

const props = defineProps<{
  points: PointDto[];
  syncing: boolean;
}>();

const emit = defineEmits<{
  advanceStatus: [pointId: number];
}>();

const sortedPoints = computed(() => props.points.slice());

function canAdvance(point: PointDto): boolean {
  return nextStatus(point.status) !== null;
}
</script>

<template>
  <section class="list">
    <h2>Точки</h2>
    <article v-for="point in sortedPoints" :key="point.id" class="point-card">
      <div class="title-row">
        <strong>#{{ point.id }} · {{ point.type_point }}</strong>
        <span class="status">{{ statusLabel(point.status) }}</span>
      </div>
      <p>{{ point.place_point }}</p>
      <small>{{ point.date_point }}</small>
      <button :disabled="!canAdvance(point) || syncing" @click="emit('advanceStatus', point.id)">
        {{ canAdvance(point) ? "Следующий статус" : "Завершено" }}
      </button>
    </article>
  </section>
</template>

<style scoped>
.list {
  display: grid;
  gap: 0.7rem;
}
.point-card {
  padding: 0.8rem;
  border: 1px solid #374151;
  border-radius: 12px;
  background: #111827;
  display: grid;
  gap: 0.45rem;
}
.title-row {
  display: flex;
  justify-content: space-between;
  gap: 0.6rem;
}
.status {
  color: #93c5fd;
}
p,
small {
  margin: 0;
}
button {
  width: fit-content;
  background: #10b981;
  color: #052e1f;
  border: none;
  border-radius: 8px;
  padding: 0.45rem 0.7rem;
  font-weight: 600;
}
</style>

