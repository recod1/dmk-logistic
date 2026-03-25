<script setup lang="ts">
import type { NotificationDto } from "../types";

defineProps<{
  items: NotificationDto[];
  loading: boolean;
  error: string;
  unreadCount?: number;
}>();

const emit = defineEmits<{
  refresh: [];
  markRead: [notificationId: number];
  markAllRead: [];
}>();

function eventTypeLabel(eventType: string): string {
  const map: Record<string, string> = {
    route_assigned: "Назначение рейса",
    route_cancelled: "Отмена рейса",
    route_completed: "Завершение рейса",
    point_status_changed: "Статус точки"
  };
  return map[eventType] ?? eventType;
}

function formatDate(value: string): string {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) {
    return value;
  }
  return d.toLocaleString("ru-RU");
}
</script>

<template>
  <section class="notifications-wrap">
    <div class="head-row">
      <h1>Уведомления <span v-if="typeof unreadCount === 'number'" class="counter">({{ unreadCount }})</span></h1>
      <div class="head-actions">
        <button :disabled="loading" @click="emit('refresh')">Обновить</button>
        <button :disabled="loading || !items.some((item) => !item.is_read)" @click="emit('markAllRead')">Прочитать всё</button>
      </div>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <article v-if="!items.length && !loading" class="card empty-card">
      <p>Пока нет событий.</p>
    </article>

    <section class="list">
      <article v-for="item in items" :key="item.id" class="card item-card" :class="{ unread: !item.is_read }">
        <div class="row-top">
          <strong>{{ item.title }}</strong>
          <span class="type">{{ eventTypeLabel(item.event_type) }}</span>
        </div>
        <p>{{ item.message }}</p>
        <div class="meta">
          <span v-if="item.route_id">Рейс: {{ item.route_id }}</span>
          <span v-if="item.point_id">Точка: {{ item.point_id }}</span>
          <span>{{ formatDate(item.created_at) }}</span>
          <button v-if="!item.is_read" class="link-btn" @click="emit('markRead', item.id)">Отметить прочитанным</button>
        </div>
      </article>
    </section>
  </section>
</template>

<style scoped>
.notifications-wrap {
  display: grid;
  gap: 0.75rem;
}
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.head-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}
.list {
  display: grid;
  gap: 0.55rem;
}
.item-card {
  display: grid;
  gap: 0.45rem;
}
.item-card.unread {
  border-color: #ef4444;
}
.row-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.5rem;
}
.type {
  border-radius: 999px;
  border: 1px solid #334155;
  color: #bfdbfe;
  padding: 0.05rem 0.45rem;
  font-size: 0.8rem;
}
p {
  margin: 0;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  color: #94a3b8;
  font-size: 0.82rem;
  align-items: center;
}
.counter {
  color: #fca5a5;
}
.error {
  color: #fca5a5;
}
.empty-card {
  color: #94a3b8;
}
.link-btn {
  width: auto;
  border: 1px solid #334155;
  border-radius: 8px;
  background: transparent;
  color: #bfdbfe;
  padding: 0.2rem 0.45rem;
  font-size: 0.78rem;
}
</style>
