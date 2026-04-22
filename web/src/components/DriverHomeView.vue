<script setup lang="ts">
import { computed } from "vue";

import { isPointDone, mapsSearchUrl, routeStatusLabel, statusLabel } from "../status";
import type { DriverRouteListItem, RouteDto } from "../types";

const props = defineProps<{
  activeRoute: RouteDto | null;
  activeRouteSummary: DriverRouteListItem | null;
  hasAssignedRoutes: boolean;
  syncMessage: string;
  syncing: boolean;
}>();

const emit = defineEmits<{
  openRoutes: [];
  openActiveRoute: [];
  acceptActiveRoute: [];
  advanceActivePoint: [];
}>();

const activePoint = computed(() =>
  props.activeRoute?.points.find((point) => !isPointDone(point.status)) ?? props.activeRoute?.points[0] ?? null
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

const canAdvance = computed(() => {
  if (!props.activeRoute || props.activeRoute.status !== "process") {
    return false;
  }
  return Boolean(activePoint.value && !isPointDone(activePoint.value.status));
});
</script>

<template>
  <section class="driver-shell">
    <article v-if="activeRoute" class="card main-card clickable-card" @click="emit('openActiveRoute')">
      <div class="title-row">
        <h2>Рейс #{{ activeRoute.id }}</h2>
        <span class="status-chip">{{ routeStatusLabel(activeRoute.status) }}</span>
      </div>
      <p class="route-meta">
        <span v-if="activeRoute.number_auto"><strong>ТС:</strong> {{ activeRoute.number_auto }}</span>
        <span v-if="activeRoute.trailer_number"><strong>Прицеп:</strong> {{ activeRoute.trailer_number }}</span>
        <span v-if="activeRoute.registration_number"><strong>Рег. №:</strong> {{ activeRoute.registration_number }}</span>
        <span v-if="activeRoute.temperature"><strong>Темп.:</strong> {{ activeRoute.temperature }}</span>
      </p>
      <p><strong>Точек:</strong> {{ activeRoute.points.length }}</p>

      <div v-if="activePoint" class="point-pill">
        <strong>Текущая точка: {{ statusLabel(activePoint.status) }}</strong>
        <span><strong>Тип:</strong> {{ activePoint.type_point === "unloading" ? "Выгрузка" : "Загрузка" }}</span>
        <span v-if="activePoint.place_point"
          ><strong>Адрес:</strong>
          <a
            class="maps-link"
            :href="mapsSearchUrl(activePoint.place_point)"
            target="_blank"
            rel="noopener noreferrer"
            @click.stop
            >{{ activePoint.place_point }}</a
          ></span
        >
        <span v-else><strong>Адрес:</strong> —</span>
        <span><strong>Плановое время:</strong> {{ activePoint.date_point || "—" }} {{ activePoint.point_time || "" }}</span>
      </div>

      <button v-if="activeRoute.status === 'new'" class="primary" @click.stop="emit('acceptActiveRoute')">Принять рейс</button>
      <template v-else>
        <button class="primary" :disabled="!canAdvance || syncing" @click.stop="emit('advanceActivePoint')">
          {{ actionLabel }}
        </button>
      </template>
      <button class="secondary" @click.stop="emit('openActiveRoute')">Открыть всю информацию о рейсе</button>
      <p class="hint">{{ syncMessage }}</p>
    </article>

    <article v-else-if="hasAssignedRoutes" class="card main-card">
      <h2>Рейс назначен</h2>
      <p>У вас есть назначенный рейс, который ещё не принят.</p>
      <button class="primary" @click="emit('openRoutes')">Открыть список рейсов</button>
    </article>

    <article v-else class="card main-card">
      <h2>Назначенных рейсов нет</h2>
      <p>Когда логист или администратор назначит рейс, он появится здесь.</p>
      <button class="primary" @click="emit('openRoutes')">Открыть список рейсов</button>
    </article>
  </section>
</template>

<style scoped>
.driver-shell {
  display: grid;
  gap: 0.85rem;
}
.main-card {
  display: grid;
  gap: 0.6rem;
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
}
.status-chip {
  border-radius: 999px;
  background: #1f2937;
  padding: 0.12rem 0.55rem;
  font-size: 0.78rem;
  color: #e2e8f0;
}
.clickable-card {
  cursor: pointer;
}
.route-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  margin: 0;
}
.point-pill {
  display: grid;
  gap: 0.2rem;
  padding: 0.55rem;
  border-radius: 10px;
  background: #0f172a;
  border: 1px solid #334155;
}
.primary {
  border: none;
  border-radius: 10px;
  background: #2563eb;
  color: #fff;
  padding: 0.55rem 0.8rem;
}
.secondary {
  border: 1px solid #334155;
  border-radius: 10px;
  background: transparent;
  color: #bfdbfe;
  padding: 0.5rem 0.75rem;
}
.hint {
  margin: 0;
  color: #94a3b8;
}
.maps-link {
  color: #38bdf8;
  text-decoration: underline;
  word-break: break-word;
}
</style>
