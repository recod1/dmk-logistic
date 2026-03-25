<script setup lang="ts">
import { computed } from "vue";

import { statusLabel } from "../status";
import type { DriverRouteListItem, RouteDto } from "../types";

const props = defineProps<{
  activeRoute: RouteDto | null;
  activeRouteSummary: DriverRouteListItem | null;
  hasAssignedRoutes: boolean;
  syncMessage: string;
  syncing: boolean;
  showMenu: boolean;
  unreadCount: number;
}>();

const emit = defineEmits<{
  toggleMenu: [];
  openNotifications: [];
  openRoutes: [];
  openSalary: [];
  openRepair: [];
  logout: [];
  acceptActiveRoute: [];
  advanceActivePoint: [];
}>();

const activePoint = computed(() =>
  props.activeRoute?.points.find((point) => point.status !== "success") ?? props.activeRoute?.points[0] ?? null
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
  if (status === "docs") {
    return "Выехал с точки";
  }
  return "Все точки завершены";
});

const canAdvance = computed(() => {
  if (!props.activeRoute || props.activeRoute.status !== "process") {
    return false;
  }
  return Boolean(activePoint.value && activePoint.value.status !== "success");
});
</script>

<template>
  <section class="driver-shell">
    <header class="driver-header">
      <button class="icon-btn" @click="emit('toggleMenu')">☰</button>
      <h1>Главная</h1>
      <button class="icon-btn bell-btn" @click="emit('openNotifications')">
        🔔
        <span v-if="unreadCount > 0" class="dot" />
      </button>
    </header>

    <aside v-if="showMenu" class="side-menu">
      <button @click="emit('openRoutes')">Рейсы</button>
      <button @click="emit('openSalary')">Зарплата</button>
      <button @click="emit('openRepair')">Ремонт</button>
      <button @click="emit('logout')">Выход</button>
    </aside>

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
      <h2>Активных рейсов нет</h2>
      <p>Когда администратор назначит рейс, он появится на главной.</p>
      <button class="primary" @click="emit('openRoutes')">К списку рейсов</button>
    </article>
  </section>
</template>

<style scoped>
.driver-shell {
  display: grid;
  gap: 0.85rem;
}
.driver-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
}
.icon-btn {
  width: 42px;
  height: 42px;
  border: 1px solid #334155;
  border-radius: 12px;
  background: #0f172a;
  color: #fff;
  font-size: 1.05rem;
}
.bell-btn {
  position: relative;
}
.dot {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #ef4444;
}
.side-menu {
  display: grid;
  gap: 0.45rem;
  padding: 0.75rem;
  border-radius: 12px;
  border: 1px solid #334155;
  background: #111827;
}
.side-menu button {
  text-align: left;
  border: 1px solid #334155;
  border-radius: 10px;
  background: #0f172a;
  color: #fff;
  padding: 0.55rem 0.65rem;
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
