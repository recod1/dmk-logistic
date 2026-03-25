<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";

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
  completeAdminRoute,
  createAdminRoute,
  createAdminUser,
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
import { nextStatus } from "./status";
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

type AppSection = "driver_home" | "driver_routes" | "driver_route_details" | "notifications" | "admin_users" | "admin_routes";
type RouteFilters = { status?: string; route_id?: string; number_auto?: string; driver_query?: string };

const authToken = ref<string>("");
const authUser = ref<AuthUser | null>(null);
const route = ref<RouteDto | null>(null);
const authLoading = ref(false);
const authError = ref("");
const syncing = ref(false);
const syncMessage = ref("Готово");
const isOnline = ref(navigator.onLine);
const currentSection = ref<AppSection>("driver_home");
const driverMenuOpen = ref(false);
const selectedDriverRoute = ref<RouteDto | null>(null);
const selectedDriverRouteId = ref<string | null>(null);
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
const onlineLabel = computed(() => (isOnline.value ? "Онлайн" : "Офлайн"));
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
  if (document.visibilityState === "visible") {
    return;
  }
  if (Notification.permission === "granted") {
    void new Notification(item.title, {
      body: item.message,
      tag: `dmk-notification-${item.id}`
    });
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
          const exists = notifications.value.some((item) => item.id === payload.item?.id);
          if (!exists) {
            notifications.value = [payload.item, ...notifications.value].slice(0, 50);
            showBrowserPushNotification(payload.item);
          }
          unreadNotificationsCount.value += payload.item.is_read ? 0 : 1;
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
  selectedDriverRouteId.value = null;
  driverAssignedRoutes.value = [];
  driverHistoryRoutes.value = [];
  adminUsers.value = [];
  adminRoutes.value = [];
  routeDrivers.value = [];
  selectedAdminRoute.value = null;
  notifications.value = [];
  unreadNotificationsCount.value = 0;
  currentSection.value = "driver_home";
  driverMenuOpen.value = false;
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(USER_STORAGE_KEY);
}

function openDefaultSectionByRole(user: AuthUser): void {
  if (isAdminRole(user.role_code)) {
    currentSection.value = "admin_users";
    return;
  }
  if (isRouteManagerRole(user.role_code)) {
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
    if (!route.value && assigned.active_route_id) {
      const activeRoute = await getDriverRoute(authToken.value, assigned.active_route_id);
      route.value = await applyOverlaysToRoute(activeRoute);
      await saveActiveRoute(route.value);
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

async function syncOutboxInBackground(): Promise<void> {
  if (!authToken.value || !isDriver.value) {
    return;
  }
  if (!navigator.onLine) {
    return;
  }
  if (syncing.value) {
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
  } catch (error) {
    routesError.value = `Ошибка загрузки рейса: ${(error as Error).message}`;
  } finally {
    routesLoading.value = false;
  }
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

async function doCompleteAdminRoute(routeId: string): Promise<void> {
  if (!authToken.value || !isRouteManager.value) {
    return;
  }
  routesLoading.value = true;
  routesError.value = "";
  try {
    await completeAdminRoute(authToken.value, routeId);
    selectedAdminRoute.value = await getAdminRoute(authToken.value, routeId);
    await refreshAdminRoutes(routeFilters.value);
  } catch (error) {
    routesError.value = `Ошибка завершения рейса: ${(error as Error).message}`;
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
    notifications.value = await listNotifications(authToken.value, 50);
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

async function bootstrapByRole(user: AuthUser): Promise<void> {
  if (typeof window !== "undefined" && "Notification" in window && Notification.permission === "default") {
    void Notification.requestPermission();
  }
  connectNotificationsSocket();
  if (isAdminRole(user.role_code)) {
    currentSection.value = "admin_users";
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
  if (section === "notifications") {
    currentSection.value = "notifications";
    return;
  }
  if (section === "admin_users" && isAdminRole(authUser.value.role_code)) {
    currentSection.value = section;
    return;
  }
  if (section === "admin_routes" && isRouteManagerRole(authUser.value.role_code)) {
    currentSection.value = section;
    return;
  }
  if ((section === "driver_home" || section === "driver_routes") && authUser.value.role_code === "driver") {
    currentSection.value = section;
    return;
  }
  openDefaultSectionByRole(authUser.value);
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
  if (route.value?.status === "success") {
    route.value = null;
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
    selectedDriverRouteId.value = routeId;
    currentSection.value = "driver_route_details";
  } catch (error) {
    syncMessage.value = `Ошибка загрузки деталей рейса: ${(error as Error).message}`;
  }
}

function onOnline(): void {
  isOnline.value = true;
  void syncOutboxInBackground();
}

function onOffline(): void {
  isOnline.value = false;
  syncMessage.value = "Офлайн-режим";
}

function openNotifications(): void {
  currentSection.value = "notifications";
  void refreshNotifications();
}

function toggleDriverMenu(): void {
  driverMenuOpen.value = !driverMenuOpen.value;
}

function openDriverHome(): void {
  driverMenuOpen.value = false;
  currentSection.value = "driver_home";
}

function openDriverRoutes(): void {
  driverMenuOpen.value = false;
  currentSection.value = "driver_routes";
  void refreshDriverRoutes();
}

function openDriverSalary(): void {
  driverMenuOpen.value = false;
  syncMessage.value = "Раздел «Зарплата» будет доступен в следующей итерации.";
}

function openDriverRepair(): void {
  driverMenuOpen.value = false;
  syncMessage.value = "Раздел «Ремонт» будет доступен в следующей итерации.";
}

function advanceActivePointFromHome(): void {
  if (!route.value) {
    return;
  }
  const activePoint = route.value.points.find((point) => point.status !== "success");
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
});

onUnmounted(() => {
  stopBackgroundSyncLoop();
  closeNotificationsSocket();
  window.removeEventListener("online", onOnline);
  window.removeEventListener("offline", onOffline);
});
</script>

<template>
  <main class="container">
    <header class="topbar">
      <div>
        <strong>ДМК Логистика</strong>
        <small>{{ onlineLabel }}</small>
      </div>
      <div class="actions">
        <span v-if="authUser">{{ authUser.login }} · {{ authUser.role_label }}</span>
        <button
          v-if="isAuthed && isAdmin"
          :class="{ activeTab: currentSection === 'admin_users' }"
          @click="openRoleMainSection('admin_users')"
        >
          Пользователи
        </button>
        <button
          v-if="isAuthed && isRouteManager"
          :class="{ activeTab: currentSection === 'admin_routes' }"
          @click="openRoleMainSection('admin_routes')"
        >
          Рейсы
        </button>
        <button
          v-if="isAuthed && isDriver"
          :class="{ activeTab: currentSection === 'driver_home' || currentSection === 'driver_routes' || currentSection === 'driver_route_details' }"
          @click="openRoleMainSection('driver_home')"
        >
          Водитель
        </button>
        <button
          v-if="isAuthed"
          :class="{ activeTab: currentSection === 'notifications' }"
          @click="openNotifications"
        >
          Уведомления
          <span v-if="hasUnreadNotifications" class="notif-dot" />
        </button>
        <button v-if="isAuthed" @click="logout">Выход</button>
      </div>
    </header>

    <LoginView v-if="!isAuthed" :loading="authLoading" :error="authError" @submit="doLogin" />

    <section v-else-if="isAdmin && currentSection === 'admin_users'">
      <AdminUsersView
        :users="adminUsers"
        :loading="usersLoading"
        :error="usersError"
        @refresh="refreshAdminUsers"
        @create="doCreateAdminUser"
        @update="doUpdateAdminUser"
      />
    </section>

    <section v-else-if="isRouteManager && currentSection === 'admin_routes'">
      <AdminRoutesView
        :routes="adminRoutes"
        :drivers="routeDrivers"
        :selected-route="selectedAdminRoute"
        :loading="routesLoading"
        :error="routesError"
        @refresh="refreshAdminRoutes"
        @create="doCreateAdminRoute"
        @select-route="doSelectAdminRoute"
        @assign-driver="doAssignAdminRoute"
        @cancel-route="doCancelAdminRoute"
        @complete-route="doCompleteAdminRoute"
        @update-route="doUpdateAdminRoute"
      />
    </section>

    <section v-else-if="isDriver && currentSection === 'driver_home'">
      <DriverHomeView
        :active-route="route"
        :active-route-summary="activeRouteSummary"
        :has-assigned-routes="hasAssignedRoutes"
        :sync-message="syncMessage"
        :syncing="syncing"
        :show-menu="driverMenuOpen"
        :unread-count="unreadNotificationsCount"
        @toggle-menu="toggleDriverMenu"
        @open-notifications="openNotifications"
        @open-routes="openDriverRoutes"
        @open-salary="openDriverSalary"
        @open-repair="openDriverRepair"
        @logout="logout"
        @accept-active-route="doAcceptRoute()"
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
        @refresh="refreshDriverRoutes"
      />
    </section>

    <section v-else-if="isDriver && currentSection === 'driver_route_details' && selectedDriverRoute">
      <DriverRouteDetailsView
        :route="selectedDriverRoute"
        :syncing="syncing"
        @back="openDriverRoutes"
        @accept="doAcceptRoute(selectedDriverRoute.id)"
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
      />
    </section>

    <section v-else class="card">
      <h1 v-if="isDriver">Активного рейса нет</h1>
      <h1 v-else>Раздел пуст</h1>
      <p v-if="isDriver">Когда диспетчер назначит рейс, он появится здесь.</p>
      <p v-else>Выберите раздел в верхнем меню.</p>
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
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-bottom: 0.8rem;
}
.topbar small {
  display: block;
  color: #9ca3af;
}
.actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
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
.actions button {
  width: auto;
  position: relative;
}
.notif-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-left: 6px;
  border-radius: 999px;
  background: #ef4444;
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
  .actions {
    width: 100%;
  }
  .actions > span {
    width: 100%;
  }
  .actions button {
    flex: 1 1 calc(50% - 0.3rem);
    min-width: 0;
  }
}
</style>

