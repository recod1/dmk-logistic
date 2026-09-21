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

function chatKindLabel(item: NotificationDto): string {
  if (item.event_type !== "chat_message") {
    return "";
  }
  const p = item.payload && typeof item.payload === "object" && !Array.isArray(item.payload)
    ? (item.payload as Record<string, unknown>)
    : null;
  if (payloadNumber(p, "room_id") != null) {
    return "чат личный";
  }
  if (item.route_id || (typeof p?.route_id === "string" && p.route_id.trim())) {
    return "чат рейса";
  }
  return "";
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
    <div class="head-sticky">
      <div class="head-row">
        <h2 class="page-heading">
          Уведомления <span v-if="typeof unreadCount === 'number'" class="counter">({{ unreadCount }})</span>
        </h2>
        <div class="head-actions">
          <button :disabled="loading" @click="emit('refresh')">Обновить</button>
          <button v-if="canPush && !pushEnabled" :disabled="loading" @click="emit('enablePush')">Включить push</button>
          <button v-if="canPush && pushEnabled" :disabled="loading" @click="emit('disablePush')">Выключить push</button>
          <button :disabled="loading || !items.some((item) => !item.is_read)" @click="emit('markAllRead')">Прочитать всё</button>
        </div>
      </div>
      <p v-if="pushHint" class="hint">{{ pushHint }}</p>
    </div>

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
          <span v-if="chatKindLabel(item)" class="chat-kind">{{ chatKindLabel(item) }}</span>
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
  gap: 0.8rem;
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
}
.head-sticky {
  position: sticky;
  top: calc(var(--topbar-h) + env(safe-area-inset-top, 0px));
  z-index: 20;
  margin: 0 -0.2rem;
  padding: 0.35rem 0.2rem 0.45rem;
  background: rgba(3, 7, 18, 0.94);
  backdrop-filter: blur(12px);
}
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: nowrap;
  gap: 0.5rem;
}
.page-heading {
  margin: 0;
  font-size: 1rem;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
}
.head-actions {
  display: flex;
  flex-wrap: nowrap;
  gap: 0.45rem;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  min-width: 0;
}
.head-actions button {
  min-height: 36px;
  border-radius: 10px;
  flex: 0 0 auto;
  white-space: nowrap;
}
.chat-kind {
  flex: 0 0 auto;
  border-radius: 999px;
  padding: 0.12rem 0.45rem;
  background: rgba(56, 189, 248, 0.16);
  color: #7dd3fc;
  font-size: 0.72rem;
  font-weight: 700;
  white-space: nowrap;
}
.list {
  display: grid;
  gap: 0.7rem;
}
.item-card {
  display: grid;
  gap: 0.45rem;
  border: 1px solid var(--border);
  padding: 0.85rem;
  border-radius: 14px;
  background: rgba(17, 24, 39, 0.8);
}
.item-card.clickable {
  cursor: pointer;
}
.item-card.unread {
  border-color: rgba(239, 68, 68, 0.55);
  box-shadow: inset 3px 0 0 var(--danger);
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
  color: var(--text-muted);
  font-size: 0.9rem;
  align-items: center;
}
.extra {
  margin: 0;
  color: var(--text-muted);
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
  color: var(--text-muted);
  font-size: 0.9rem;
}
.empty-card {
  color: var(--text-muted);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 1.1rem;
  background: rgba(17, 24, 39, 0.72);
}
.link-btn {
  width: auto;
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  background: transparent;
  color: #bfdbfe;
  padding: 0.25rem 0.5rem;
  font-size: 0.78rem;
}
</style>
