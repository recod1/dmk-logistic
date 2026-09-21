<script setup lang="ts">
import { computed } from "vue";

import { formatPointSchedule, listPointStatusLabel } from "../status";
import type { DriverRouteListItem } from "../types";

const props = defineProps<{
  assigned: DriverRouteListItem[];
  history: DriverRouteListItem[];
  loading: boolean;
  activeRouteId: string | null;
  unreadByRoute?: Record<string, number>;
}>();

const emit = defineEmits<{
  back: [];
  openRoute: [routeId: string];
  refresh: [];
}>();

function newestFirst(items: DriverRouteListItem[]): DriverRouteListItem[] {
  return [...items].sort((a, b) => {
    const createdA = a.created_at || "";
    const createdB = b.created_at || "";
    if (createdA !== createdB) {
      return createdB.localeCompare(createdA);
    }
    return String(b.id).localeCompare(String(a.id), undefined, { numeric: true });
  });
}

const assignedSorted = computed(() => newestFirst(props.assigned));
const historySorted = computed(() => newestFirst(props.history));

function routeStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    new: "Назначен",
    process: "В работе",
    success: "Завершён",
    cancelled: "Отменён"
  };
  return labels[status] ?? status;
}

function processStageLabel(item: DriverRouteListItem): string {
  return listPointStatusLabel(item.active_point_status) || routeStatusLabel(item.status);
}

function processPointName(item: DriverRouteListItem): string {
  const place = (item.active_point_place || "").trim();
  const name = (item.active_point_name || "").trim();
  return place || name;
}

function processPointSchedule(item: DriverRouteListItem): string {
  return formatPointSchedule(item.active_point_type, item.active_point_date, item.active_point_time);
}

function isActiveRoute(routeId: string): boolean {
  return props.activeRouteId === routeId;
}

function unreadCount(routeId: string): number {
  return props.unreadByRoute?.[routeId] ?? 0;
}
</script>

<template>
  <section class="routes-wrap">
    <button class="ghost back" type="button" @click="emit('back')">← Назад</button>
    <article class="card">
      <h2>Назначенные</h2>
      <div class="list">
        <button v-for="item in assignedSorted" :key="item.id" class="route-card" @click="emit('openRoute', item.id)">
          <div class="row">
            <div class="row-left">
              <strong>#{{ item.id }}</strong>
              <span v-if="unreadCount(item.id) > 0" class="chat-dot" :title="`Новых сообщений: ${unreadCount(item.id)}`" />
            </div>
            <span class="chip" :class="{ active: item.id === activeRouteId }">{{
              item.status === "process" ? processStageLabel(item) : routeStatusLabel(item.status)
            }}</span>
          </div>
          <small>ТС: {{ item.number_auto || "—" }}</small>
          <small v-if="item.status === 'process' && processPointName(item)">Точка: {{ processPointName(item) }}</small>
          <small v-if="item.status === 'process' && processPointSchedule(item)">{{ processPointSchedule(item) }}</small>
          <small v-else-if="item.status !== 'process'">Точек: {{ item.points_count }}</small>
          <small v-if="isActiveRoute(item.id)" class="active-note">Текущий принятый рейс</small>
          <small v-else class="inactive-note">Только просмотр. Принятие/этапы недоступны</small>
        </button>
        <p v-if="!assigned.length" class="empty">Нет назначенных рейсов</p>
      </div>
    </article>

    <article class="card">
      <h2>Прошедшие</h2>
      <div class="list">
        <button v-for="item in historySorted" :key="item.id" class="route-card" @click="emit('openRoute', item.id)">
          <div class="row">
            <div class="row-left">
              <strong>#{{ item.id }}</strong>
              <span v-if="unreadCount(item.id) > 0" class="chat-dot" :title="`Новых сообщений: ${unreadCount(item.id)}`" />
            </div>
            <span class="chip">{{ routeStatusLabel(item.status) }}</span>
          </div>
          <small>ТС: {{ item.number_auto || "—" }}</small>
          <small>Точек: {{ item.points_count }}</small>
        </button>
        <p v-if="!history.length" class="empty">Нет завершённых рейсов</p>
      </div>
    </article>
  </section>
</template>

<style scoped>
.routes-wrap {
  display: grid;
  gap: 0.85rem;
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
}
.card {
  border: 1px solid var(--border);
  border-radius: 16px;
  background: rgba(17, 24, 39, 0.88);
  box-shadow: var(--shadow-sm);
  padding: 0.95rem;
}
.card h2 {
  margin: 0 0 0.65rem;
  font-size: 0.95rem;
  color: var(--text-muted);
  font-weight: 650;
}
.list {
  display: grid;
  gap: 0.55rem;
}
.route-card {
  text-align: left;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface-2);
  color: #fff;
  padding: 0.75rem;
  display: grid;
  gap: 0.22rem;
}
.route-card strong {
  color: var(--text-heading);
  font-size: 1rem;
}
.route-card small {
  color: var(--text-muted);
  font-size: 0.82rem;
}
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.row-left {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  min-width: 0;
}
.chat-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  background: var(--success);
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.22);
  flex: 0 0 auto;
  animation: route-unread-pulse 1.8s ease-in-out infinite;
}
@keyframes route-unread-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.2);
    opacity: 0.7;
  }
}
.chip {
  border-radius: 999px;
  background: var(--chip);
  padding: 0.14rem 0.55rem;
  font-size: 0.78rem;
}
.chip.active {
  background: var(--primary-strong);
}
.active-note {
  color: #93c5fd;
}
.inactive-note {
  color: var(--text-muted);
}
.empty {
  margin: 0;
  color: var(--text-muted);
}
.ghost {
  width: auto;
  min-height: 40px;
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  background: transparent;
  color: #bfdbfe;
  padding: 0.4rem 0.7rem;
  justify-self: start;
}
</style>
