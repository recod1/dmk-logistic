<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import type { AdminChatRoomRow } from "../api";
import { ROLE_OPTIONS, type RoleCode } from "../roles";

export type ChatRoomListItem = {
  id: number;
  kind: "direct" | "group";
  title: string;
  system_key?: string | null;
  unread_count?: number;
};

export type UserListItem = {
  id: number;
  login: string;
  full_name: string | null;
  role_code: string;
  role_label: string;
};

export type LogisticDriverRoomRow = {
  driver: { id: number; full_name: string | null; login: string };
  room: ChatRoomListItem;
};

type HubTab = "direct" | "group" | "broadcast" | "admin";

const props = defineProps<{
  loading: boolean;
  error: string;
  rooms: ChatRoomListItem[];
  users: UserListItem[];
  logisticDriverRooms?: LogisticDriverRoomRow[];
  accountantDriverRooms?: LogisticDriverRoomRow[];
  isLogistic?: boolean;
  isAccountant?: boolean;
  isDriver?: boolean;
  currentUserId?: number | null;
  isAdmin?: boolean;
  adminRooms?: AdminChatRoomRow[];
  adminRoomsLoading?: boolean;
  /** Incremented after successful admin room mutation — clears create/edit forms */
  adminChatTick?: number;
}>();

const emit = defineEmits<{
  back: [];
  refresh: [];
  openRoom: [roomId: number, titleHint?: string];
  openDirectWith: [userId: number];
  "admin-broadcast": [payload: { title: string; message: string; role_codes: RoleCode[] }];
  "admin-delete-room": [roomId: number];
  "admin-refresh-rooms": [];
  "admin-create-room": [payload: { title: string; system_key: string | null; member_user_ids: number[]; role_codes: string[] }];
  "admin-patch-room": [payload: { roomId: number; title: string }];
}>();

const tab = ref<HubTab>("direct");
const userQuery = ref("");

const broadcastTitle = ref("");
const broadcastMessage = ref("");
const broadcastRoles = ref<Record<RoleCode, boolean>>({
  driver: false,
  logistic: false,
  accountant: false,
  admin: false,
  superadmin: false
});

const newRoomTitle = ref("");
const newRoomSystemKey = ref("");
const newRoomMemberIdsText = ref("");
const newRoomRoles = ref<Record<RoleCode, boolean>>({
  driver: false,
  logistic: false,
  accountant: false,
  admin: false,
  superadmin: false
});

const editingRoomId = ref<number | null>(null);
const editingTitle = ref("");

const filteredUsers = computed(() => {
  const q = userQuery.value.trim().toLowerCase();
  if (!q) return props.users;
  return props.users.filter((u) => {
    const name = (u.full_name || "").toLowerCase();
    return u.login.toLowerCase().includes(q) || name.includes(q);
  });
});

const directRooms = computed(() => props.rooms.filter((r) => r.kind === "direct"));
const groupRooms = computed(() => props.rooms.filter((r) => r.kind === "group"));

const excludedGroupRoomIds = computed(() => {
  const ids = new Set<number>();
  (props.logisticDriverRooms ?? []).forEach((x) => ids.add(x.room.id));
  (props.accountantDriverRooms ?? []).forEach((x) => ids.add(x.room.id));
  return ids;
});

const driverPinnedKeys = computed(() => {
  const uid = props.currentUserId;
  if (!uid || !props.isDriver) return null;
  return new Set([`sys:driver:${uid}:logistics`, `sys:driver:${uid}:accounting`]);
});

const driverLogisticsRoom = computed(() => {
  const uid = props.currentUserId;
  if (!uid || !props.isDriver) return null;
  return props.rooms.find((r) => r.system_key === `sys:driver:${uid}:logistics`) ?? null;
});

const driverAccountingRoom = computed(() => {
  const uid = props.currentUserId;
  if (!uid || !props.isDriver) return null;
  return props.rooms.find((r) => r.system_key === `sys:driver:${uid}:accounting`) ?? null;
});

const groupRoomsFiltered = computed(() =>
  groupRooms.value.filter((r) => {
    if (excludedGroupRoomIds.value.has(r.id)) return false;
    const pin = driverPinnedKeys.value;
    if (pin && r.system_key && pin.has(r.system_key)) return false;
    return true;
  })
);

function submitBroadcast(): void {
  const role_codes = (Object.keys(broadcastRoles.value) as RoleCode[]).filter((k) => broadcastRoles.value[k]);
  if (!role_codes.length) {
    return;
  }
  emit("admin-broadcast", {
    title: broadcastTitle.value.trim(),
    message: broadcastMessage.value.trim(),
    role_codes
  });
}

function parseMemberIds(raw: string): number[] {
  const out: number[] = [];
  for (const part of raw.split(/[\s,;]+/)) {
    const n = parseInt(part.trim(), 10);
    if (Number.isFinite(n) && n > 0) out.push(n);
  }
  return [...new Set(out)];
}

function submitCreateRoom(): void {
  const title = newRoomTitle.value.trim();
  if (!title) return;
  const system_key = newRoomSystemKey.value.trim() || null;
  const member_user_ids = parseMemberIds(newRoomMemberIdsText.value);
  const role_codes = (Object.keys(newRoomRoles.value) as RoleCode[]).filter((k) => newRoomRoles.value[k]).map((k) => k);
  emit("admin-create-room", { title, system_key, member_user_ids, role_codes });
}

function startEditRoom(r: AdminChatRoomRow): void {
  editingRoomId.value = r.id;
  editingTitle.value = r.title || "";
}

function cancelEditRoom(): void {
  editingRoomId.value = null;
  editingTitle.value = "";
}

function submitEditRoom(): void {
  if (editingRoomId.value == null) return;
  const title = editingTitle.value.trim();
  if (!title) return;
  emit("admin-patch-room", { roomId: editingRoomId.value, title });
  cancelEditRoom();
}

function onTabSelect(next: HubTab): void {
  if (!props.isAdmin && (next === "broadcast" || next === "admin")) {
    return;
  }
  tab.value = next;
}

onMounted(() => {
  emit("refresh");
});

watch(
  () => props.adminChatTick ?? 0,
  (t, prev) => {
    if (t > 0 && t !== prev) {
      newRoomTitle.value = "";
      newRoomSystemKey.value = "";
      newRoomMemberIdsText.value = "";
      (Object.keys(newRoomRoles.value) as RoleCode[]).forEach((k) => {
        newRoomRoles.value[k] = false;
      });
      cancelEditRoom();
    }
  }
);
</script>

<template>
  <section class="wrap">
    <header class="head">
      <button class="ghost" type="button" @click="emit('back')">← Назад</button>
      <h1>Чаты</h1>
      <button class="secondary" type="button" :disabled="loading" @click="emit('refresh')">Обновить</button>
    </header>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="tabs">
      <button class="tab" :class="{ active: tab === 'direct' }" type="button" @click="onTabSelect('direct')">Личные</button>
      <button class="tab" :class="{ active: tab === 'group' }" type="button" @click="onTabSelect('group')">Групповые</button>
      <button v-if="isAdmin" class="tab" :class="{ active: tab === 'broadcast' }" type="button" @click="onTabSelect('broadcast')">
        Рассылка
      </button>
      <button v-if="isAdmin" class="tab" :class="{ active: tab === 'admin' }" type="button" @click="onTabSelect('admin')">Комнаты</button>
    </div>

    <section v-if="tab === 'direct'" class="card">
      <h2>Диалоги</h2>
      <div class="rooms">
        <button v-for="r in directRooms" :key="r.id" type="button" class="room" @click="emit('openRoom', r.id, r.title)">
          <span class="room-title">{{ r.title }}</span>
          <span v-if="(r.unread_count ?? 0) > 0" class="dot" />
        </button>
        <p v-if="!directRooms.length" class="empty">Диалогов пока нет.</p>
      </div>

      <h2 class="subhead">Написать пользователю</h2>
      <label class="field">
        Поиск
        <input v-model="userQuery" placeholder="Логин или ФИО" />
      </label>
      <div class="users">
        <button
          v-for="u in filteredUsers"
          :key="u.id"
          type="button"
          class="user"
          @click="emit('openDirectWith', u.id)"
        >
          <span class="user-name">{{ u.full_name || u.login }}</span>
          <span class="user-meta">{{ u.role_label }}</span>
        </button>
      </div>
    </section>

    <section v-else-if="tab === 'group'" class="card">
      <template v-if="isDriver && currentUserId">
        <h2>Служба</h2>
        <p class="hint">Один чат с логистами и один с бухгалтерией по всем рейсам и вопросам.</p>
        <div class="rooms">
          <button
            v-if="driverLogisticsRoom"
            type="button"
            class="room"
            @click="emit('openRoom', driverLogisticsRoom.id, driverLogisticsRoom.title || 'Логисты')"
          >
            <span class="room-title">{{ driverLogisticsRoom.title || "Логисты" }}</span>
            <span v-if="(driverLogisticsRoom.unread_count ?? 0) > 0" class="dot" />
          </button>
          <button
            v-if="driverAccountingRoom"
            type="button"
            class="room"
            @click="emit('openRoom', driverAccountingRoom.id, driverAccountingRoom.title || 'Бухгалтерия')"
          >
            <span class="room-title">{{ driverAccountingRoom.title || "Бухгалтерия" }}</span>
            <span v-if="(driverAccountingRoom.unread_count ?? 0) > 0" class="dot" />
          </button>
          <p v-if="!driverLogisticsRoom && !driverAccountingRoom" class="empty">
            Чаты подключаются при загрузке. Нажмите «Обновить».
          </p>
        </div>
      </template>

      <template v-if="isLogistic && (logisticDriverRooms?.length ?? 0) > 0">
        <h2>Водители (логисты)</h2>
        <p class="hint">Отдельный диалог с каждым водителем; сообщения видны всем логистам и этому водителю.</p>
        <div class="rooms">
          <button
            v-for="row in logisticDriverRooms"
            :key="row.room.id"
            type="button"
            class="room"
            @click="emit('openRoom', row.room.id, row.room.title)"
          >
            <span class="room-title">{{ row.room.title }}</span>
            <span v-if="(row.room.unread_count ?? 0) > 0" class="dot" />
          </button>
        </div>
      </template>

      <template v-if="isAccountant && (accountantDriverRooms?.length ?? 0) > 0">
        <h2>Водители (бухгалтерия)</h2>
        <p class="hint">Отдельный диалог с каждым водителем; сообщения видны всем бухгалтерам и этому водителю.</p>
        <div class="rooms">
          <button
            v-for="row in accountantDriverRooms"
            :key="row.room.id"
            type="button"
            class="room"
            @click="emit('openRoom', row.room.id, row.room.title)"
          >
            <span class="room-title">{{ row.room.title }}</span>
            <span v-if="(row.room.unread_count ?? 0) > 0" class="dot" />
          </button>
        </div>
      </template>

      <h2 v-if="!isDriver || groupRoomsFiltered.length">Прочие группы</h2>
      <div v-if="!isDriver || groupRoomsFiltered.length" class="rooms">
        <button
          v-for="r in groupRoomsFiltered"
          :key="r.id"
          type="button"
          class="room"
          @click="emit('openRoom', r.id, r.title)"
        >
          <span class="room-title">{{ r.title }}</span>
          <span v-if="(r.unread_count ?? 0) > 0" class="dot" />
        </button>
        <p v-if="!groupRoomsFiltered.length" class="empty">Других групповых чатов нет.</p>
      </div>
    </section>

    <section v-else-if="tab === 'broadcast' && isAdmin" class="card">
      <h2>Рассылка по ролям</h2>
      <p class="hint">Пользователи выбранных ролей получат уведомление в приложении.</p>
      <label class="field">
        Заголовок
        <input v-model="broadcastTitle" placeholder="Например: Важно" />
      </label>
      <label class="field">
        Текст
        <textarea v-model="broadcastMessage" rows="3" placeholder="Текст уведомления" />
      </label>
      <div class="role-grid">
        <label v-for="opt in ROLE_OPTIONS" :key="opt.role_code" class="check">
          <input v-model="broadcastRoles[opt.role_code]" type="checkbox" />
          {{ opt.role_label }}
        </label>
      </div>
      <button class="primary" type="button" @click="submitBroadcast">Отправить</button>
    </section>

    <section v-else-if="tab === 'admin' && isAdmin" class="card">
      <h2>Создать групповую комнату</h2>
      <p class="hint">Название обязательно. Участники — id пользователей через запятую. Роли — все пользователи с этой ролью видят чат.</p>
      <label class="field">
        Название
        <input v-model="newRoomTitle" placeholder="Например: Общий склад" />
      </label>
      <label class="field">
        Ключ системы (необязательно, уникально)
        <input v-model="newRoomSystemKey" placeholder="my_room_key" />
      </label>
      <label class="field">
        ID участников (через запятую)
        <input v-model="newRoomMemberIdsText" placeholder="12, 34" />
      </label>
      <p class="hint">Роли в комнате</p>
      <div class="role-grid">
        <label v-for="opt in ROLE_OPTIONS" :key="'nr-' + opt.role_code" class="check">
          <input v-model="newRoomRoles[opt.role_code]" type="checkbox" />
          {{ opt.role_label }}
        </label>
      </div>
      <button class="primary" type="button" @click="submitCreateRoom">Создать</button>

      <h2 class="subhead">Все комнаты</h2>
      <button class="ghost sm" type="button" :disabled="adminRoomsLoading" @click="emit('admin-refresh-rooms')">
        Обновить список комнат
      </button>
      <div v-if="adminRooms?.length" class="admin-rooms">
        <div v-for="r in adminRooms" :key="r.id" class="admin-row">
          <div class="admin-row-main">
            <template v-if="editingRoomId === r.id">
              <input v-model="editingTitle" class="inline-input" />
              <div class="edit-actions">
                <button class="ghost sm" type="button" @click="submitEditRoom">Сохранить</button>
                <button class="ghost sm" type="button" @click="cancelEditRoom">Отмена</button>
              </div>
            </template>
            <template v-else>
              <span class="admin-title">{{ r.title || `Комната #${r.id}` }}</span>
              <span class="admin-meta">{{ r.kind }} · id {{ r.id }}</span>
              <span v-if="r.system_key" class="admin-meta">{{ r.system_key }}</span>
            </template>
          </div>
          <div v-if="editingRoomId !== r.id" class="admin-actions">
            <button class="ghost sm" type="button" @click="startEditRoom(r)">Изменить</button>
            <button class="danger sm" type="button" @click="emit('admin-delete-room', r.id)">Удалить</button>
          </div>
        </div>
      </div>
      <p v-else class="empty">Нет комнат или список ещё не загружен.</p>
    </section>
  </section>
</template>

<style scoped>
.wrap {
  display: grid;
  gap: 0.75rem;
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
}
.head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  justify-content: space-between;
  flex-wrap: wrap;
}
h1 {
  margin: 0;
  font-size: 1.05rem;
}
h2 {
  margin: 0;
  font-size: 1rem;
}
.tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.tab {
  border: 1px solid #334155;
  border-radius: 999px;
  background: #0b1220;
  color: #cbd5e1;
  padding: 0.35rem 0.7rem;
}
.tab.active {
  background: #4f46e5;
  border-color: #6366f1;
  color: #fff;
}
.card {
  border: 1px solid #243043;
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.85), rgba(2, 6, 23, 0.95));
  box-shadow: 0 10px 28px rgba(2, 6, 23, 0.28);
  padding: 1rem;
  display: grid;
  gap: 0.75rem;
}
.rooms {
  display: grid;
  gap: 0.45rem;
}
.room {
  border: 1px solid #243043;
  border-radius: 12px;
  background: rgba(2, 6, 23, 0.55);
  color: #e2e8f0;
  padding: 0.7rem 0.85rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  text-align: left;
}
.room-title {
  font-weight: 600;
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #ef4444;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.18);
}
.subhead {
  margin: 0.75rem 0 0;
  font-size: 0.95rem;
}
.field {
  display: grid;
  gap: 0.25rem;
}
textarea {
  width: 100%;
  border-radius: 10px;
  border: 1px solid #334155;
  background: #0b1220;
  color: #fff;
  padding: 0.5rem 0.62rem;
  resize: vertical;
}
input {
  width: 100%;
  border-radius: 10px;
  border: 1px solid #334155;
  background: #0b1220;
  color: #fff;
  padding: 0.5rem 0.62rem;
}
.inline-input {
  margin-bottom: 0.35rem;
}
.edit-actions {
  display: flex;
  gap: 0.35rem;
  flex-wrap: wrap;
}
.role-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
}
.check {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  color: #cbd5e1;
  font-size: 0.9rem;
}
.primary {
  border: none;
  border-radius: 10px;
  background: #16a34a;
  color: #fff;
  padding: 0.5rem 0.85rem;
  font-weight: 600;
  justify-self: start;
}
.users {
  display: grid;
  gap: 0.35rem;
  max-height: 45vh;
  overflow: auto;
}
.user {
  border: 1px solid #243043;
  border-radius: 12px;
  background: rgba(2, 6, 23, 0.35);
  color: #e2e8f0;
  padding: 0.6rem 0.75rem;
  display: grid;
  gap: 0.15rem;
  text-align: left;
}
.user-meta {
  color: #94a3b8;
  font-size: 0.85rem;
}
.empty {
  margin: 0;
  color: #94a3b8;
}
.hint {
  margin: 0;
  color: #94a3b8;
  font-size: 0.88rem;
}
.ghost {
  border: 1px solid #334155;
  border-radius: 10px;
  background: transparent;
  color: #cbd5e1;
  padding: 0.42rem 0.62rem;
}
.ghost.sm {
  font-size: 0.85rem;
  padding: 0.3rem 0.5rem;
}
.secondary {
  border: none;
  border-radius: 10px;
  background: #3b82f6;
  color: #fff;
  padding: 0.42rem 0.62rem;
}
.danger.sm {
  border: none;
  border-radius: 8px;
  background: #b91c1c;
  color: #fff;
  padding: 0.28rem 0.5rem;
  font-size: 0.82rem;
}
.admin-rooms {
  display: grid;
  gap: 0.4rem;
  max-height: 36vh;
  overflow: auto;
}
.admin-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
  border: 1px solid #334155;
  border-radius: 10px;
  padding: 0.5rem 0.62rem;
  background: rgba(2, 6, 23, 0.4);
}
.admin-row-main {
  display: grid;
  gap: 0.15rem;
  min-width: 0;
  flex: 1;
}
.admin-actions {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  flex-shrink: 0;
}
.admin-title {
  font-weight: 600;
  color: #e2e8f0;
}
.admin-meta {
  font-size: 0.8rem;
  color: #94a3b8;
  word-break: break-all;
}
.error {
  margin: 0;
  color: #fca5a5;
}
</style>
