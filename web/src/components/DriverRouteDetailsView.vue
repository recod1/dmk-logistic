<script setup lang="ts">
import { computed } from "vue";

import { statusLabel } from "../status";
import type { RouteDto } from "../types";

const props = defineProps<{
  route: RouteDto;
  syncing: boolean;
}>();

const emit = defineEmits<{
  back: [];
  accept: [];
  advancePoint: [pointId: number];
}>();

const firstIncompletePoint = computed(() =>
  props.route.points.find((point) => point.status !== "success") ?? null
);

function actionLabel(status: string): string {
  if (status === "new") {
    return "Выехал на точку";
  }
  if (status === "process") {
    return "Зарегистрировался";
  }
  if (status === "registration") {
    return "Поставил на ворота";
  }
  if (status === "load") {
    return "Забрал документы";
  }
  if (status === "docs") {
    return "Выехал с точки";
  }
  return "Завершено";
}

function canAdvancePoint(pointId: number): boolean {
  const point = props.route.points.find((item) => item.id === pointId);
  if (!point) {
    return false;
  }
  return point.status !== "success" && props.route.status === "process";
}
</script>

<template>
  <section class="details-wrap">
    <header class="head-row">
      <button class="ghost" @click="emit('back')">← К списку рейсов</button>
      <h1>Рейс #{{ route.id }}</h1>
    </header>

    <article class="card">
      <p><strong>Статус рейса:</strong> {{ route.status }}</p>
      <p><strong>ТС:</strong> {{ route.number_auto || "—" }}</p>
      <p><strong>Прицеп:</strong> {{ route.trailer_number || "—" }}</p>
      <button v-if="route.status === 'new'" class="primary" @click="emit('accept')">Принять рейс</button>
      <button
        v-else-if="firstIncompletePoint"
        class="primary"
        :disabled="syncing || !canAdvancePoint(firstIncompletePoint.id)"
        @click="emit('advancePoint', firstIncompletePoint.id)"
      >
        {{ actionLabel(firstIncompletePoint.status) }}
      </button>
    </article>

    <article class="card">
      <h2>Точки</h2>
      <div class="points">
        <div v-for="point in route.points" :key="point.id" class="point-card">
          <div class="row">
            <strong>#{{ point.id }} · {{ point.type_point }}</strong>
            <span class="chip">{{ statusLabel(point.status) }}</span>
          </div>
          <p>{{ point.place_point }}</p>
          <small>{{ point.date_point }}</small>
          <div class="meta">
            <span>Одометр: {{ point.odometer || "—" }}</span>
            <span>Координаты: {{ point.coordinates?.lat ?? "—" }}, {{ point.coordinates?.lng ?? "—" }}</span>
          </div>
          <button class="ghost" :disabled="!canAdvancePoint(point.id) || syncing" @click="emit('advancePoint', point.id)">
            {{ actionLabel(point.status) }}
          </button>
        </div>
      </div>
    </article>
  </section>
</template>

<style scoped>
.details-wrap {
  display: grid;
  gap: 0.8rem;
}
.head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.points {
  display: grid;
  gap: 0.55rem;
}
.point-card {
  border: 1px solid #334155;
  border-radius: 12px;
  background: #0f172a;
  padding: 0.65rem;
  display: grid;
  gap: 0.35rem;
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.chip {
  border-radius: 999px;
  background: #1f2937;
  padding: 0.1rem 0.55rem;
  font-size: 0.78rem;
}
.meta {
  display: grid;
  gap: 0.15rem;
  color: #94a3b8;
  font-size: 0.82rem;
}
p,
small {
  margin: 0;
}
.primary {
  border: none;
  border-radius: 10px;
  background: #2563eb;
  color: #fff;
  padding: 0.52rem 0.78rem;
}
.ghost {
  width: auto;
  border: 1px solid #334155;
  border-radius: 10px;
  background: transparent;
  color: #bfdbfe;
  padding: 0.42rem 0.62rem;
}
</style>
