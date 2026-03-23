<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";

import ActiveRouteView from "./components/ActiveRouteView.vue";
import AdminUsersView from "./components/AdminUsersView.vue";
import LoginView from "./components/LoginView.vue";
import {
  acceptRoute,
  createAdminUser,
  getActiveRoute,
  listAdminUsers,
  login as loginRequest,
  sendEventsBatch,
  updateAdminUser
} from "./api";
import { addOutboxEvent, getOutboxEvents, loadActiveRoute, removeOutboxByClientEventIds, saveActiveRoute } from "./db";
import { nextStatus } from "./status";
import type { AdminUser, AuthUser, EventPayload, RouteDto } from "./types";

const TOKEN_STORAGE_KEY = "dmk_mobile_token";
const USER_STORAGE_KEY = "dmk_mobile_user";
const DEVICE_ID_STORAGE_KEY = "dmk_mobile_device_id";

const authToken = ref<string>("");
const authUser = ref<AuthUser | null>(null);
const route = ref<RouteDto | null>(null);
const authLoading = ref(false);
const authError = ref("");
const syncing = ref(false);
const syncMessage = ref("Ожидание");
const isOnline = ref(navigator.onLine);
const currentSection = ref<"route" | "users">("route");
const adminUsers = ref<AdminUser[]>([]);
const usersLoading = ref(false);
const usersError = ref("");

const isAuthed = computed(() => Boolean(authToken.value));
const onlineLabel = computed(() => (isOnline.value ? "online" : "offline"));
const isAdmin = computed(() => (authUser.value?.role || "").toLowerCase() === "admin");

function getDeviceId(): string {
  const existing = localStorage.getItem(DEVICE_ID_STORAGE_KEY);
  if (existing) {
    return existing;
  }
  const generated = `web-${Math.random().toString(36).slice(2)}-${Date.now()}`;
  localStorage.setItem(DEVICE_ID_STORAGE_KEY, generated);
  return generated;
}

function persistAuth(token: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
  localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
}

function clearAuth(): void {
  authToken.value = "";
  authUser.value = null;
  adminUsers.value = [];
  currentSection.value = "route";
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(USER_STORAGE_KEY);
}

async function refreshRoute(): Promise<void> {
  if (!authToken.value) {
    return;
  }
  try {
    const serverRoute = await getActiveRoute(authToken.value);
    route.value = serverRoute;
    await saveActiveRoute(serverRoute);
  } catch (error) {
    syncMessage.value = `Ошибка загрузки рейса: ${(error as Error).message}`;
  }
}

async function syncOutbox(): Promise<void> {
  if (!authToken.value) {
    return;
  }
  if (!navigator.onLine) {
    syncMessage.value = "Офлайн: события в очереди";
    return;
  }
  const deviceId = getDeviceId();
  const outbox = await getOutboxEvents(deviceId);
  if (!outbox.length) {
    syncMessage.value = "Очередь событий пуста";
    return;
  }

  syncing.value = true;
  try {
    const events: EventPayload[] = outbox.map((e) => ({
      client_event_id: e.client_event_id,
      occurred_at_client: e.occurred_at_client,
      point_id: e.point_id,
      to_status: e.to_status
    }));
    const result = await sendEventsBatch(authToken.value, deviceId, events);
    const removable = result.items
      .filter((item) => item.applied || item.duplicate)
      .map((item) => item.client_event_id);
    await removeOutboxByClientEventIds(removable);
    await refreshRoute();
    syncMessage.value = `Синхронизировано: ${result.applied}/${result.received}`;
  } catch (error) {
    syncMessage.value = `Ошибка синхронизации: ${(error as Error).message}`;
  } finally {
    syncing.value = false;
  }
}

async function doLogin(loginValue: string, password: string): Promise<void> {
  authError.value = "";
  authLoading.value = true;
  try {
    const result = await loginRequest(loginValue, password);
    authToken.value = result.access_token;
    authUser.value = result.user;
    persistAuth(result.access_token, result.user);
    if ((result.user.role || "").toLowerCase() === "admin") {
      currentSection.value = "users";
      await refreshAdminUsers();
    } else {
      currentSection.value = "route";
    }
    await refreshRoute();
    await syncOutbox();
  } catch (error) {
    authError.value = (error as Error).message;
  } finally {
    authLoading.value = false;
  }
}

async function refreshAdminUsers(): Promise<void> {
  if (!authToken.value || !isAdmin.value) {
    return;
  }
  usersLoading.value = true;
  usersError.value = "";
  try {
    adminUsers.value = await listAdminUsers(authToken.value);
  } catch (error) {
    usersError.value = `Ошибка загрузки пользователей: ${(error as Error).message}`;
  } finally {
    usersLoading.value = false;
  }
}

async function doCreateAdminUser(payload: { login: string; password: string; role: string }): Promise<void> {
  if (!authToken.value || !isAdmin.value) {
    return;
  }
  usersLoading.value = true;
  usersError.value = "";
  try {
    await createAdminUser(authToken.value, payload);
    await refreshAdminUsers();
  } catch (error) {
    usersError.value = `Ошибка создания: ${(error as Error).message}`;
    usersLoading.value = false;
  }
}

async function doUpdateAdminUser(
  userId: number,
  payload: { login?: string; password?: string; role?: string; is_active?: boolean }
): Promise<void> {
  if (!authToken.value || !isAdmin.value) {
    return;
  }
  if (!Object.keys(payload).length) {
    return;
  }
  usersLoading.value = true;
  usersError.value = "";
  try {
    await updateAdminUser(authToken.value, userId, payload);
    await refreshAdminUsers();
  } catch (error) {
    usersError.value = `Ошибка обновления: ${(error as Error).message}`;
    usersLoading.value = false;
  }
}

async function doAcceptRoute(): Promise<void> {
  if (!authToken.value || !route.value) {
    return;
  }
  try {
    route.value = await acceptRoute(authToken.value, route.value.id);
    await saveActiveRoute(route.value);
  } catch (error) {
    syncMessage.value = `Ошибка принятия рейса: ${(error as Error).message}`;
  }
}

async function markPointNext(pointId: number): Promise<void> {
  if (!route.value) {
    return;
  }
  const current = route.value.points.find((p) => p.id === pointId);
  if (!current) {
    return;
  }
  const toStatus = nextStatus(current.status);
  if (!toStatus) {
    return;
  }

  const event: EventPayload = {
    client_event_id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    occurred_at_client: new Date().toISOString(),
    point_id: pointId,
    to_status: toStatus
  };

  // Оптимистично меняем статус в локальном snapshot.
  current.status = toStatus;
  await saveActiveRoute(route.value);
  await addOutboxEvent({
    ...event,
    device_id: getDeviceId(),
    created_at: new Date().toISOString()
  });
  syncMessage.value = "Событие сохранено локально";
  await syncOutbox();
}

function onOnline(): void {
  isOnline.value = true;
  void syncOutbox();
}

function onOffline(): void {
  isOnline.value = false;
  syncMessage.value = "Нет сети: работа в офлайне";
}

function logout(): void {
  clearAuth();
  route.value = null;
}

onMounted(async () => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY) || "";
  const rawUser = localStorage.getItem(USER_STORAGE_KEY);
  authToken.value = token;
  authUser.value = rawUser ? (JSON.parse(rawUser) as AuthUser) : null;
  route.value = await loadActiveRoute();
  if (token) {
    if ((authUser.value?.role || "").toLowerCase() === "admin") {
      currentSection.value = "users";
      await refreshAdminUsers();
    }
    await refreshRoute();
    await syncOutbox();
  }
  window.addEventListener("online", onOnline);
  window.addEventListener("offline", onOffline);
});

onUnmounted(() => {
  window.removeEventListener("online", onOnline);
  window.removeEventListener("offline", onOffline);
});
</script>

<template>
  <main class="container">
    <header class="topbar">
      <div>
        <strong>DMK Mobile</strong>
        <small>{{ onlineLabel }}</small>
      </div>
      <div class="actions">
        <span v-if="authUser">{{ authUser.login }}</span>
        <button
          v-if="isAuthed && isAdmin"
          :class="{ activeTab: currentSection === 'users' }"
          @click="currentSection = 'users'"
        >
          Пользователи
        </button>
        <button
          v-if="isAuthed"
          :class="{ activeTab: currentSection === 'route' }"
          @click="currentSection = 'route'"
        >
          Рейс
        </button>
        <button v-if="isAuthed" @click="logout">Выход</button>
      </div>
    </header>

    <LoginView v-if="!isAuthed" :loading="authLoading" :error="authError" @submit="doLogin" />

    <section v-else-if="isAdmin && currentSection === 'users'">
      <AdminUsersView
        :users="adminUsers"
        :loading="usersLoading"
        :error="usersError"
        @refresh="refreshAdminUsers"
        @create="doCreateAdminUser"
        @update="doUpdateAdminUser"
      />
    </section>

    <section v-else-if="route">
      <ActiveRouteView
        :route="route"
        :syncing="syncing"
        :sync-message="syncMessage"
        @accept="doAcceptRoute"
        @advance-status="markPointNext"
        @manual-sync="syncOutbox"
      />
    </section>

    <section v-else class="card">
      <h1>Активного рейса нет</h1>
      <p>Когда диспетчер назначит рейс, он появится здесь.</p>
      <button @click="refreshRoute">Обновить</button>
      <p class="hint">{{ syncMessage }}</p>
    </section>
  </main>
</template>

<style scoped>
.container {
  max-width: 760px;
  margin: 0 auto;
  padding: 1rem;
  color: #f9fafb;
  font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
}
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.8rem;
}
.topbar small {
  display: block;
  color: #9ca3af;
}
.actions {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.activeTab {
  background: #1d4ed8;
}
button {
  border: none;
  border-radius: 10px;
  background: #2563eb;
  color: #fff;
  padding: 0.4rem 0.7rem;
}
.card {
  padding: 1rem;
  border: 1px solid #374151;
  background: #111827;
  border-radius: 12px;
}
.hint {
  color: #9ca3af;
}
</style>

