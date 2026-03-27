<script setup lang="ts">
import { computed } from "vue";

import {
  canRevertPointStatus,
  isPointDone,
  mapsSearchUrl,
  nextStatus,
  routeStatusLabel,
  statusLabel
} from "../status";
import type { RouteDto } from "../types";

const props = defineProps<{
  route: RouteDto;
  activeRouteId: string | null;
  syncing: boolean;
  canAcceptRoute: boolean;
}>();

const emit = defineEmits<{
  back: [];
  advancePoint: [pointId: number];
  revertPoint: [pointId: number];
  acceptRoute: [];
}>();

const firstIncompletePoint = computed(
  () => props.route.points.find((point) => !isPointDone(point.status)) ?? null
);

const isAcceptedCurrentRoute = computed(
  () => props.route.status === "process" && props.route.id === props.activeRouteId
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
  return "Завершено";
}

function canAdvancePoint(pointId: number): boolean {
  const point = props.route.points.find((item) => item.id === pointId);
  if (!point) {
    return false;
  }
  return !isPointDone(point.status) && props.route.status === "process";
}

function showRevert(pointId: number): boolean {
  const point = props.route.points.find((item) => item.id === pointId);
  if (!point) {
    return false;
  }
  return isAcceptedCurrentRoute.value && canRevertPointStatus(point.status);
}
</script>

<template>
  <section class="details-wrap">
    <header class="head-row">
      <button class="ghost" type="button" @click="emit('back')">← К списку рейсов</button>
    </header>
    <h1 class="route-title">Рейс #{{ route.id }}</h1>

    <div class="scroll-area">
      <article class="card">
        <p><strong>Статус рейса:</strong> {{ routeStatusLabel(route.status) }}</p>
        <p><strong>ТС:</strong> {{ route.number_auto || "—" }}</p>
        <p><strong>Прицеп:</strong> {{ route.trailer_number || "—" }}</p>
        <p><strong>Темп.:</strong> {{ route.temperature || "—" }}</p>
        <p><strong>Диспетчер:</strong> {{ route.dispatcher_contacts || "—" }}</p>
        <p v-if="!isAcceptedCurrentRoute && route.status === 'process'" class="note">
          Изменение статусов доступно только для принятого текущего рейса.
        </p>
      </article>

      <article class="card">
        <h2>Точки</h2>
        <div class="points">
          <div v-for="point in route.points" :key="point.id" class="point-card">
            <div class="row">
              <strong>{{ point.type_point === "unloading" ? "Выгрузка" : "Загрузка" }}</strong>
              <span class="chip">{{ statusLabel(point.status) }}</span>
            </div>
            <p v-if="point.place_point" class="addr">
              <a class="maps-link" :href="mapsSearchUrl(point.place_point)" target="_blank" rel="noopener noreferrer">{{
                point.place_point
              }}</a>
            </p>
            <small>{{ point.date_point }} {{ point.point_time || "" }}</small>
            <div class="meta">
              <span>Выезд: {{ point.departure_time || point.time_accepted || "—" }}</span>
              <span>Регистрация: {{ point.registration_time || point.time_registration || "—" }}</span>
              <span>Ворота: {{ point.gate_time || point.time_put_on_gate || "—" }}</span>
              <span>Документы: {{ point.docs_time || point.time_docs || "—" }}</span>
            </div>
          </div>
        </div>
      </article>
    </div>

    <footer class="dock">
      <button
        v-if="canAcceptRoute"
        type="button"
        class="primary wide"
        :disabled="syncing"
        @click="emit('acceptRoute')"
      >
        Принять рейс
      </button>

      <template v-if="isAcceptedCurrentRoute">
        <p v-if="firstIncompletePoint && nextStatus(firstIncompletePoint.status)" class="dock-hint">
          Текущая точка: этап «{{ statusLabel(firstIncompletePoint.status) }}»
        </p>
        <div v-for="point in route.points" :key="`act-${point.id}`" class="dock-actions">
          <button
            v-if="canAdvancePoint(point.id)"
            type="button"
            class="primary wide"
            :disabled="syncing"
            @click="emit('advancePoint', point.id)"
          >
            {{ actionLabel(point.status) }}
          </button>
          <button
            v-if="showRevert(point.id)"
            type="button"
            class="ghost wide"
            :disabled="syncing"
            @click="emit('revertPoint', point.id)"
          >
            Вернуть предыдущий статус
          </button>
        </div>
      </template>
    </footer>
  </section>
</template>

<style scoped>
.details-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  min-height: calc(100vh - 6rem);
}
.route-title {
  margin: 0;
  font-size: 1.1rem;
  line-height: 1.25;
  overflow-wrap: anywhere;
}
.head-row {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 0.5rem;
}
.scroll-area {
  flex: 1;
  display: grid;
  gap: 0.75rem;
  min-height: 0;
}
.card {
  border: 1px solid #334155;
  border-radius: 12px;
  background: #0f172a;
  padding: 0.65rem 0.85rem;
}
.card h2 {
  margin: 0 0 0.5rem;
  font-size: 1rem;
}
.points {
  display: grid;
  gap: 0.55rem;
}
.point-card {
  border: 1px solid #334155;
  border-radius: 12px;
  background: #111827;
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
.addr {
  margin: 0;
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
.dock {
  position: sticky;
  bottom: 0;
  padding: 0.65rem 0;
  margin-top: auto;
  background: linear-gradient(180deg, transparent, #020617 35%);
  display: grid;
  gap: 0.5rem;
}
.dock-hint {
  margin: 0;
  color: #94a3b8;
  font-size: 0.86rem;
}
.dock-actions {
  display: grid;
  gap: 0.4rem;
}
.primary.wide,
.ghost.wide {
  width: 100%;
}
.primary {
  border: none;
  border-radius: 10px;
  background: #2563eb;
  color: #fff;
  padding: 0.52rem 0.78rem;
}
.ghost {
  border: 1px solid #78350f;
  border-radius: 10px;
  background: #451a03;
  color: #fed7aa;
  padding: 0.42rem 0.62rem;
}
.note {
  margin: 0.35rem 0 0;
  color: #94a3b8;
  font-size: 0.88rem;
}
</style>
