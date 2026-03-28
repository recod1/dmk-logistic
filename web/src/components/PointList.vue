<script setup lang="ts">
import { computed } from "vue";

import {
  canRevertPointStatus,
  isPointDone,
  mapsSearchUrl,
  nextStatus,
  nextStatusLabel,
  statusLabel
} from "../status";
import type { PointDto } from "../types";

const props = defineProps<{
  points: PointDto[];
  routeStatus: string;
  syncing: boolean;
}>();

const emit = defineEmits<{
  advanceStatus: [pointId: number];
  revertStatus: [pointId: number];
}>();

const sortedPoints = computed(() => props.points.slice());

const firstIncompletePointId = computed(
  () => props.points.find((point) => !isPointDone(point.status))?.id ?? null
);

function canAdvance(point: PointDto): boolean {
  if (firstIncompletePointId.value !== point.id) {
    return false;
  }
  return nextStatus(point.status) !== null;
}

function nextLabel(point: PointDto): string {
  const label = nextStatusLabel(point.status);
  return label ? `Следующий статус: ${label}` : "Завершено";
}

function showRevert(point: PointDto): boolean {
  return (
    firstIncompletePointId.value === point.id &&
    props.routeStatus === "process" &&
    canRevertPointStatus(point.status)
  );
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
      <p v-if="point.place_point" class="addr">
        <a class="maps-link" :href="mapsSearchUrl(point.place_point)" target="_blank" rel="noopener noreferrer">{{
          point.place_point
        }}</a>
      </p>
      <p v-else class="addr-muted">Адрес не указан</p>
      <small>{{ point.date_point }}</small>
      <small v-if="point.point_name || point.point_contacts || point.point_time || point.point_note" class="point-meta">
        {{ point.point_name || "Без названия" }}
        <span v-if="point.point_contacts"> · {{ point.point_contacts }}</span>
        <span v-if="point.point_time"> · {{ point.point_time }}</span>
      </small>
      <small v-if="point.point_note" class="point-note">{{ point.point_note }}</small>
      <div class="btn-row">
        <button :disabled="!canAdvance(point) || syncing" @click="emit('advanceStatus', point.id)">
          {{ nextLabel(point) }}
        </button>
        <button
          v-if="showRevert(point)"
          class="revert"
          type="button"
          :disabled="syncing"
          @click="emit('revertStatus', point.id)"
        >
          Вернуть предыдущий статус
        </button>
      </div>
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
  flex-wrap: wrap;
  gap: 0.6rem;
}
.status {
  color: #93c5fd;
}
.point-meta {
  color: #9ca3af;
}
.point-note {
  color: #d1d5db;
}
.addr {
  margin: 0;
}
.addr-muted {
  margin: 0;
  color: #64748b;
  font-size: 0.85rem;
}
.maps-link {
  color: #38bdf8;
  text-decoration: underline;
  word-break: break-word;
}
p,
small {
  margin: 0;
}
.btn-row {
  display: grid;
  gap: 0.45rem;
}
button {
  width: 100%;
  background: #10b981;
  color: #052e1f;
  border: none;
  border-radius: 8px;
  padding: 0.45rem 0.7rem;
  font-weight: 600;
}
button.revert {
  background: #451a03;
  color: #fed7aa;
  border: 1px solid #78350f;
  font-weight: 500;
}
</style>
