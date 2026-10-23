<script setup lang="ts">
import { computed } from "vue";

import MapsAddressLink from "./MapsAddressLink.vue";
import { lateKindClass, lateReasonLines, pointLateKind } from "../lateArrival";
import { isPointDone, routeStatusLabel, statusLabel } from "../status";
import { plannedScheduleDisplay } from "../plannedTime";
import type { DriverRouteListItem, DriverShiftListItem, RouteDto } from "../types";

const props = defineProps<{
  activeRoute: RouteDto | null;
  activeRouteSummary: DriverRouteListItem | null;
  hasAssignedRoutes: boolean;
  syncMessage: string;
  syncing: boolean;
  activeShift?: DriverShiftListItem | null;
  shiftBusy?: boolean;
  hasProblem?: boolean;
}>();

const emit = defineEmits<{
  openRoutes: [];
  openActiveRoute: [];
  acceptActiveRoute: [];
  advanceActivePoint: [];
  reportProblem: [];
  toggleShift: [];
}>();

const activePoint = computed(
  () => props.activeRoute?.points.find((point) => !isPointDone(point.status)) ?? props.activeRoute?.points[0] ?? null
);

const actionLabel = computed(() => {
  if (!activePoint.value) {
    return "Все точки завершены";
  }
  const status = activePoint.value.status;
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
  return "Все точки завершены";
});

const homeLateKind = computed(() => (activePoint.value ? pointLateKind(activePoint.value) : ""));

const canAdvance = computed(() => {
  if (!props.activeRoute || props.activeRoute.status !== "process") {
    return false;
  }
  return Boolean(activePoint.value && !isPointDone(activePoint.value.status));
});
</script>

<template>
  <section class="driver-shell">
    <button class="shift-btn" type="button" :disabled="shiftBusy" @click="emit('toggleShift')">
      {{ activeShift ? "Закончить Вахту" : "Начать Вахту" }}
    </button>
    <article
      v-if="activeRoute"
      class="card main-card clickable-card"
      :class="[lateKindClass(homeLateKind), { 'has-problem': hasProblem }]"
      @click="emit('openActiveRoute')"
    >
      <div class="title-row">
        <h2>Рейс #{{ activeRoute.id }}</h2>
        <span class="status-chip">{{ routeStatusLabel(activeRoute.status) }}</span>
      </div>
      <p class="route-meta">
        <span v-if="activeRoute.number_auto"><strong>ТС</strong> {{ activeRoute.number_auto }}</span>
        <span v-if="activeRoute.trailer_number"><strong>Прицеп</strong> {{ activeRoute.trailer_number }}</span>
        <span v-if="activeRoute.registration_number"><strong>Рег. №</strong> {{ activeRoute.registration_number }}</span>
        <span v-if="activeRoute.temperature"><strong>Темп.</strong> {{ activeRoute.temperature }}</span>
      </p>
      <p class="points-count">Точек: {{ activeRoute.points.length }}</p>

      <div v-if="activePoint" class="point-pill" :class="lateKindClass(homeLateKind)">
        <span class="pill-k">Текущая точка</span>
        <strong>{{ statusLabel(activePoint.status) }}</strong>
        <span class="pill-type">{{ activePoint.type_point === "unloading" ? "Выгрузка" : "Загрузка" }}</span>
        <span v-if="activePoint.point_name" class="pill-org">{{ activePoint.point_name }}</span>
        <span v-if="activePoint.place_point" class="pill-addr">
          <MapsAddressLink :address="activePoint.place_point" />
        </span>
        <span v-else class="plan">Адрес не указан</span>
        <span class="plan">План: {{ plannedScheduleDisplay(activePoint.date_point, activePoint.point_time) || "—" }}</span>
        <span v-if="activePoint.estimated_arrival" class="plan">Ориентировочно: {{ activePoint.estimated_arrival }}</span>
        <div v-if="lateReasonLines(activePoint.late_reason).length" class="late-reason">
          <span v-for="(line, idx) in lateReasonLines(activePoint.late_reason)" :key="idx">{{ line }}</span>
        </div>
      </div>

      <button v-if="activeRoute.status === 'new'" class="primary" @click.stop="emit('acceptActiveRoute')">Принять рейс</button>
      <div v-else class="status-row">
        <button class="primary" :disabled="!canAdvance" @click.stop="emit('advanceActivePoint')">
          {{ actionLabel }}
        </button>
        <button class="problem-mini" type="button" @click.stop="emit('reportProblem')">Проблема</button>
      </div>
      <button class="secondary" @click.stop="emit('openActiveRoute')">Открыть всю информацию о рейсе</button>
    </article>

    <article v-else-if="hasAssignedRoutes" class="card main-card empty-state">
      <h2>Рейс назначен</h2>
      <p>Есть назначенный рейс, который ещё не принят. Откройте список и примите его.</p>
      <button class="primary" @click="emit('openRoutes')">Открыть список рейсов</button>
    </article>

    <article v-else class="card main-card empty-state">
      <h2>Назначенных рейсов нет</h2>
      <p>Когда логист или администратор назначит рейс, он появится здесь.</p>
      <button class="primary" @click="emit('openRoutes')">Открыть список рейсов</button>
    </article>
  </section>
</template>

<style scoped>
@import "../lateHighlight.css";
.driver-shell {
  display: grid;
  gap: 0.85rem;
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
}
.main-card {
  display: grid;
  gap: 0.7rem;
  padding: 1.05rem;
  border: 1px solid #3d5270;
  border-radius: 18px;
  background: #152033;
  box-shadow: var(--shadow-sm);
}
.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.title-row h2 {
  margin: 0;
  letter-spacing: -0.02em;
}
.status-chip {
  border-radius: 999px;
  background: var(--primary-soft);
  border: 1px solid rgba(96, 165, 250, 0.28);
  padding: 0.18rem 0.65rem;
  font-size: 0.78rem;
  color: #dbeafe;
  font-weight: 600;
}
.clickable-card {
  cursor: pointer;
}
.route-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
  margin: 0;
}
.route-meta span {
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.75);
  border: 1px solid var(--border);
  padding: 0.22rem 0.55rem;
  font-size: 0.82rem;
  color: #cbd5e1;
}
.route-meta strong {
  color: var(--text-muted);
  font-weight: 600;
  margin-right: 0.25rem;
}
.points-count {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.9rem;
}
.point-pill {
  display: grid;
  gap: 0.22rem;
  padding: 0.8rem 0.85rem;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.8);
  border: 1px solid var(--border);
}
.pill-k {
  font-size: 0.72rem;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-label);
}
.point-pill strong {
  font-size: 1.02rem;
  color: var(--text-heading);
}
.pill-type {
  color: var(--text-body);
  font-size: 0.9rem;
}
.pill-org {
  font-weight: 600;
}
.pill-addr {
  margin-top: 0.12rem;
}
.plan {
  color: var(--text-muted);
  font-size: 0.84rem;
}
.late-reason {
  display: grid;
  gap: 0.18rem;
  color: #fecaca;
  font-size: 0.84rem;
}
.points-count {
  margin: 0;
  color: var(--text-muted);
  font-size: 0.84rem;
}
.shift-btn {
  min-height: 46px;
  border: none;
  border-radius: 12px;
  font-weight: 700;
  background: linear-gradient(180deg, #0ea5e9, #0284c7);
  color: #fff;
}
.shift-btn:disabled {
  opacity: 0.55;
}
.primary,
.secondary {
  min-height: 46px;
  border-radius: 12px;
  font-weight: 650;
}
.status-row {
  display: flex;
  align-items: stretch;
  gap: 0.45rem;
}
.status-row .primary {
  flex: 1 1 auto;
}
.problem-mini {
  flex: 0 0 auto;
  min-width: 4.4rem;
  padding: 0 0.55rem;
  border: none;
  border-radius: 12px;
  background: #b91c1c;
  color: #fff;
  font-size: 0.78rem;
  font-weight: 700;
}
.primary {
  border: none;
  background: linear-gradient(180deg, #3b82f6, #2563eb);
  color: #fff;
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.24);
}
.secondary {
  border: 1px solid #60a5fa;
  background: #1e3a5f;
  color: #e0f2fe;
}
.empty-state p {
  margin: 0;
  color: var(--text-muted);
  line-height: 1.45;
}
.maps-link {
  color: var(--accent);
  text-decoration: none;
  word-break: break-word;
  border-bottom: 1px solid rgba(56, 189, 248, 0.35);
}
</style>
