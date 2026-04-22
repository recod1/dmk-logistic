<script setup lang="ts">
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

function routeStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    new: "Назначен",
    process: "В работе",
    success: "Завершён",
    cancelled: "Отменён"
  };
  return labels[status] ?? status;
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
    <header class="head-row">
      <button class="ghost" @click="emit('back')">← Главная</button>
      <h1>Рейсы</h1>
      <button class="ghost" :disabled="loading" @click="emit('refresh')">Обновить</button>
    </header>

    <article class="card">
      <h2>Назначенные</h2>
      <div class="list">
        <button v-for="item in assigned" :key="item.id" class="route-card" @click="emit('openRoute', item.id)">
          <div class="row">
            <div class="row-left">
              <strong>#{{ item.id }}</strong>
              <span v-if="unreadCount(item.id) > 0" class="chat-dot" :title="`Новых сообщений: ${unreadCount(item.id)}`" />
            </div>
            <span class="chip" :class="{ active: item.id === activeRouteId }">{{ routeStatusLabel(item.status) }}</span>
          </div>
          <small>ТС: {{ item.number_auto || "—" }}</small>
          <small>Точек: {{ item.points_count }}</small>
          <small v-if="isActiveRoute(item.id)" class="active-note">Текущий принятый рейс</small>
          <small v-else class="inactive-note">Только просмотр. Принятие/этапы недоступны</small>
        </button>
        <p v-if="!assigned.length" class="empty">Нет назначенных рейсов</p>
      </div>
    </article>

    <article class="card">
      <h2>Прошедшие</h2>
      <div class="list">
        <button v-for="item in history" :key="item.id" class="route-card" @click="emit('openRoute', item.id)">
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
  gap: 0.8rem;
}
.head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.list {
  display: grid;
  gap: 0.5rem;
}
.route-card {
  text-align: left;
  border: 1px solid #334155;
  border-radius: 12px;
  background: #0f172a;
  color: #fff;
  padding: 0.6rem;
  display: grid;
  gap: 0.3rem;
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
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #22c55e;
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
  flex: 0 0 auto;
}
.chip {
  border-radius: 999px;
  background: #1f2937;
  padding: 0.1rem 0.5rem;
  font-size: 0.78rem;
}
.chip.active {
  background: #1d4ed8;
}
.active-note {
  color: #93c5fd;
}
.inactive-note {
  color: #94a3b8;
}
.empty {
  margin: 0;
  color: #94a3b8;
}
.ghost {
  width: auto;
  border: 1px solid #334155;
  border-radius: 10px;
  background: transparent;
  color: #bfdbfe;
  padding: 0.4rem 0.6rem;
}
</style>
