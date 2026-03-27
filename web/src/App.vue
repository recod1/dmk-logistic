<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";

import AdminRouteDetailsView from "./components/AdminRouteDetailsView.vue";
import AdminRoutesView from "./components/AdminRoutesView.vue";
import AdminUsersView from "./components/AdminUsersView.vue";
import DriverHomeView from "./components/DriverHomeView.vue";
import DriverRouteDetailsView from "./components/DriverRouteDetailsView.vue";
import DriverRoutesView from "./components/DriverRoutesView.vue";
import LoginView from "./components/LoginView.vue";
import NotificationsView from "./components/NotificationsView.vue";
import {
  acceptRoute,
  assignAdminRouteDriver,
  cancelAdminRoute,
  createAdminRoute,
  createAdminUser,
  deleteAdminRoute,
  deleteAdminUser,
  getActiveRoute,
  getAdminRoute,
  getDriverRoute,
  getUnreadNotificationsCount,
  listAdminRoutes,
  listAdminUsers,
  listDriverRoutes,
  listNotifications,
  listRouteDrivers,
  login as loginRequest,
  markAllNotificationsRead,
  markNotificationRead,
  notificationsWebSocketUrl,
  sendEventsBatch,
  updateAdminRoute,
  updateAdminUser
} from "./api";
import {
  addOutboxEvent,
  getOutboxEvents,
  getPointOverlays,
  loadActiveRoute,
  removeOutboxByClientEventIds,
  removePointOverlays,
  saveActiveRoute,
  savePointOverlay
} from "./db";
import { isAdminRole, isRouteManagerRole } from "./roles";
import { isPointDone, nextStatus } from "./status";
import type {
  AdminRoute,
  AdminRouteCreatePayload,
  AdminUser,
  AuthUser,
  DriverOption,
  DriverRouteListItem,
  EventPayload,
  NotificationDto,
  RouteDto
} from "./types";

const TOKEN_STORAGE_KEY = "dmk_mobile_token";
const USER_STORAGE_KEY = "dmk_mobile_user";
const DEVICE_ID_STORAGE_KEY = "dmk_mobile_device_id";

type AppSection =
  | "driver_home"
  | "driver_routes"
  | "driver_route_details"
  | "notifications"
  | "admin_users"
  | "admin_routes"
  | "admin_route_details";
type RouteFilters = { status?: string; route_id?: string; number_auto?: string; driver_query?: string };

const authToken = ref<string>("");
const authUser = ref<AuthUser | null>(null);
const route = ref<RouteDto | null>(null);
const authLoading = ref(false);
const authError = ref("");
const syncing = ref(false);
const syncMessage = ref("Готово");
const currentSection = ref<AppSection>("driver_home");
const profileMenuOpen = ref(false);
const selectedDriverRoute = ref<RouteDto | null>(null);
const driverAssignedRoutes = ref<DriverRouteListItem[]>([]);
const driverHistoryRoutes = ref<DriverRouteListItem[]>([]);
const driverRoutesLoading = ref(false);
const unreadNotificationsCount = ref(0);

const adminUsers = ref<AdminUser[]>([]);
const usersLoading = ref(false);
const usersError = ref("");

const adminRoutes = ref<AdminRoute[]>([]);
const selectedAdminRoute = ref<AdminRoute | null>(null);
const routeDrivers = ref<DriverOption[]>([]);
const routesLoading = ref(false);
const routesError = ref("");
const routeFilters = ref<RouteFilters>({ status: "process" });

const notifications = ref<NotificationDto[]>([]);
const notificationsLoading = ref(false);
const notificationsError = ref("");

let syncIntervalId: number | null = null;
let notificationsWs: WebSocket | null = null;
let notificationsWsReconnectTimer: number | null = null;
let notificationsPingInterval: number | null = null;

const isAuthed = computed(() => Boolean(authToken.value));
const isAdmin = computed(() => isAdminRole(authUser.value?.role_code || ""));
const isRouteManager = computed(() => isRouteManagerRole(authUser.value?.role_code || ""));
const isDriver = computed(() => authUser.value?.role_code === "driver");
const activeRouteSummary = computed(() => {
  if (!route.value) {
    return null;
  }
  return driverAssignedRoutes.value.find((item) => item.id === route.value?.id) ?? null;
});
const hasAssignedRoutes = computed(() => driverAssignedRoutes.value.some((item) => item.status === "new"));
const hasUnreadNotifications = computed(() => unreadNotificationsCount.value > 0);

const currentPageTitle = computed(() => {
  if (!isAuthed.value) {
    return "ДМК - Вход";
  }
  if (currentSection.value === "driver_home") {
    return "ДМК - Главная";
  }
  if (
    currentSection.value === "driver_routes" ||
    currentSection.value === "driver_route_details" ||
    currentSection.value === "admin_routes" ||
    currentSection.value === "admin_route_details"
  ) {
    return "ДМК - Рейсы";
  }
  if (currentSection.value === "admin_users") {
    return "ДМК - Пользователи";
  }
  if (currentSection.value === "notifications") {
    return "ДМК - Уведомления";
  }
  return "ДМК";
});

const profileDisplayName = computed(() => authUser.value?.full_name || authUser.value?.login || "");

const profileMenuItems = computed<Array<{ section: AppSection; label: string }>>(() => {
  if (!authUser.value) {
    return [];
  }
  if (isAdminRole(authUser.value.role_code)) {
    return [
      { section: "admin_routes", label: "Рейсы" },
      { section: "admin_users", label: "Пользователи" },
      { section: "notifications", label: "Уведомления" }
    ];
  }
  if (isRouteManagerRole(authUser.value.role_code)) {
    return [
      { section: "admin_routes", label: "Рейсы" },
      { section: "notifications", label: "Уведомления" }
    ];
  }
  return [
    { section: "driver_home", label: "Главная" },
    { section: "driver_routes", label: "Рейсы" },
    { section: "notifications", label: "Уведомления" }
  ];
});

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

function stopBackgroundSyncLoop(): void {
  if (syncIntervalId !== null) {
    window.clearInterval(syncIntervalId);
    syncIntervalId = null;
  }
}

function startBackgroundSyncLoop(): void {
  stopBackgroundSyncLoop();
  if (!isDriver.value || !authToken.value) {
    return;
  }
  syncIntervalId = window.setInterval(() => {
    void syncOutboxInBackground();
  }, 15000);
}

function closeNotificationsSocket(): void {
  if (notificationsPingInterval !== null) {
    window.clearInterval(notificationsPingInterval);
    notificationsPingInterval = null;
  }
  if (notificationsWsReconnectTimer !== null) {
    window.clearTimeout(notificationsWsReconnectTimer);
    notificationsWsReconnectTimer = null;
  }
  if (notificationsWs) {
    notificationsWs.close();
    notificationsWs = null;
  }
}

function clearNotificationsSocketTimers(): void {
  if (notificationsPingInterval !== null) {
    window.clearInterval(notificationsPingInterval);
    notificationsPingInterval = null;
  }
  if (notificationsWsReconnectTimer !== null) {
    window.clearTimeout(notificationsWsReconnectTimer);
    notificationsWsReconnectTimer = null;
  }
}

function showBrowserPushNotification(item: NotificationDto): void {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return;
  }
  if (Notification.permission === "granted") {
    void new Notification(item.title, {
      body: item.message,
      tag: `dmk-notification-${item.id}`
    });
  }
}

function handleIncomingNotification(
  item: NotificationDto,
  options: { playEffects?: boolean; syncDriverState?: boolean } = {}
): void {
  const playEffects = options.playEffects ?? true;
  const syncDriverState = options.syncDriverState ?? true;
  const exists = notifications.value.some((candidate) => candidate.id === item.id);
  if (!exists) {
    notifications.value = [item, ...notifications.value].slice(0, 50);
    if (playEffects) {
      playNotificationSound();
      showBrowserPushNotification(item);
    }
    if (!item.is_read) {
      unreadNotificationsCount.value += 1;
    }
  }

  if (syncDriverState && item.event_type === "route_deleted" && isDriver.value) {
    if (!item.route_id || selectedDriverRoute.value?.id === item.route_id) {
      selectedDriverRoute.value = null;
      if (currentSection.value === "driver_route_details") {
        currentSection.value = "driver_home";
      }
    }
    void refreshDriverData();
  }
}

function playNotificationSound(): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    const audioContextClass =
      (window as Window & { AudioContext?: typeof AudioContext }).AudioContext ||
      (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!audioContextClass) {
      return;
    }
    const context = new audioContextClass();
    const now = context.currentTime;
    const gain = context.createGain();
    gain.gain.value = 0.001;
    gain.connect(context.destination);
    gain.gain.exponentialRampToValueAtTime(0.22, now + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.38);

    const oscillator = context.createOscillator();
    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(930, now);
    oscillator.connect(gain);
    oscillator.start(now);
    oscillator.stop(now + 0.4);

    window.setTimeout(() => {
      void context.close();
    }, 550);
  } catch {
    // Ignore sound errors on restricted devices.
  }
}

function scheduleNotificationsSocketReconnect(): void {
  if (!authToken.value) {
    return;
  }
  if (notificationsWsReconnectTimer !== null) {
    return;
  }
  notificationsWsReconnectTimer = window.setTimeout(() => {
    notificationsWsReconnectTimer = null;
    connectNotificationsSocket();
  }, 2500);
}

function connectNotificationsSocket(): void {
  if (!authToken.value) {
    return;
  }
  closeNotificationsSocket();
  try {
    const ws = new WebSocket(notificationsWebSocketUrl(authToken.value));
    notificationsWs = ws;
    ws.onopen = () => {
      if (notificationsPingInterval !== null) {
        window.clearInterval(notificationsPingInterval);
      }
      notificationsPingInterval = window.setInterval(() => {
        try {
          ws.send("ping");
        } catch {
          // noop
        }
      }, 20000);
    };
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as { type?: string; item?: NotificationDto };
        if (payload.type === "notification_created" && payload.item) {
          handleIncomingNotification(payload.item, { playEffects: true, syncDriverState: true });
          if (payload.item.route_id) {
            if (isDriver.value) {
              void refreshDriverRoutes();
              if (currentSection.value === "driver_route_details" && selectedDriverRoute.value?.id === payload.item.route_id) {
                void openDriverRouteDetails(payload.item.route_id);
              }
            } else if (isRouteManager.value) {
              void refreshAdminRoutes(routeFilters.value);
            }
          }
        }
      } catch {
        // heartbeat responses can be non-json (e.g. "pong")
      }
    };
    ws.onclose = () => {
      clearNotificationsSocketTimers();
      notificationsWs = null;
      scheduleNotificationsSocketReconnect();
    };
    ws.onerror = () => {
      clearNotificationsSocketTimers();
      notificationsWs = null;
      scheduleNotificationsSocketReconnect();
    };
  } catch {
    scheduleNotificationsSocketReconnect();
  }
}

function clearAuth(): void {
  authToken.value = "";
  clearNotificationsSocketTimers();
  stopBackgroundSyncLoop();
  closeNotificationsSocket();
  authUser.value = null;
  route.value = null;
  selectedDriverRoute.value = null;
  driverAssignedRoutes.value = [];
  driverHistoryRoutes.value = [];
  adminUsers.value = [];
  adminRoutes.value = [];
  routeDrivers.value = [];
  selectedAdminRoute.value = null;
  notifications.value = [];
  unreadNotificationsCount.value = 0;
  currentSection.value = "driver_home";
  profileMenuOpen.value = false;
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(USER_STORAGE_KEY);
}

function openDefaultSectionByRole(user: AuthUser): void {
  if (isAdminRole(user.role_code) || isRouteManagerRole(user.role_code)) {
    currentSection.value = "admin_routes";
    return;
  }
  currentSection.value = "driver_home";
}

async function applyOverlaysToRoute(baseRoute: RouteDto | null): Promise<RouteDto | null> {
  if (!baseRoute) {
    return null;
  }
  const overlays = await getPointOverlays(baseRoute.id);
  if (!overlays.length) {
    return baseRoute;
  }
  const byPointId = new Map(overlays.map((item) => [item.point_id, item]));
  const points = baseRoute.points.map((point) => {
    const overlay = byPointId.get(point.id);
    if (!overlay) {
      return point;
    }
    return {
      ...point,
      status: overlay.status
    };
  });
  return {
    ...baseRoute,
    points
  } as RouteDto;
}

async function refreshDriverRoutes(): Promise<void> {
  if (!authToken.value || !isDriver.value) {
    return;
  }
  driverRoutesLoading.value = true;
  try {
    const assigned = await listDriverRoutes(authToken.value, "assigned");
    const history = await listDriverRoutes(authToken.value, "history");
    driverAssignedRoutes.value = assigned.items;
    driverHistoryRoutes.value = history.items;

    if (assigned.active_route_id) {
      if (!route.value || route.value.id !== assigned.active_route_id) {
        const activeRoute = await getDriverRoute(authToken.value, assigned.active_route_id);
        route.value = await applyOverlaysToRoute(activeRoute);
        await saveActiveRoute(route.value);
      }
    } else {
      route.value = null;
      await saveActiveRoute(null);
    }
  } catch (error) {
    syncMessage.value = `Ошибка загрузки рейсов: ${(error as Error).message}`;
  } finally {
    driverRoutesLoading.value = false;
  }
}

async function refreshRoute(): Promise<void> {
  if (!authToken.value || !isDriver.value) {
    return;
  }
  try {
    const serverRoute = await getActiveRoute(authToken.value);
    const merged = await applyOverlaysToRoute(serverRoute);
    route.value = merged;
    await saveActiveRoute(merged);
  } catch (error) {
    syncMessage.value = `Режим офлайн: ${(error as Error).message}`;
  }
}

function onOnline(): void {
  syncMessage.value = "Онлайн: синхронизация возобновлена";
  if (authToken.value) {
    connectNotificationsSocket();
    void refreshNotifications();
  }
  if (isDriver.value) {
    void syncOutboxInBackground();
    void refreshDriverRoutes();
  } else if (isRouteManager.value) {
    void refreshAdminRoutes(routeFilters.value);
  }
}

function onOffline(): void {
  syncMessage.value = "Офлайн: изменения сохраняются локально";
  closeNotificationsSocket();
}

async function syncOutboxInBackground(): Promise<void> {
  if (!authToken.value || !isDriver.value) {
    return;
  }
  if (!navigator.onLine || syncing.value) {
    return;
  }
  const deviceId = getDeviceId();
  const outbox = await getOutboxEvents(deviceId);
  if (!outbox.length) {
    return;
  }

  syncing.value = true;
  try {
    const events: EventPayload[] = outbox.map((event) => ({
      client_event_id: event.client_event_id,
      occurred_at_client: event.occurred_at_client,
      point_id: event.point_id,
      to_status: event.to_status,
      odometer: null,
      coordinates: null
    }));
    const result = await sendEventsBatch(authToken.value, deviceId, events);
    const removable = result.items.filter((item) => item.applied || item.duplicate).map((item) => item.client_event_id);
    await removeOutboxByClientEventIds(removable);
    const appliedPointIds = result.items.filter((item) => item.applied || item.duplicate).map((item) => item.point_id);
    if (route.value && appliedPointIds.length) {
      await removePointOverlays(route.value.id, appliedPointIds);
    }
    await refreshRoute();
    await refreshDriverRoutes();
  } catch (error) {
    console.debug("[pwa-sync] background sync failed", error);
  } finally {
    syncing.value = false;
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

async function doCreateAdminUser(payload: {
  login: string;
  password: string;
  role_code: string;
  full_name?: string | null;
  phone?: string | null;
}): Promise<void> {
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
  } finally {
    usersLoading.value = false;
  }
}

async function doUpdateAdminUser(
  userId: number,
  payload: { login?: string; password?: string; role_code?: string; full_name?: string | null; phone?: string | null; is_active?: boolean }
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
  } finally {
    usersLoading.value = false;
  }
}

async function doDeleteAdminUser(userId: number): Promise<void> {
  if (!authToken.value || !isAdmin.value) {
    return;
  }
  usersLoading.value = true;
  usersError.value = "";
  try {
    await deleteAdminUser(authToken.value, userId);
    await refreshAdminUsers();
  } catch (error) {
    usersError.value = `Ошибка удаления: ${(error as Error).message}`;
  } finally {
    usersLoading.value = false;
  }
}

async function refreshRouteDrivers(): Promise<void> {
  if (!authToken.value || !isRouteManager.value) {
    return;
  }
  try {
    routeDrivers.value = await listRouteDrivers(authToken.value);
  } catch (error) {
    routesError.value = `Ошибка загрузки водителей: ${(error as Error).message}`;
  }
}

async function refreshAdminRoutes(filters?: RouteFilters): Promise<void> {
  if (!authToken.value || !isRouteManager.value) {
    return;
  }
  routesLoading.value = true;
  routesError.value = "";
  try {
    const effectiveFilters = filters ?? routeFilters.value;
    routeFilters.value = effectiveFilters;
    adminRoutes.value = await listAdminRoutes(authToken.value, effectiveFilters);
    if (selectedAdminRoute.value) {
      const selected = adminRoutes.value.find((item) => item.id === selectedAdminRoute.value?.id);
      if (selected) {
        selectedAdminRoute.value = await getAdminRoute(authToken.value, selected.id);
      } else if (currentSection.value === "admin_route_details") {
        selectedAdminRoute.value = null;
        currentSection.value = "admin_routes";
      }
    }
  } catch (error) {
    routesError.value = `Ошибка загрузки рейсов: ${(error as Error).message}`;
  } finally {
    routesLoading.value = false;
  }
}

async function doCreateAdminRoute(payload: AdminRouteCreatePayload): Promise<void> {
  if (!authToken.value || !isRouteManager.value) {
    return;
  }
  routesLoading.value = true;
  routesError.value = "";
  try {
    const routeCreated = await createAdminRoute(authToken.value, payload);
    await refreshAdminRoutes(routeFilters.value);
    selectedAdminRoute.value = await getAdminRoute(authToken.value, routeCreated.id);
    currentSection.value = "admin_route_details";
  } catch (error) {
    routesError.value = `Ошибка создания рейса: ${(error as Error).message}`;
  } finally {
    routesLoading.value = false;
  }
}

async function doUpdateAdminRoute(
  routeId: string,
  payload: {
    number_auto?: string;
    temperature?: string;
    dispatcher_contacts?: string;
    registration_number?: string;
    trailer_number?: string;
    points?: AdminRouteCreatePayload["points"];
  }
): Promise<void> {
  if (!authToken.value || !isRouteManager.value) {
    return;
  }
  routesLoading.value = true;
  routesError.value = "";
  try {
    await updateAdminRoute(authToken.value, routeId, payload);
    selectedAdminRoute.value = await getAdminRoute(authToken.value, routeId);
    await refreshAdminRoutes(routeFilters.value);
  } catch (error) {
    routesError.value = `Ошибка редактирования рейса: ${(error as Error).message}`;
  } finally {
    routesLoading.value = false;
  }
}

async function doSelectAdminRoute(routeId: string): Promise<void> {
  if (!authToken.value || !isRouteManager.value) {
    return;
  }
  routesLoading.value = true;
  routesError.value = "";
  try {
    selectedAdminRoute.value = await getAdminRoute(authToken.value, routeId);
    currentSection.value = "admin_route_details";
  } catch (error) {
    routesError.value = `Ошибка загрузки рейса: ${(error as Error).message}`;
  } finally {
    routesLoading.value = false;
  }
}

function openAdminRouteList(): void {
  profileMenuOpen.value = false;
  currentSection.value = "admin_routes";
}

async function doAssignAdminRoute(routeId: string, driverUserId: number): Promise<void> {
  if (!authToken.value || !isRouteManager.value) {
    return;
  }
  routesLoading.value = true;
  routesError.value = "";
  try {
    await assignAdminRouteDriver(authToken.value, routeId, driverUserId);
    selectedAdminRoute.value = await getAdminRoute(authToken.value, routeId);
    await refreshAdminRoutes(routeFilters.value);
  } catch (error) {
    routesError.value = `Ошибка назначения водителя: ${(error as Error).message}`;
  } finally {
    routesLoading.value = false;
  }
}

async function doCancelAdminRoute(routeId: string): Promise<void> {
  if (!authToken.value || !isRouteManager.value) {
    return;
  }
  routesLoading.value = true;
  routesError.value = "";
  try {
    await cancelAdminRoute(authToken.value, routeId);
    selectedAdminRoute.value = await getAdminRoute(authToken.value, routeId);
    await refreshAdminRoutes(routeFilters.value);
  } catch (error) {
    routesError.value = `Ошибка отмены рейса: ${(error as Error).message}`;
  } finally {
    routesLoading.value = false;
  }
}

async function doDeleteAdminRoute(routeId: string): Promise<void> {
  if (!authToken.value || !isRouteManager.value) {
    return;
  }
  routesLoading.value = true;
  routesError.value = "";
  try {
    await deleteAdminRoute(authToken.value, routeId);
    selectedAdminRoute.value = null;
    currentSection.value = "admin_routes";
    await refreshAdminRoutes(routeFilters.value);
    await refreshNotifications();
  } catch (error) {
    routesError.value = `Ошибка удаления рейса: ${(error as Error).message}`;
  } finally {
    routesLoading.value = false;
  }
}

async function refreshNotifications(): Promise<void> {
  if (!authToken.value) {
    return;
  }
  notificationsLoading.value = true;
  notificationsError.value = "";
  try {
    const latestNotifications = await listNotifications(authToken.value, 50);
    latestNotifications.forEach((item) => handleIncomingNotification(item, { playEffects: false, syncDriverState: true }));
    notifications.value = latestNotifications;
    unreadNotificationsCount.value = await getUnreadNotificationsCount(authToken.value);
  } catch (error) {
    notificationsError.value = `Ошибка загрузки уведомлений: ${(error as Error).message}`;
  } finally {
    notificationsLoading.value = false;
  }
}

async function doMarkNotificationRead(notificationId: number): Promise<void> {
  if (!authToken.value) {
    return;
  }
  try {
    const updated = await markNotificationRead(authToken.value, notificationId);
    notifications.value = notifications.value.map((item) => (item.id === updated.id ? updated : item));
    unreadNotificationsCount.value = Math.max(0, unreadNotificationsCount.value - 1);
  } catch (error) {
    notificationsError.value = `Ошибка отметки прочитанного: ${(error as Error).message}`;
  }
}

async function doMarkAllNotificationsRead(): Promise<void> {
  if (!authToken.value) {
    return;
  }
  try {
    await markAllNotificationsRead(authToken.value);
    notifications.value = notifications.value.map((item) => ({ ...item, is_read: true }));
    unreadNotificationsCount.value = 0;
  } catch (error) {
    notificationsError.value = `Ошибка отметки прочитанного: ${(error as Error).message}`;
  }
}

async function openRouteFromNotification(routeId: string, notificationId: number): Promise<void> {
  if (!authToken.value || !authUser.value) {
    return;
  }
  await doMarkNotificationRead(notificationId);
  profileMenuOpen.value = false;
  notificationsError.value = "";
  if (isDriver.value) {
    try {
      selectedDriverRoute.value = await getDriverRoute(authToken.value, routeId);
      currentSection.value = "driver_route_details";
    } catch (error) {
      syncMessage.value = `Ошибка открытия рейса: ${(error as Error).message}`;
    }
    return;
  }
  if (isRouteManager.value) {
    try {
      selectedAdminRoute.value = await getAdminRoute(authToken.value, routeId);
      currentSection.value = "admin_route_details";
    } catch (error) {
      routesError.value = `Ошибка открытия рейса: ${(error as Error).message}`;
    }
  }
}

async function openActiveRouteFromHome(): Promise<void> {
  if (!route.value || !isDriver.value || !authToken.value) {
    return;
  }
  try {
    await refreshDriverData();
    if (!route.value) {
      currentSection.value = "driver_home";
      return;
    }
    selectedDriverRoute.value = await getDriverRoute(authToken.value, route.value.id);
    currentSection.value = "driver_route_details";
  } catch (error) {
    syncMessage.value = `Ошибка загрузки деталей рейса: ${(error as Error).message}`;
  }
}

async function bootstrapByRole(user: AuthUser): Promise<void> {
  if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "default") {
    void Notification.requestPermission();
  }
  connectNotificationsSocket();
  if (isAdminRole(user.role_code)) {
    currentSection.value = "admin_routes";
    await refreshAdminUsers();
    await refreshRouteDrivers();
    await refreshAdminRoutes({ status: "process" });
  } else if (isRouteManagerRole(user.role_code)) {
    currentSection.value = "admin_routes";
    await refreshRouteDrivers();
    await refreshAdminRoutes({ status: "process" });
  } else {
    currentSection.value = "driver_home";
    await refreshDriverRoutes();
    await refreshRoute();
    await syncOutboxInBackground();
    startBackgroundSyncLoop();
  }
  await refreshNotifications();
}

function openRoleMainSection(section: AppSection): void {
  if (!authUser.value) {
    currentSection.value = "driver_home";
    return;
  }
  profileMenuOpen.value = false;
  if (section === "notifications") {
    currentSection.value = "notifications";
    return;
  }
  if (section === "admin_users" && isAdminRole(authUser.value.role_code)) {
    currentSection.value = section;
    return;
  }
  if ((section === "admin_routes" || section === "admin_route_details") && isRouteManagerRole(authUser.value.role_code)) {
    currentSection.value = section === "admin_route_details" && !selectedAdminRoute.value ? "admin_routes" : section;
    return;
  }
  if ((section === "driver_home" || section === "driver_routes") && authUser.value.role_code === "driver") {
    currentSection.value = section;
    return;
  }
  openDefaultSectionByRole(authUser.value);
}

function toggleProfileMenu(): void {
  if (!isAuthed.value) {
    return;
  }
  profileMenuOpen.value = !profileMenuOpen.value;
}

function selectProfileSection(section: AppSection): void {
  openRoleMainSection(section);
}

async function doLogin(loginValue: string, password: string): Promise<void> {
  authError.value = "";
  authLoading.value = true;
  try {
    const result = await loginRequest(loginValue, password);
    authToken.value = result.access_token;
    authUser.value = result.user;
    persistAuth(result.access_token, result.user);
    await bootstrapByRole(result.user);
  } catch (error) {
    authError.value = (error as Error).message;
  } finally {
    authLoading.value = false;
  }
}

async function doAcceptRoute(routeId?: string): Promise<void> {
  if (!authToken.value || !isDriver.value) {
    return;
  }
  const id = routeId ?? route.value?.id;
  if (!id) {
    return;
  }
  try {
    const serverRoute = await acceptRoute(authToken.value, id);
    const merged = await applyOverlaysToRoute(serverRoute);
    route.value = merged;
    selectedDriverRoute.value = merged;
    await saveActiveRoute(merged);
    await refreshDriverRoutes();
    await refreshNotifications();
    syncMessage.value = "Рейс принят";
  } catch (error) {
    syncMessage.value = `Ошибка принятия рейса: ${(error as Error).message}`;
  }
}

async function markPointNext(pointId: number): Promise<void> {
  if (!route.value || !isDriver.value) {
    return;
  }
  const current = route.value.points.find((point) => point.id === pointId);
  if (!current) {
    return;
  }
  const toStatus = nextStatus(current.status);
  if (!toStatus) {
    return;
  }

  const occurredAt = new Date().toISOString();
  const event: EventPayload = {
    client_event_id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    occurred_at_client: occurredAt,
    point_id: pointId,
    to_status: toStatus,
    odometer: null,
    coordinates: null
  };

  current.status = toStatus;
  if (selectedDriverRoute.value?.id === route.value.id) {
    const selectedPoint = selectedDriverRoute.value.points.find((point) => point.id === pointId);
    if (selectedPoint) {
      selectedPoint.status = toStatus;
    }
  }
  await savePointOverlay(route.value.id, pointId, toStatus, occurredAt);
  await saveActiveRoute(route.value);
  await addOutboxEvent({
    ...event,
    device_id: getDeviceId(),
    created_at: new Date().toISOString()
  });
  syncMessage.value = "Изменение сохранено локально";
  await syncOutboxInBackground();
  await refreshRoute();
  await refreshDriverRoutes();
  if (authToken.value && selectedDriverRoute.value?.id) {
    try {
      selectedDriverRoute.value = await getDriverRoute(authToken.value, selectedDriverRoute.value.id);
    } catch {
      // keep current snapshot if details refresh failed
    }
  }
  if (route.value?.status === "success") {
    route.value = null;
    selectedDriverRoute.value = null;
    await saveActiveRoute(null);
    currentSection.value = "driver_home";
  }
}

async function openDriverRouteDetails(routeId: string): Promise<void> {
  if (!authToken.value || !isDriver.value) {
    return;
  }
  try {
    selectedDriverRoute.value = await getDriverRoute(authToken.value, routeId);
    currentSection.value = "driver_route_details";
  } catch (error) {
    syncMessage.value = `Ошибка загрузки деталей рейса: ${(error as Error).message}`;
  }
}

async function refreshDriverData(): Promise<void> {
  await refreshDriverRoutes();
  await refreshRoute();
}

function onDocumentClick(event: MouseEvent): void {
  const target = event.target as HTMLElement | null;
  if (!target?.closest(".profile-wrap")) {
    profileMenuOpen.value = false;
  }
}

function openNotifications(): void {
  profileMenuOpen.value = false;
  currentSection.value = "notifications";
  void refreshNotifications();
}

function openDriverRoutes(): void {
  profileMenuOpen.value = false;
  currentSection.value = "driver_routes";
  void refreshDriverData();
}

function openDriverHome(): void {
  profileMenuOpen.value = false;
  currentSection.value = "driver_home";
  void refreshDriverData();
}

function advanceActivePointFromHome(): void {
  if (!route.value) {
    return;
  }
  const activePoint = route.value.points.find((point) => !isPointDone(point.status));
  if (!activePoint) {
    return;
  }
  void markPointNext(activePoint.id);
}

function logout(): void {
  clearAuth();
}

onMounted(async () => {
  const token = localStorage.getItem(TOKEN_STORAGE_KEY) || "";
  const rawUser = localStorage.getItem(USER_STORAGE_KEY);
  authToken.value = token;
  authUser.value = rawUser ? (JSON.parse(rawUser) as AuthUser) : null;
  route.value = await loadActiveRoute();
  if (authUser.value) {
    openDefaultSectionByRole(authUser.value);
  }
  if (token && authUser.value) {
    await bootstrapByRole(authUser.value);
  }
  window.addEventListener("online", onOnline);
  window.addEventListener("offline", onOffline);
  window.addEventListener("mousedown", onDocumentClick);
});

onUnmounted(() => {
  stopBackgroundSyncLoop();
  closeNotificationsSocket();
  window.removeEventListener("online", onOnline);
  window.removeEventListener("offline", onOffline);
  window.removeEventListener("mousedown", onDocumentClick);
});
</script>

<template>
  <main class="container">
    <header class="topbar">
      <div class="topbar-side">
        <button v-if="isAuthed" class="icon-btn bell-btn" @click="openNotifications">
          🔔
          <span v-if="hasUnreadNotifications" class="notif-dot" />
        </button>
      </div>

      <h1 class="topbar-title">{{ currentPageTitle }}</h1>

      <div class="topbar-side right">
        <div v-if="isAuthed" class="profile-wrap">
          <button class="profile-btn" @click="toggleProfileMenu">
            {{ profileDisplayName }}
            <span class="caret">▾</span>
          </button>
          <div v-if="profileMenuOpen" class="profile-dropdown">
            <p class="profile-name">{{ profileDisplayName }}</p>
            <p class="profile-role">{{ authUser?.role_label }}</p>
            <button
              v-for="item in profileMenuItems"
              :key="item.section"
              class="menu-item"
              @click="selectProfileSection(item.section)"
            >
              {{ item.label }}
            </button>
            <button class="menu-item danger" @click="logout">Выход</button>
          </div>
        </div>
      </div>
    </header>

    <LoginView v-if="!isAuthed" :loading="authLoading" :error="authError" @submit="doLogin" />

    <section v-else-if="isRouteManager && currentSection === 'admin_routes'">
      <AdminRoutesView
        :routes="adminRoutes"
        :drivers="routeDrivers"
        :loading="routesLoading"
        :error="routesError"
        @refresh="refreshAdminRoutes"
        @create="doCreateAdminRoute"
        @select-route="doSelectAdminRoute"
      />
    </section>

    <section v-else-if="isRouteManager && currentSection === 'admin_route_details' && selectedAdminRoute">
      <AdminRouteDetailsView
        :route="selectedAdminRoute"
        :drivers="routeDrivers"
        :loading="routesLoading"
        @back="openAdminRouteList"
        @assign-driver="doAssignAdminRoute"
        @cancel-route="doCancelAdminRoute"
        @delete-route="doDeleteAdminRoute"
        @update-route="doUpdateAdminRoute"
      />
    </section>

    <section v-else-if="isAdmin && currentSection === 'admin_users'">
      <AdminUsersView
        :users="adminUsers"
        :loading="usersLoading"
        :error="usersError"
        @refresh="refreshAdminUsers"
        @create="doCreateAdminUser"
        @update="doUpdateAdminUser"
        @delete="doDeleteAdminUser"
      />
    </section>

    <section v-else-if="isDriver && currentSection === 'driver_home'">
      <DriverHomeView
        :active-route="route"
        :active-route-summary="activeRouteSummary"
        :has-assigned-routes="hasAssignedRoutes"
        :sync-message="syncMessage"
        :syncing="syncing"
        @open-routes="openDriverRoutes"
        @open-active-route="openActiveRouteFromHome"
        @accept-active-route="doAcceptRoute"
        @advance-active-point="advanceActivePointFromHome"
      />
    </section>

    <section v-else-if="isDriver && currentSection === 'driver_routes'">
      <DriverRoutesView
        :assigned="driverAssignedRoutes"
        :history="driverHistoryRoutes"
        :loading="driverRoutesLoading"
        :active-route-id="route?.id || null"
        @back="openDriverHome"
        @open-route="openDriverRouteDetails"
        @refresh="refreshDriverData"
      />
    </section>

    <section v-else-if="isDriver && currentSection === 'driver_route_details' && selectedDriverRoute">
      <DriverRouteDetailsView
        :route="selectedDriverRoute"
        :active-route-id="route?.id || null"
        :syncing="syncing"
        @back="openDriverRoutes"
        @advance-point="markPointNext"
      />
    </section>

    <section v-else-if="currentSection === 'notifications'">
      <NotificationsView
        :items="notifications"
        :loading="notificationsLoading"
        :error="notificationsError"
        :unread-count="unreadNotificationsCount"
        @refresh="refreshNotifications"
        @mark-read="doMarkNotificationRead"
        @mark-all-read="doMarkAllNotificationsRead"
        @open-route="openRouteFromNotification"
      />
    </section>

    <section v-else class="card">
      <h1 v-if="isDriver">Назначенных рейсов нет</h1>
      <h1 v-else>Раздел пуст</h1>
      <p v-if="isDriver">Когда логист или администратор назначит рейс, он появится здесь.</p>
      <p v-else>Выберите раздел в меню профиля.</p>
      <button v-if="isDriver" @click="refreshDriverRoutes">Обновить рейсы</button>
      <p class="hint">{{ syncMessage }}</p>
    </section>
  </main>
</template>

<style scoped>
.container {
  max-width: 1100px;
  margin: 0 auto;
  padding: 1rem;
  color: #f9fafb;
  font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
}
.topbar {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 0.7rem;
  margin-bottom: 0.95rem;
}
.topbar-side {
  display: flex;
  align-items: center;
  min-width: 0;
}
.topbar-side.right {
  justify-content: flex-end;
}
.topbar-title {
  margin: 0;
  text-align: center;
  font-size: 1.05rem;
  font-weight: 700;
}
.icon-btn {
  width: 42px;
  height: 42px;
  border: 1px solid #334155;
  border-radius: 12px;
  background: #0f172a;
  color: #fff;
  font-size: 1.05rem;
  position: relative;
}
.notif-dot {
  position: absolute;
  top: 7px;
  right: 7px;
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #ef4444;
}
.profile-wrap {
  position: relative;
}
.profile-btn {
  border: 1px solid #334155;
  border-radius: 10px;
  background: #0f172a;
  color: #fff;
  padding: 0.45rem 0.65rem;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.caret {
  font-size: 0.8rem;
  color: #cbd5e1;
}
.profile-dropdown {
  position: absolute;
  right: 0;
  top: calc(100% + 0.45rem);
  z-index: 20;
  width: min(260px, 80vw);
  border: 1px solid #334155;
  border-radius: 12px;
  background: #0b1220;
  padding: 0.6rem;
  display: grid;
  gap: 0.35rem;
  box-shadow: 0 12px 30px rgba(2, 6, 23, 0.45);
}
.profile-name {
  margin: 0;
  font-weight: 700;
}
.profile-role {
  margin: 0 0 0.25rem;
  color: #94a3b8;
  font-size: 0.85rem;
}
.menu-item {
  border: 1px solid #334155;
  border-radius: 10px;
  background: #111827;
  color: #fff;
  padding: 0.42rem 0.58rem;
  text-align: left;
}
.menu-item.danger {
  background: #7f1d1d;
  border-color: #7f1d1d;
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
@media (max-width: 760px) {
  .container {
    padding: 0.75rem;
  }
  .topbar {
    grid-template-columns: auto 1fr auto;
  }
  .topbar-title {
    font-size: 0.95rem;
  }
  .profile-btn {
    max-width: 160px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}
</style>
