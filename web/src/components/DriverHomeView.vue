<script setup lang="ts">
import { computed } from "vue";

import { isPointDone, statusLabel } from "../status";
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
    <article v-if="activeRoute" class="card main-card">
      <h2>Рейс #{{ activeRoute.id }}</h2>
      <p><strong>Статус:</strong> {{ activeRoute.status }}</p>
      <p><strong>ТС:</strong> {{ activeRoute.number_auto || "—" }}</p>
      <p><strong>Точек:</strong> {{ activeRoute.points.length }}</p>

      <div v-if="activePoint" class="point-pill">
        <strong>Текущая точка:</strong>
        <span>#{{ activePoint.id }} · {{ statusLabel(activePoint.status) }}</span>
      </div>

      <button v-if="activeRoute.status === 'new'" class="primary" @click="emit('acceptActiveRoute')">Принять рейс</button>
      <button v-else class="primary" :disabled="!canAdvance || syncing" @click="emit('advanceActivePoint')">
        {{ actionLabel }}
      </button>
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
.hint {
  margin: 0;
  color: #94a3b8;
}
</style>
