<script setup lang="ts">
import type { NotificationDto } from "../types";

defineProps<{
  items: NotificationDto[];
  loading: boolean;
  error: string;
  unreadCount?: number;
  canPush?: boolean;
  pushEnabled?: boolean;
  pushHint?: string;
}>();

const emit = defineEmits<{
  refresh: [];
  enablePush: [];
  disablePush: [];
  markRead: [notificationId: number];
  markAllRead: [];
  openFromNotification: [item: NotificationDto];
}>();

function payloadNumber(payload: Record<string, unknown> | null | undefined, key: string): number | null {
  if (!payload || typeof payload !== "object") return null;
  const v = payload[key];
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function notificationIsNavigable(item: NotificationDto): boolean {
  if (item.route_id) return true;
  const p = item.payload;
  if (p && typeof p === "object" && !Array.isArray(p)) {
    if (payloadNumber(p as Record<string, unknown>, "room_id") != null) return true;
    if (payloadNumber(p as Record<string, unknown>, "salary_id") != null) return true;
  }
  return false;
}

function onNotificationCardClick(item: NotificationDto): void {
  if (!notificationIsNavigable(item)) return;
  emit("openFromNotification", item);
}

function formatExtra(item: NotificationDto): string {
  const parts: string[] = [];
  const driver = (item.driver_full_name || "").trim();
  if (driver) parts.push(`Водитель: ${driver}`);
  const auto = (item.number_auto || "").trim();
  if (auto) parts.push(`ТС: ${auto}`);
  const trailer = (item.trailer_number || "").trim();
  if (trailer) parts.push(`Прицеп: ${trailer}`);
  const pointType = (item.point_type_point || "").trim();
  const pointAddr = (item.point_place_point || "").trim();
  if (pointType || pointAddr) {
    const label = [pointType, pointAddr].filter(Boolean).join(" · ");
    parts.push(`Точка: ${label}`);
  }
  return parts.join(" | ");
}
</script>

<template>
  <section class="notifications-wrap">
    <div class="head-row">
      <h1>Уведомления <span v-if="typeof unreadCount === 'number'" class="counter">({{ unreadCount }})</span></h1>
      <div class="head-actions">
        <button :disabled="loading" @click="emit('refresh')">Обновить</button>
        <button v-if="canPush && !pushEnabled" :disabled="loading" @click="emit('enablePush')">Включить push</button>
        <button v-if="canPush && pushEnabled" :disabled="loading" @click="emit('disablePush')">Выключить push</button>
        <button :disabled="loading || !items.some((item) => !item.is_read)" @click="emit('markAllRead')">Прочитать всё</button>
      </div>
    </div>

    <p v-if="pushHint" class="hint">{{ pushHint }}</p>
    <p v-if="error" class="error">{{ error }}</p>

    <article v-if="!items.length && !loading" class="card empty-card">
      <p>Пока нет событий.</p>
    </article>

    <section class="list">
      <article
        v-for="item in items"
        :key="item.id"
        class="card item-card"
        :class="{ unread: !item.is_read, clickable: notificationIsNavigable(item) }"
        @click="onNotificationCardClick(item)"
      >
        <div class="row-top">
          <strong>{{ item.message }}</strong>
        </div>
        <p v-if="formatExtra(item)" class="extra">{{ formatExtra(item) }}</p>
        <div v-if="!item.is_read" class="meta">
          <button class="link-btn" @click.stop="emit('markRead', item.id)">Отметить прочитанным</button>
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
  gap: 0.7rem;
}
.item-card {
  display: grid;
  gap: 0.45rem;
  border-bottom: 1px solid #334155;
  padding-bottom: 0.7rem;
  border-radius: 12px;
}
.item-card.clickable {
  cursor: pointer;
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
p {
  margin: 0;
}
.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  color: #94a3b8;
  font-size: 0.9rem;
  align-items: center;
}
.extra {
  margin: 0;
  color: #94a3b8;
  font-size: 0.88rem;
  line-height: 1.25;
  overflow-wrap: anywhere;
}
.counter {
  color: #fca5a5;
}
.error {
  color: #fca5a5;
}
.hint {
  margin: 0;
  color: #94a3b8;
  font-size: 0.9rem;
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
