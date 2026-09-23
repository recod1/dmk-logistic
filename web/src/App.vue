<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch, watchEffect } from "vue";
import type { RoleCode } from "./roles";

import AdminErrorDebugPanel from "./components/AdminErrorDebugPanel.vue";
import AdminRouteDetailsView from "./components/AdminRouteDetailsView.vue";
import AdminRoutesView from "./components/AdminRoutesView.vue";
import AdminUsersView from "./components/AdminUsersView.vue";
import AdminLogisticsContactsView from "./components/AdminLogisticsContactsView.vue";
import BottomNav from "./components/BottomNav.vue";
import type { BottomNavItem } from "./components/BottomNav.vue";
import HeaderNav from "./components/HeaderNav.vue";
import ConnectionStatusBadge from "./components/ConnectionStatusBadge.vue";
import ChatView from "./components/ChatView.vue";
import ChatsHubView from "./components/ChatsHubView.vue";
import DriverSalaryView from "./components/DriverSalaryView.vue";
import AccountantSalaryView from "./components/AccountantSalaryView.vue";
import SalaryDetailView from "./components/SalaryDetailView.vue";
import DriverHomeView from "./components/DriverHomeView.vue";
import DocsUploadDialog from "./components/DocsUploadDialog.vue";
import DriverRouteDetailsView from "./components/DriverRouteDetailsView.vue";
import DriverRoutesView from "./components/DriverRoutesView.vue";
import LoginView from "./components/LoginView.vue";
import MapsChooser from "./components/MapsChooser.vue";
import NotificationsView from "./components/NotificationsView.vue";
import StatusConfirmDialog from "./components/StatusConfirmDialog.vue";
import {
  ApiError,
  API_BASE,
  acceptRoute,
  assignAdminRouteDriver,
  cancelAdminRoute,
  createAdminRouteFromOnec,
  createAdminRoute,
  createAdminUser,
  deleteAdminRoute,
  deleteAdminUser,
  getActiveRoute,
  getAdminRoute,
  getDriverRoute,
  getPointTelemetry,
  getUnreadNotificationsCount,
  getVapidPublicKey,
  getChatUnreadSummary,
  getMyChatUnreadSummary,
  fetchChatAttachmentBlob,
  // chats hub
  postChatsBootstrap,
  listChatRooms,
  listChatUsers,
  listLogisticDriverChatRooms,
  listAccountantDriverChatRooms,
  listAdminChatRooms,
  adminCreateChatRoom,
  adminPatchChatRoom,
  adminDeleteChatRoom,
  adminBroadcastByRoles,
  openDirectChat,
  listChatRoomMessages,
  sendChatRoomMessage,
  uploadChatRoomAttachments,
  fetchChatRoomAttachmentBlob,
  type SalaryRecord,
  type LogisticsContact,
  listMySalaries,
  fetchMySalaryCsvBlob,
  fetchDriverSalaryCsvBlob,
  lookupSalaryDrivers,
  createSalaryManual,
  listSalariesForDriver,
  getSalary,
  confirmSalary,
  commentSalary,
  deleteSalary,
  isOfflineLikeError,
  isPageHidden,
  listSalaryChatMessages,
  sendSalaryChatMessage,
  uploadSalaryChatAttachments,
  fetchSalaryChatAttachmentBlob,
  listLogisticsContacts,
  saveLogisticsContacts,
  listAdminRoutes,
  listAdminUsers,
  listDriverRoutes,
  prefetchDriverAssignedRoutes,
  listNotifications,
  listRouteDrivers,
  listRouteLogistics,
  login as loginRequest,
  markAllNotificationsRead,
  markNotificationRead,
  chatWebSocketUrl,
  listRouteChatMessages,
  notificationsWebSocketUrl,
  revertPointStatus,
  sendEventsBatch,
  sendRouteChatMessage,
  uploadRouteChatAttachments,
  subscribeWebPush,
  clearWebPushSubscriptions,
  updateAdminRoute,
  updateAdminRoutePoint,
  updateAdminUser,
  uploadPointDocuments
} from "./api";
import {
  addOutboxEvent,
  addPendingAccept,
  getOutboxEvents,
  getPendingAccepts,
  getPendingDocBlob,
  getDriverQueueCounts,
  getPointOverlays,
  loadActiveRoute,
  loadDriverRoutesCache,
  loadRouteSnapshot,
  removeOutboxByClientEventIds,
  removePendingAccept,
  removePendingDocBlobs,
  removePointOverlays,
  saveActiveRoute,
  saveAuthSession,
  clearAuthSession,
  saveDriverRoutesCache,
  savePendingDocBlob,
  savePointOverlay,
  saveRouteSnapshot,
  updateOutboxEventByClientId
} from "./db";
import { DRIVER_PREFETCH_SYNC_TAG, persistPrefetchPayload, prefetchAssignedRoutesFromSession, routeToListItem } from "./offlinePrefetch";
import { fromDatetimeLocalToIso, toDatetimeLocalValue } from "./datetimeLocal";
import { prepareDocumentImageBlobs } from "./imageUploadPrep";
import { isAccountantRole, isAdminRole, isLogisticRole, isRouteManagerRole } from "./roles";
import { isPointDone, nextStatus, nextStatusLabel } from "./status";
import {
  connectionHint,
  connectionServerOk,
  noteForegroundResume,
  pingServer,
  restartConnectionWatch,
  setChatWsState,
  setConnectionQueue,
  setConnectionSyncing,
  setNotificationsWsState,
  startConnectionWatch,
  stopConnectionWatch
} from "./connectionWatch";
import { latestDebugError, markDebugErrorsRead, reportDebugError, unreadDebugCount } from "./debugLog";
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
const PENDING_NOTIFICATION_READS_KEY = "dmk_pending_notification_reads";
const USER_STORAGE_KEY = "dmk_mobile_user";
const DEVICE_ID_STORAGE_KEY = "dmk_mobile_device_id";

type AppSection =
  | "driver_home"
  | "driver_routes"
  | "driver_route_details"
  | "chat"
  | "chat_room"
  | "chats"
  | "notifications"
  | "admin_users"
  | "admin_logistics_contacts"
  | "admin_routes"
  | "admin_route_details"
  | "driver_salary"
  | "salary_accounting"
  | "salary_detail"
  | "salary_chat";
type RouteFilters = { status?: string; route_id?: string; number_auto?: string; driver_query?: string };

const authToken = ref<string>("");
const authUser = ref<AuthUser | null>(null);
const route = ref<RouteDto | null>(null);
const authLoading = ref(false);
const authError = ref("");
const syncing = ref(false);
const syncMessage = ref("Готово");
const currentSection = ref<AppSection>("driver_home");
const sectionStack = ref<AppSection[]>([]);
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
const routeLogistics = ref<DriverOption[]>([]);
const routesLoading = ref(false);
const routesError = ref("");
const routeFilters = ref<RouteFilters>({ status: "process" });
const appScrollEl = ref<HTMLElement | null>(null);
const keyboardOpen = ref(false);

const notifications = ref<NotificationDto[]>([]);
const notificationsLoading = ref(false);
const notificationsError = ref("");

const chatRouteId = ref<string | null>(null);
const chatMessages = ref<Array<{ id: number; route_id: string; user_id: number; author_name: string; text: string; created_at: string; read?: boolean }>>([]);
const chatLoading = ref(false);
const chatError = ref("");
const chatUnreadByRoute = ref<Record<string, number>>({});

const driverActiveRouteId = ref<string | null>(null);
const useLegacyBrowserNotification = ref(true);
const statusConfirm = ref<{
  pointId: number;
  nextLabel: string;
  datetimeLocal: string;
  initialDatetimeLocal: string;
  showOdometer: boolean;
  odometer: string;
  initialOdometer: string;
  odometerPrefillSource: "wialon" | null;
  telemetryLoading: boolean;
} | null>(null);
const docsUpload = ref<{
  pointId: number;
  occurredAtIso: string;
  timeSource: "device" | "manual";
  odometer: string;
  odometer_source: "manual" | "wialon" | null;
} | null>(null);
const docsUploading = ref(false);
const adminDebugOpen = ref(false);
let docsUploadAbort: AbortController | null = null;
let syncGeneration = 0;
let syncWatchdogTimer: number | null = null;

let syncIntervalId: number | null = null;
let notificationsWs: WebSocket | null = null;
let notificationsWsReconnectTimer: number | null = null;
let notificationsWsHandshakeTimer: number | null = null;
let notificationsPingInterval: number | null = null;
let notificationsPollInterval: number | null = null;
let notificationsWsBackoffMs = 4000;
let wsWatchdogTimer: number | null = null;
let refreshAdminRoutesInFlight: Promise<void> | null = null;
const markReadInFlight = new Set<number>();

let chatWs: WebSocket | null = null;
let chatWsReconnectTimer: number | null = null;
let chatWsHandshakeTimer: number | null = null;
let chatPingInterval: number | null = null;
let chatPollInterval: number | null = null;
let roomChatPollInterval: number | null = null;
let salaryChatPollInterval: number | null = null;
let chatWsBackoffMs = 4000;
let realtimeSocketsAllowed = false;

// Generic chats hub
const chatsRooms = ref<Array<{ id: number; kind: "direct" | "group"; title: string; unread_count?: number }>>([]);
const chatsUsers = ref<Array<{ id: number; login: string; full_name: string | null; role_code: string; role_label: string }>>([]);
const chatsLoading = ref(false);
const chatsError = ref("");
const roomUnreadBump = ref<Record<number, number>>({});
const logisticDriverChatRooms = ref<
  Array<{
    driver: { id: number; full_name: string | null; login: string };
    room: { id: number; kind: "direct" | "group"; title: string; system_key?: string | null; unread_count?: number };
  }>
>([]);
const accountantDriverChatRooms = ref<
  Array<{
    driver: { id: number; full_name: string | null; login: string };
    room: { id: number; kind: "direct" | "group"; title: string; system_key?: string | null; unread_count?: number };
  }>
>([]);
const adminChatsHubTick = ref(0);
const adminChatRoomsList = ref<
  Array<{
    id: number;
    kind: string;
    title: string;
    system_key: string | null;
    member_user_ids: number[];
    role_codes: string[];
    created_at: string;
  }>
>([]);
const adminChatRoomsLoading = ref(false);
const chatRoomId = ref<number | null>(null);
const chatRoomTitle = ref<string>("");
const chatRoomMessages = ref<any[]>([]);
const chatRoomLoading = ref(false);
const chatRoomError = ref("");

const salaryDriverFilterFrom = ref("");
const salaryDriverFilterTo = ref("");
const salaryListMine = ref<SalaryRecord[]>([]);
const salaryListLoading = ref(false);
const salaryError = ref("");
const salaryCurrentRecord = ref<SalaryRecord | null>(null);
const salaryDetailBusy = ref(false);
const salaryChatSalaryId = ref<number | null>(null);
const salaryChatMessages = ref<any[]>([]);
const salaryChatLoading = ref(false);
const salaryChatError = ref("");
const salaryAccountantDrivers = ref<Array<{ id: number; login: string; full_name: string | null; legacy_tg_id: string | null }>>([]);
const salaryAccountantItems = ref<SalaryRecord[]>([]);
const salarySelectedDriver = ref<{ id: number; login: string; full_name: string | null } | null>(null);
const salarySaving = ref(false);
const salaryDetailBackSection = ref<AppSection>("driver_salary");
const logisticsContacts = ref<LogisticsContact[]>([]);
const logisticsContactsLoading = ref(false);
const logisticsContactsSaving = ref(false);
const logisticsContactsError = ref("");

const isAuthed = computed(() => Boolean(authToken.value));
const isChatSection = computed(
  () => currentSection.value === "chat" || currentSection.value === "chat_room" || currentSection.value === "salary_chat"
);
const isAdmin = computed(() => isAdminRole(authUser.value?.role_code || ""));
const isRouteManager = computed(() => isRouteManagerRole(authUser.value?.role_code || ""));
const isDriver = computed(() => authUser.value?.role_code === "driver");
const isLogistic = computed(() => isLogisticRole(authUser.value?.role_code || ""));
const isAccountant = computed(() => isAccountantRole(authUser.value?.role_code || ""));

const chatsRoomsForDisplay = computed(() => {
  const bump = roomUnreadBump.value;
  return chatsRooms.value.map((r) => ({
    ...r,
    unread_count: (r.unread_count ?? 0) + (bump[r.id] ?? 0)
  }));
});

const logisticDriverChatRoomsDisplay = computed(() => {
  const bump = roomUnreadBump.value;
  return logisticDriverChatRooms.value.map((row) => ({
    ...row,
    room: {
      ...row.room,
      unread_count: (row.room.unread_count ?? 0) + (bump[row.room.id] ?? 0)
    }
  }));
});

const accountantDriverChatRoomsDisplay = computed(() => {
  const bump = roomUnreadBump.value;
  return accountantDriverChatRooms.value.map((row) => ({
    ...row,
    room: {
      ...row.room,
      unread_count: (row.room.unread_count ?? 0) + (bump[row.room.id] ?? 0)
    }
  }));
});

const hasUnreadGenericChats = computed(() => {
  if (Object.values(roomUnreadBump.value).some((count) => Number(count) > 0)) return true;
  if (chatsRoomsForDisplay.value.some((r) => (r.unread_count ?? 0) > 0)) return true;
  if (logisticDriverChatRoomsDisplay.value.some((row) => (row.room.unread_count ?? 0) > 0)) return true;
  if (accountantDriverChatRoomsDisplay.value.some((row) => (row.room.unread_count ?? 0) > 0)) return true;
  return false;
});

const hasUnreadRouteChats = computed(() => Object.values(chatUnreadByRoute.value).some((count) => Number(count) > 0));
const hasUnreadChatsNav = computed(() => hasUnreadGenericChats.value || hasUnreadRouteChats.value);

const salaryChatItemsForChatView = computed(() => {
  const sid = salaryChatSalaryId.value;
  if (!sid) return [];
  return salaryChatMessages.value.map((m: Record<string, unknown>) => ({ ...m, route_id: String(sid) }));
});

const activeRouteSummary = computed(() => {
  if (!route.value) {
    return null;
  }
  return driverAssignedRoutes.value.find((item) => item.id === route.value?.id) ?? null;
});
const hasAssignedRoutes = computed(() => driverAssignedRoutes.value.some((item) => item.status === "new"));
const hasUnreadNotifications = computed(() => unreadNotificationsCount.value > 0);
const pushIsSupported = computed(() => {
  if (typeof window === "undefined") return false;
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
});
const pushInProgress = ref(false);
const pushLastError = ref("");
const pushLastOkAt = ref<string | null>(null);
const webPushSubscribed = ref(false);
const pushHint = computed(() => {
  if (typeof window === "undefined" || !("Notification" in window)) {
    return "";
  }
  if (pushInProgress.value) {
    return "Сохранение подписки…";
  }
  if (Notification.permission === "denied") {
    return "Уведомления заблокированы в браузере/Android. Разрешите уведомления для сайта и переоткройте приложение.";
  }
  if (webPushSubscribed.value) {
    return pushLastOkAt.value
      ? `Push активен (подписка оформлена ${pushLastOkAt.value}). Нажмите «Выключить push», чтобы отписаться.`
      : "Push активен. Нажмите «Выключить push», чтобы отписаться.";
  }
  if (pushLastError.value) {
    return `Push не включён: ${pushLastError.value}`;
  }
  if (useLegacyBrowserNotification.value) {
    return "Нажмите «Включить push» и разрешите уведомления, чтобы получать события в фоне.";
  }
  return "";
});

async function refreshWebPushSubscriptionState(): Promise<void> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator) || !("PushManager" in window)) {
    webPushSubscribed.value = false;
    return;
  }
  try {
    const registration = await navigator.serviceWorker.ready;
    const sub = await registration.pushManager.getSubscription();
    webPushSubscribed.value = Boolean(sub?.endpoint);
    if (webPushSubscribed.value) {
      useLegacyBrowserNotification.value = false;
    }
  } catch {
    webPushSubscribed.value = false;
  }
}

function updateUiNotificationIndicators(): void {
  if (typeof document !== "undefined") {
    const base = `ДМК · ${currentPageTitle.value}`;
    const unread = unreadNotificationsCount.value;
    document.title = unread > 0 ? `(${unread}) ${base}` : base;
  }

  const unread = unreadNotificationsCount.value;
  const nav = navigator as Navigator & {
    setAppBadge?: (count?: number) => Promise<void>;
    clearAppBadge?: () => Promise<void>;
  };
  // iOS Safari/PWA can expose setAppBadge without clearAppBadge (version-dependent).
  // Prefer clearAppBadge when available; otherwise fall back to setAppBadge(0).
  if (typeof nav?.setAppBadge === "function") {
    if (unread > 0) {
      void nav.setAppBadge(unread);
    } else if (typeof nav?.clearAppBadge === "function") {
      void nav.clearAppBadge();
    } else {
      void nav.setAppBadge(0);
    }
  }
}

watchEffect(() => {
  // Keep tab title + badge in sync while app runs in browser / installed PWA.
  void currentPageTitle.value;
  void unreadNotificationsCount.value;
  updateUiNotificationIndicators();
});

function isAuthError(error: unknown): boolean {
  if (error instanceof ApiError) {
    return error.status === 401;
  }
  const msg = (error as Error | null)?.message || "";
  return msg.includes("Invalid access token") || msg.includes("invalid access token");
}

function handleAuthError(error: unknown, ctx: { userMessage?: string } = {}): boolean {
  if (!isAuthError(error)) {
    return false;
  }
  syncMessage.value = ctx.userMessage || "Сессия истекла. Пожалуйста, войдите заново.";
  clearAuth();
  return true;
}

const canAcceptSelectedDriverRoute = computed(() => {
  if (!isDriver.value || !selectedDriverRoute.value) {
    return false;
  }
  const selected = selectedDriverRoute.value;
  if (selected.status !== "new") {
    return false;
  }
  const anotherAccepted =
    (route.value && route.value.id !== selected.id && route.value.status === "process") ||
    driverAssignedRoutes.value.some((item) => item.status === "process" && item.id !== selected.id);
  if (anotherAccepted) {
    return false;
  }
  if (!driverActiveRouteId.value) {
    return true;
  }
  return selected.id === driverActiveRouteId.value || selected.id === route.value?.id;
});

const currentPageTitle = computed(() => {
  if (!isAuthed.value) {
    return "Вход";
  }
  if (currentSection.value === "driver_home") {
    return "Главная";
  }
  if (
    currentSection.value === "driver_routes" ||
    currentSection.value === "driver_route_details" ||
    currentSection.value === "admin_routes" ||
    currentSection.value === "admin_route_details"
  ) {
    return "Рейсы";
  }
  if (currentSection.value === "admin_users") {
    return "Пользователи";
  }
  if (currentSection.value === "admin_logistics_contacts") {
    return "Настройки";
  }
  if (currentSection.value === "notifications") {
    return "Уведомления";
  }
  if (currentSection.value === "chats") {
    return "Чаты";
  }
  if (currentSection.value === "chat_room") {
    return "Чаты";
  }
  if (currentSection.value === "driver_salary" || currentSection.value === "salary_accounting") {
    return "Зарплата";
  }
  if (currentSection.value === "salary_detail") {
    return "Расчёт";
  }
  if (currentSection.value === "salary_chat") {
    return "Чат расчёта";
  }
  return "ДМК";
});

const profileDisplayName = computed(() => authUser.value?.full_name || authUser.value?.login || "");

const profileInitials = computed(() => {
  const name = profileDisplayName.value.trim();
  if (!name) return "ДМК";
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0] ?? ""}${parts[1][0] ?? ""}`.toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
});

const toastText = ref("");
const resettingConnections = ref(false);
let toastTimer: number | null = null;

watch(syncMessage, (value) => {
  const message = (value || "").trim();
  if (!message || message === "Готово") {
    toastText.value = "";
    return;
  }
  toastText.value = message;
  if (toastTimer) {
    window.clearTimeout(toastTimer);
  }
  toastTimer = window.setTimeout(() => {
    toastText.value = "";
  }, 3200);
});

const toastVisible = computed(() => Boolean(toastText.value));

watch(
  () => latestDebugError.value?.id ?? 0,
  (id, prev) => {
    if (!id || id === prev || !isAdmin.value || !isAuthed.value) {
      return;
    }
    adminDebugOpen.value = true;
  }
);

async function refreshConnectionQueue(): Promise<void> {
  try {
    const counts = await getDriverQueueCounts(getDeviceId());
    setConnectionQueue(counts);
  } catch {
    // ignore queue snapshot errors
  }
}

function onConnectionBadgeClick(): void {
  if (isAdmin.value) {
    adminDebugOpen.value = true;
    markDebugErrorsRead();
    return;
  }
  syncMessage.value = connectionHint.value;
}

const profileMenuItems = computed<Array<{ section: AppSection; label: string; tabBar?: boolean; headerNav?: boolean }>>(() => {
  if (!authUser.value) {
    return [];
  }
  if (isAdminRole(authUser.value.role_code)) {
    return [
      { section: "admin_routes", label: "Рейсы", tabBar: true, headerNav: true },
      { section: "chats", label: "Чаты", tabBar: true, headerNav: true },
      { section: "salary_accounting", label: "Зарплата", tabBar: true, headerNav: true },
      { section: "admin_users", label: "Пользователи", headerNav: true },
      { section: "admin_logistics_contacts", label: "Настройки", headerNav: true }
    ];
  }
  if (isRouteManagerRole(authUser.value.role_code)) {
    const items: Array<{ section: AppSection; label: string; tabBar?: boolean; headerNav?: boolean }> = [
      { section: "admin_routes", label: "Рейсы", headerNav: true },
      { section: "chats", label: "Чаты", headerNav: true }
    ];
    if (isAccountantRole(authUser.value.role_code)) {
      items.push({ section: "salary_accounting", label: "Зарплата", headerNav: true });
    }
    return items;
  }
  return [
    { section: "driver_home", label: "Главная", tabBar: true, headerNav: true },
    { section: "driver_routes", label: "Рейсы", tabBar: true, headerNav: true },
    { section: "chats", label: "Чаты", tabBar: true, headerNav: true },
    { section: "driver_salary", label: "Зарплата", tabBar: true, headerNav: true }
  ];
});

const bottomNavItems = computed<BottomNavItem[]>(() => {
  if (isDriver.value) {
    return [
      { id: "home", label: "Главная", section: "driver_home" },
      { id: "routes", label: "Рейсы", section: "driver_routes" },
      { id: "chats", label: "Чаты", section: "chats" },
      { id: "salary", label: "Зарплата", section: "driver_salary" }
    ];
  }
  if (isAdmin.value) {
    return [
      { id: "routes", label: "Рейсы", section: "admin_routes" },
      { id: "chats", label: "Чаты", section: "chats" },
      { id: "salary", label: "Зарплата", section: "salary_accounting" }
    ];
  }
  return [];
});

const showBottomNav = computed(() => isAuthed.value && bottomNavItems.value.length > 0);

const headerNavItems = computed<BottomNavItem[]>(() =>
  profileMenuItems.value
    .filter((item) => item.headerNav)
    .map((item) => {
      let id: BottomNavItem["id"] = "routes";
      if (item.section === "driver_home") {
        id = "home";
      } else if (item.section === "chats") {
        id = "chats";
      } else if (item.section === "driver_salary" || item.section === "salary_accounting") {
        id = "salary";
      } else if (item.section === "admin_users") {
        id = "users";
      } else if (item.section === "admin_logistics_contacts") {
        id = "settings";
      }
      return { id, label: item.label, section: item.section };
    })
);

const showHeaderNav = computed(() => isAuthed.value && headerNavItems.value.length > 0);

const activeBottomNavId = computed(() => {
  const section = currentSection.value;
  if (section === "driver_home") {
    return "home";
  }
  if (
    section === "driver_routes" ||
    section === "driver_route_details" ||
    section === "admin_routes" ||
    section === "admin_route_details"
  ) {
    return "routes";
  }
  if (section === "admin_users") {
    return "users";
  }
  if (section === "admin_logistics_contacts") {
    return "settings";
  }
  if (section === "chats" || section === "chat" || section === "chat_room") {
    return "chats";
  }
  if (
    section === "driver_salary" ||
    section === "salary_accounting" ||
    section === "salary_detail" ||
    section === "salary_chat"
  ) {
    return "salary";
  }
  return null;
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

async function persistAuth(token: string, user: AuthUser): Promise<void> {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
  localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user));
  await saveAuthSession({
    token,
    apiBase: API_BASE,
    roleCode: user.role_code
  });
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
    void prefetchAssignedRoutesFromSession();
    void syncOutboxInBackground();
    void refreshConnectionQueue();
  }, 15000);
  void prefetchAssignedRoutesFromSession();
  void registerDriverBackgroundSync();
  void refreshConnectionQueue();
}

async function registerDriverBackgroundSync(): Promise<void> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator) || !isDriver.value) {
    return;
  }
  try {
    const registration = await navigator.serviceWorker.ready;
    registration.active?.postMessage({ type: "DMK_PREFETCH" });
    const syncManager = (registration as ServiceWorkerRegistration & { sync?: { register: (tag: string) => Promise<void> } }).sync;
    if (syncManager) {
      await syncManager.register(DRIVER_PREFETCH_SYNC_TAG);
    }
    const periodic = (
      registration as ServiceWorkerRegistration & {
        periodicSync?: { register: (tag: string, options: { minInterval: number }) => Promise<void> };
      }
    ).periodicSync;
    if (periodic) {
      try {
        const status = await navigator.permissions.query({ name: "periodic-background-sync" as PermissionName });
        if (status.state === "granted") {
          await periodic.register(DRIVER_PREFETCH_SYNC_TAG, { minInterval: 15 * 60 * 1000 });
        }
      } catch {
        await periodic.register(DRIVER_PREFETCH_SYNC_TAG, { minInterval: 15 * 60 * 1000 });
      }
    }
  } catch {
    // Background sync is best-effort: iOS and some browsers may not support it.
  }
}

function isCoarseUi(): boolean {
  return Boolean(window.matchMedia?.("(pointer: coarse)")?.matches);
}

function wsHandshakeTimeoutMs(): number {
  return isCoarseUi() ? 15_000 : 10_000;
}

function stopWsWatchdog(): void {
  if (wsWatchdogTimer !== null) {
    window.clearInterval(wsWatchdogTimer);
    wsWatchdogTimer = null;
  }
}

function startWsWatchdog(): void {
  stopWsWatchdog();
  wsWatchdogTimer = window.setInterval(() => {
    if (!authToken.value || !realtimeSocketsAllowed || isPageHidden() || !hasNetwork()) {
      return;
    }
    const state = notificationsWs?.readyState;
    if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) {
      return;
    }
    forceReconnectRealtimeSockets();
  }, isCoarseUi() ? 12_000 : 8_000);
}

function allowRealtimeSockets(): void {
  realtimeSocketsAllowed = true;
  startWsWatchdog();
}

function denyRealtimeSockets(): void {
  realtimeSocketsAllowed = false;
  stopWsWatchdog();
}

function wsBusy(ws: WebSocket | null): boolean {
  return Boolean(ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING));
}

function clearNotificationsHandshakeTimer(): void {
  if (notificationsWsHandshakeTimer !== null) {
    window.clearTimeout(notificationsWsHandshakeTimer);
    notificationsWsHandshakeTimer = null;
  }
}

function clearChatHandshakeTimer(): void {
  if (chatWsHandshakeTimer !== null) {
    window.clearTimeout(chatWsHandshakeTimer);
    chatWsHandshakeTimer = null;
  }
}

function armWsHandshakeTimer(ws: WebSocket, kind: "notifications" | "chat"): void {
  const arm = (setter: (id: number | null) => void) => {
    setter(
      window.setTimeout(() => {
        setter(null);
        if (ws.readyState === WebSocket.OPEN) {
          return;
        }
        if (kind === "notifications" && notificationsWs === ws) {
          notificationsWs = null;
          setNotificationsWsState("closed");
        }
        if (kind === "chat" && chatWs === ws) {
          chatWs = null;
          setChatWsState("closed");
        }
        try {
          ws.close();
        } catch {
          // handshake stuck on cellular/HTTP2
        }
        if (!isPageHidden() && authToken.value && realtimeSocketsAllowed) {
          if (kind === "notifications") {
            notificationsWsBackoffMs = isCoarseUi() ? 4000 : 2500;
            connectNotificationsSocket();
          } else {
            chatWsBackoffMs = isCoarseUi() ? 4000 : 2500;
            connectChatSocket();
          }
        }
      }, wsHandshakeTimeoutMs())
    );
  };
  if (kind === "notifications") {
    clearNotificationsHandshakeTimer();
    arm((id) => {
      notificationsWsHandshakeTimer = id;
    });
    return;
  }
  clearChatHandshakeTimer();
  arm((id) => {
    chatWsHandshakeTimer = id;
  });
}

function closeNotificationsSocket(): void {
  clearNotificationsHandshakeTimer();
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
  setNotificationsWsState("idle");
}

function stopNotificationsPolling(): void {
  if (notificationsPollInterval !== null) {
    window.clearInterval(notificationsPollInterval);
    notificationsPollInterval = null;
  }
}

function startNotificationsPolling(): void {
  stopNotificationsPolling();
  const coarse = isCoarseUi();
  notificationsPollInterval = window.setInterval(() => {
    if (!authToken.value) {
      stopNotificationsPolling();
      return;
    }
    if (!hasNetwork() || isPageHidden()) {
      return;
    }
    const nState = notificationsWs?.readyState;
    if (nState === WebSocket.OPEN || nState === WebSocket.CONNECTING) {
      return;
    }
    void refreshNotifications();
  }, coarse ? 20000 : 8000);
}

function closeChatSocket(): void {
  clearChatHandshakeTimer();
  if (chatPingInterval !== null) {
    window.clearInterval(chatPingInterval);
    chatPingInterval = null;
  }
  if (chatWsReconnectTimer !== null) {
    window.clearTimeout(chatWsReconnectTimer);
    chatWsReconnectTimer = null;
  }
  if (chatWs) {
    chatWs.close();
    chatWs = null;
  }
  setChatWsState("idle");
}

function stopChatPolling(): void {
  if (chatPollInterval !== null) {
    window.clearInterval(chatPollInterval);
    chatPollInterval = null;
  }
}

function stopRoomChatPolling(): void {
  if (roomChatPollInterval !== null) {
    window.clearInterval(roomChatPollInterval);
    roomChatPollInterval = null;
  }
}

function startRoomChatPolling(): void {
  stopRoomChatPolling();
  roomChatPollInterval = window.setInterval(() => {
    if (currentSection.value !== "chat_room" || !chatRoomId.value) {
      stopRoomChatPolling();
      return;
    }
    void refreshChatRoom({ silent: true });
  }, 2500);
}

function stopSalaryChatPolling(): void {
  if (salaryChatPollInterval !== null) {
    window.clearInterval(salaryChatPollInterval);
    salaryChatPollInterval = null;
  }
}

function startSalaryChatPolling(): void {
  stopSalaryChatPolling();
  salaryChatPollInterval = window.setInterval(() => {
    if (currentSection.value !== "salary_chat" || !salaryChatSalaryId.value) {
      stopSalaryChatPolling();
      return;
    }
    void refreshSalaryChat({ silent: true });
  }, 2500);
}

function startChatPolling(): void {
  stopChatPolling();
  // Fallback for environments where WS delivery is unreliable:
  // periodically refresh chat while it's open.
  chatPollInterval = window.setInterval(() => {
    if (currentSection.value !== "chat" || !chatRouteId.value) {
      stopChatPolling();
      return;
    }
    void refreshChat({ silent: true });
  }, 2500);
}

function scheduleChatReconnect(): void {
  if (!authToken.value || !realtimeSocketsAllowed || isPageHidden()) {
    return;
  }
  if (chatWsReconnectTimer !== null) {
    return;
  }
  const delay = chatWsBackoffMs;
  chatWsBackoffMs = Math.min(Math.round(delay * 1.8), isCoarseUi() ? 30_000 : 15_000);
  chatWsReconnectTimer = window.setTimeout(() => {
    chatWsReconnectTimer = null;
    connectChatSocket();
  }, delay);
}

type ChatReadReceipt = {
  scope?: string;
  route_id?: string;
  room_id?: number;
  salary_id?: number;
  user_id?: number;
  last_read_message_id?: number;
};

function markOwnMessagesRead<T extends { id: number; user_id: number; read?: boolean }>(
  items: T[],
  myId: number,
  lastReadId: number
): T[] {
  let changed = false;
  const next = items.map((item) => {
    if (item.user_id !== myId || item.id > lastReadId || item.read) {
      return item;
    }
    changed = true;
    return { ...item, read: true };
  });
  return changed ? next : items;
}

function applyIncomingReadReceipt(item: ChatReadReceipt): void {
  const myId = authUser.value?.id;
  const lastReadId = Number(item.last_read_message_id || 0);
  if (!myId || !lastReadId || item.user_id === myId) {
    return;
  }
  if (item.route_id && chatRouteId.value === item.route_id) {
    chatMessages.value = markOwnMessagesRead(chatMessages.value, myId, lastReadId);
  }
  if (item.room_id && chatRoomId.value === item.room_id) {
    chatRoomMessages.value = markOwnMessagesRead(chatRoomMessages.value, myId, lastReadId);
  }
  if (item.salary_id && salaryChatSalaryId.value === item.salary_id) {
    salaryChatMessages.value = markOwnMessagesRead(salaryChatMessages.value, myId, lastReadId);
  }
}

function connectChatSocket(): void {
  if (!authToken.value || !realtimeSocketsAllowed || isPageHidden()) {
    return;
  }
  if (notificationsWs?.readyState === WebSocket.CONNECTING) {
    return;
  }
  if (wsBusy(chatWs)) {
    return;
  }
  closeChatSocket();
  try {
    const ws = new WebSocket(chatWebSocketUrl(authToken.value));
    chatWs = ws;
    setChatWsState("connecting");
    armWsHandshakeTimer(ws, "chat");
    ws.onopen = () => {
      clearChatHandshakeTimer();
      chatWsBackoffMs = isCoarseUi() ? 4000 : 2500;
      setChatWsState("open");
      if (chatPingInterval !== null) {
        window.clearInterval(chatPingInterval);
      }
      chatPingInterval = window.setInterval(() => {
        try {
          ws.send("ping");
        } catch {
          // noop
        }
      }, 20000);
    };
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as { type?: string; item?: unknown };
        if (payload.type === "chat_message_created" && payload.item) {
          const item = payload.item as {
            id: number;
            route_id: string;
            user_id: number;
            author_name: string;
            text: string;
            created_at: string;
            read?: boolean;
          };
          if (chatRouteId.value && item.route_id === chatRouteId.value) {
            const exists = chatMessages.value.some((m) => m.id === item.id);
            if (!exists) {
              chatMessages.value = [...chatMessages.value, { ...item, read: Boolean(item.read) }];
            }
          } else if (authUser.value?.id && item.user_id !== authUser.value.id) {
            const current = chatUnreadByRoute.value[item.route_id] ?? 0;
            chatUnreadByRoute.value = { ...chatUnreadByRoute.value, [item.route_id]: current + 1 };
          }
        }
        if (payload.type === "chat_room_message_created" && payload.item) {
          const item = payload.item as {
            id: number;
            room_id: number;
            user_id: number;
            author_name: string;
            text: string;
            created_at: string;
            read?: boolean;
          };
          if (currentSection.value === "chat_room" && chatRoomId.value && item.room_id === chatRoomId.value) {
            const exists = chatRoomMessages.value.some((m) => m.id === item.id);
            if (!exists) {
              chatRoomMessages.value = [...chatRoomMessages.value, { ...item, read: Boolean(item.read) }];
            }
          } else if (authUser.value?.id && item.user_id !== authUser.value.id) {
            const rid = item.room_id;
            const cur = roomUnreadBump.value[rid] ?? 0;
            roomUnreadBump.value = { ...roomUnreadBump.value, [rid]: cur + 1 };
          }
        }
        if (payload.type === "salary_chat_message_created" && payload.item) {
          const item = payload.item as {
            id: number;
            salary_id: number;
            user_id: number;
            author_name: string;
            text: string;
            created_at: string;
            read?: boolean;
          };
          if (
            currentSection.value === "salary_chat" &&
            salaryChatSalaryId.value &&
            item.salary_id === salaryChatSalaryId.value
          ) {
            const exists = salaryChatMessages.value.some((m) => m.id === item.id);
            if (!exists) {
              salaryChatMessages.value = [...salaryChatMessages.value, { ...item, read: Boolean(item.read) }];
            }
          }
        }
        if (payload.type === "chat_messages_read" && payload.item) {
          applyIncomingReadReceipt(payload.item as ChatReadReceipt);
        }
      } catch {
        // ignore
      }
    };
    ws.onclose = () => {
      if (chatWs !== ws) {
        return;
      }
      clearChatHandshakeTimer();
      if (chatPingInterval !== null) {
        window.clearInterval(chatPingInterval);
        chatPingInterval = null;
      }
      chatWs = null;
      setChatWsState("closed");
      scheduleChatReconnect();
    };
    ws.onerror = () => {
      if (chatWs !== ws) {
        return;
      }
      clearChatHandshakeTimer();
      if (chatPingInterval !== null) {
        window.clearInterval(chatPingInterval);
        chatPingInterval = null;
      }
      chatWs = null;
      setChatWsState("closed");
      scheduleChatReconnect();
    };
  } catch {
    scheduleChatReconnect();
  }
}

watch(connectionServerOk, (ok) => {
  if (!ok || !authToken.value || !realtimeSocketsAllowed) {
    return;
  }
  if (!wsBusy(notificationsWs)) {
    connectNotificationsSocket();
  }
});

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
      if (useLegacyBrowserNotification.value) {
        showBrowserPushNotification(item);
      }
    }
    if (!item.is_read) {
      unreadNotificationsCount.value += 1;
    }
  }

  if (syncDriverState && item.event_type === "route_updated" && isDriver.value) {
    void refreshDriverData();
  }

  if (syncDriverState && item.event_type === "route_deleted" && isDriver.value) {
    // Only force-close the details view when we know which route was deleted
    // and it matches the currently opened route. Some backends may emit route_deleted
    // without route_id — in that case just refresh driver data without navigation.
    if (item.route_id && selectedDriverRoute.value?.id === item.route_id) {
      selectedDriverRoute.value = null;
      if (currentSection.value === "driver_route_details") {
        goBack();
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

function forceReconnectRealtimeSockets(): void {
  if (!authToken.value || !realtimeSocketsAllowed || !hasNetwork() || isPageHidden()) {
    return;
  }
  notificationsWsBackoffMs = isCoarseUi() ? 4000 : 2500;
  chatWsBackoffMs = isCoarseUi() ? 4000 : 2500;
  if (notificationsWsReconnectTimer !== null) {
    window.clearTimeout(notificationsWsReconnectTimer);
    notificationsWsReconnectTimer = null;
  }
  if (chatWsReconnectTimer !== null) {
    window.clearTimeout(chatWsReconnectTimer);
    chatWsReconnectTimer = null;
  }
  if (notificationsWs?.readyState !== WebSocket.OPEN) {
    if (notificationsWs) {
      try {
        notificationsWs.close();
      } catch {
        // replace stale handshake
      }
      notificationsWs = null;
    }
    setNotificationsWsState("closed");
    connectNotificationsSocket();
  } else if (chatWs?.readyState !== WebSocket.OPEN) {
    connectChatSocket();
  }
}

function scheduleNotificationsSocketReconnect(): void {
  if (!authToken.value || !realtimeSocketsAllowed) {
    return;
  }
  if (isPageHidden()) {
    return;
  }
  if (notificationsWsReconnectTimer !== null) {
    return;
  }
  const delay = notificationsWsBackoffMs;
  notificationsWsBackoffMs = Math.min(Math.round(delay * 1.8), isCoarseUi() ? 30_000 : 15_000);
  notificationsWsReconnectTimer = window.setTimeout(() => {
    notificationsWsReconnectTimer = null;
    connectNotificationsSocket();
  }, delay);
}

function connectNotificationsSocket(): void {
  if (!authToken.value || !realtimeSocketsAllowed || isPageHidden()) {
    return;
  }
  if (wsBusy(notificationsWs)) {
    return;
  }
  closeNotificationsSocket();
  try {
    const ws = new WebSocket(notificationsWebSocketUrl(authToken.value));
    notificationsWs = ws;
    setNotificationsWsState("connecting");
    armWsHandshakeTimer(ws, "notifications");
    ws.onopen = () => {
      clearNotificationsHandshakeTimer();
      notificationsWsBackoffMs = isCoarseUi() ? 4000 : 2500;
      setNotificationsWsState("open");
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
      if (!wsBusy(chatWs)) {
        connectChatSocket();
      }
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
      if (notificationsWs !== ws) {
        return;
      }
      clearNotificationsHandshakeTimer();
      if (notificationsPingInterval !== null) {
        window.clearInterval(notificationsPingInterval);
        notificationsPingInterval = null;
      }
      notificationsWs = null;
      setNotificationsWsState("closed");
      if (realtimeSocketsAllowed && !wsBusy(chatWs)) {
        connectChatSocket();
      }
      scheduleNotificationsSocketReconnect();
    };
    ws.onerror = () => {
      if (notificationsWs !== ws) {
        return;
      }
      clearNotificationsHandshakeTimer();
      if (notificationsPingInterval !== null) {
        window.clearInterval(notificationsPingInterval);
        notificationsPingInterval = null;
      }
      notificationsWs = null;
      setNotificationsWsState("closed");
      scheduleNotificationsSocketReconnect();
    };
  } catch {
    scheduleNotificationsSocketReconnect();
  }
}

function clearAuth(): void {
  authToken.value = "";
  denyRealtimeSockets();
  clearNotificationsSocketTimers();
  stopBackgroundSyncLoop();
  closeNotificationsSocket();
  stopNotificationsPolling();
  closeChatSocket();
  stopChatPolling();
  stopRoomChatPolling();
  stopSalaryChatPolling();
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
  chatRouteId.value = null;
  chatMessages.value = [];
  chatError.value = "";
  driverActiveRouteId.value = null;
  webPushSubscribed.value = false;
  pushLastOkAt.value = null;
  pushLastError.value = "";
  useLegacyBrowserNotification.value = true;
  roomUnreadBump.value = {};
  logisticDriverChatRooms.value = [];
  accountantDriverChatRooms.value = [];
  adminChatRoomsList.value = [];
  salaryListMine.value = [];
  salaryCurrentRecord.value = null;
  salaryChatSalaryId.value = null;
  salaryChatMessages.value = [];
  salaryAccountantDrivers.value = [];
  salaryAccountantItems.value = [];
  salarySelectedDriver.value = null;
  salaryError.value = "";
  logisticsContacts.value = [];
  logisticsContactsError.value = "";
  sectionStack.value = [];
  currentSection.value = "driver_home";
  profileMenuOpen.value = false;
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(USER_STORAGE_KEY);
  void clearAuthSession();
}

function resetToSection(section: AppSection): void {
  sectionStack.value = [];
  currentSection.value = section;
}

function pushSection(section: AppSection): void {
  if (currentSection.value === section) {
    return;
  }
  sectionStack.value.push(currentSection.value);
  if (sectionStack.value.length > 24) {
    sectionStack.value = sectionStack.value.slice(-24);
  }
  currentSection.value = section;
}

function goBack(): void {
  profileMenuOpen.value = false;
  const leaving = currentSection.value;
  if (leaving === "chat") {
    stopChatPolling();
  }
  if (leaving === "chat_room") {
    stopRoomChatPolling();
  }
  if (leaving === "salary_chat") {
    stopSalaryChatPolling();
  }
  const prev = sectionStack.value.pop();
  if (!prev) {
    if (authUser.value) {
      openDefaultSectionByRole(authUser.value);
    }
    return;
  }
  currentSection.value = prev;
}

function openDefaultSectionByRole(user: AuthUser): void {
  if (isAdminRole(user.role_code) || isRouteManagerRole(user.role_code)) {
    resetToSection("admin_routes");
    return;
  }
  resetToSection("driver_home");
}

async function applyOverlaysToRoute(baseRoute: RouteDto | null): Promise<RouteDto | null> {
  if (!baseRoute) {
    return null;
  }
  const overlays = await getPointOverlays(baseRoute.id);
  const pendingAccepts = await getPendingAccepts();
  const locallyAccepted = pendingAccepts.some((item) => item.route_id === baseRoute.id);
  const byPointId = new Map(overlays.map((item) => [item.point_id, item]));
  const points = overlays.length
    ? baseRoute.points.map((point) => {
        const overlay = byPointId.get(point.id);
        if (!overlay) {
          return point;
        }
        return {
          ...point,
          status: overlay.status
        };
      })
    : baseRoute.points;
  return {
    ...baseRoute,
    status: locallyAccepted && baseRoute.status === "new" ? "process" : baseRoute.status,
    points
  } as RouteDto;
}

function applyPendingAcceptToLists(
  assigned: DriverRouteListItem[],
  pendingIds: Set<string>
): DriverRouteListItem[] {
  if (!pendingIds.size) {
    return assigned;
  }
  return assigned.map((item) =>
    pendingIds.has(item.id) && item.status === "new" ? { ...item, status: "process" } : item
  );
}

async function persistDriverRoute(next: RouteDto | null): Promise<void> {
  if (!next) {
    await saveActiveRoute(null);
    return;
  }
  await saveActiveRoute(next);
  await saveRouteSnapshot(next);
}

function hasNetwork(): boolean {
  return typeof navigator === "undefined" ? true : navigator.onLine;
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i += 1) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

async function ensureWebPushSubscription(): Promise<void> {
  if (!authToken.value || typeof window === "undefined") {
    return;
  }
  if (!("Notification" in window) || Notification.permission !== "granted") {
    return;
  }
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
    return;
  }
  try {
    const registration = await navigator.serviceWorker.ready;
    const existing = await registration.pushManager.getSubscription();
    if (existing) {
      const json = existing.toJSON();
      const key = json.keys;
      if (json.endpoint && key?.p256dh && key?.auth) {
        try {
          await subscribeWebPush(authToken.value, {
            endpoint: json.endpoint,
            keys: { p256dh: key.p256dh, auth: key.auth }
          });
        } catch {
          // keep local subscription; server sync retries on next resume
        }
      }
      webPushSubscribed.value = true;
      useLegacyBrowserNotification.value = false;
      return;
    }
  } catch {
    // fall through to subscribe
  }
  await trySubscribeWebPush();
}

async function trySubscribeWebPush(): Promise<void> {
  if (!authToken.value || typeof window === "undefined") {
    return;
  }
  pushInProgress.value = true;
  pushLastError.value = "";
  try {
    if ("Notification" in window && Notification.permission === "default") {
      const perm = await Notification.requestPermission();
      if (perm !== "granted") {
        useLegacyBrowserNotification.value = true;
        pushLastError.value = "не получено разрешение на уведомления";
        return;
      }
    }
    const { public_key: publicKey } = await getVapidPublicKey(authToken.value);
    if (!publicKey || !("serviceWorker" in navigator) || !("PushManager" in window)) {
      useLegacyBrowserNotification.value = true;
      pushLastError.value = !publicKey ? "на сервере не настроен VAPID_PUBLIC_KEY" : "PushManager/serviceWorker недоступны";
      return;
    }
    useLegacyBrowserNotification.value = false;
    const registration = await navigator.serviceWorker.ready;

    // If VAPID keys were rotated, browsers can keep an old subscription.
    // Resubscribing with a different applicationServerKey may throw InvalidStateError.
    try {
      const existing = await registration.pushManager.getSubscription();
      if (existing) {
        await existing.unsubscribe();
      }
    } catch {
      // ignore unsubscribe errors
    }

    const sub = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey)
    });
    const json = sub.toJSON();
    const key = json.keys;
    if (!json.endpoint || !key?.p256dh || !key?.auth) {
      useLegacyBrowserNotification.value = true;
      return;
    }
    await subscribeWebPush(authToken.value, {
      endpoint: json.endpoint,
      keys: { p256dh: key.p256dh, auth: key.auth }
    });
    pushLastOkAt.value = new Date().toLocaleString();
    webPushSubscribed.value = true;
  } catch (error) {
    useLegacyBrowserNotification.value = true;
    const err = error as { name?: string; message?: string };
    const name = (err?.name || "Error").trim();
    const msg = (err?.message || "").trim();
    pushLastError.value = msg ? `${name}: ${msg}` : name;
  } finally {
    pushInProgress.value = false;
    void refreshWebPushSubscriptionState();
  }
}

async function tryUnsubscribeWebPush(): Promise<void> {
  if (!authToken.value || typeof window === "undefined") {
    return;
  }
  pushInProgress.value = true;
  pushLastError.value = "";
  try {
    if ("serviceWorker" in navigator && "PushManager" in window) {
      const registration = await navigator.serviceWorker.ready;
      const existing = await registration.pushManager.getSubscription();
      if (existing) {
        await existing.unsubscribe();
      }
    }
    await clearWebPushSubscriptions(authToken.value);
    useLegacyBrowserNotification.value = true;
    webPushSubscribed.value = false;
    pushLastOkAt.value = null;
  } catch (error) {
    const err = error as { name?: string; message?: string };
    const name = (err?.name || "Error").trim();
    const msg = (err?.message || "").trim();
    pushLastError.value = msg ? `${name}: ${msg}` : name;
  } finally {
    pushInProgress.value = false;
    void refreshWebPushSubscriptionState();
  }
}

async function refreshDriverRoutes(): Promise<void> {
  if (!authToken.value || !isDriver.value) {
    return;
  }
  const cache = await loadDriverRoutesCache();
  const pending = await getPendingAccepts();
  const pendingIds = new Set(pending.map((item) => item.route_id));
  if (cache) {
    driverAssignedRoutes.value = applyPendingAcceptToLists(cache.assigned, pendingIds);
    driverHistoryRoutes.value = cache.history;
    driverActiveRouteId.value = pending[0]?.route_id ?? cache.active_route_id;
  }

  if (!hasNetwork()) {
    const local = await loadActiveRoute();
    if (local) {
      route.value = await applyOverlaysToRoute(local);
    }
    return;
  }

  driverRoutesLoading.value = true;
  try {
    let assignedItems: DriverRouteListItem[] = [];
    try {
      const prefetch = await prefetchDriverAssignedRoutes(authToken.value);
      await persistPrefetchPayload(prefetch);
      if (prefetch.logistics_contacts?.length) {
        logisticsContacts.value = prefetch.logistics_contacts;
      }
      assignedItems = applyPendingAcceptToLists(prefetch.items.map(routeToListItem), pendingIds);
      driverAssignedRoutes.value = assignedItems;
      driverActiveRouteId.value = pending[0]?.route_id ?? prefetch.active_route_id ?? null;
    } catch {
      const assigned = await listDriverRoutes(authToken.value, "assigned");
      assignedItems = applyPendingAcceptToLists(assigned.items, pendingIds);
      driverAssignedRoutes.value = assignedItems;
      driverActiveRouteId.value = pending[0]?.route_id ?? assigned.active_route_id ?? null;
      for (const item of assignedItems) {
        try {
          const full = await applyOverlaysToRoute(await getDriverRoute(authToken.value, item.id));
          if (full) {
            await saveRouteSnapshot(full);
          }
        } catch {
          // keep previously cached snapshot
        }
      }
    }

    const history = await listDriverRoutes(authToken.value, "history");
    driverHistoryRoutes.value = history.items;
    await saveDriverRoutesCache({
      assigned: assignedItems,
      history: history.items,
      active_route_id: driverActiveRouteId.value
    });

    try {
      const routeIds = [...assignedItems.map((x) => x.id), ...history.items.map((x) => x.id)];
      const unread = await getChatUnreadSummary(authToken.value, routeIds);
      const map = { ...chatUnreadByRoute.value };
      unread.forEach((row) => {
        map[row.route_id] = row.unread_count;
      });
      chatUnreadByRoute.value = map;
    } catch {
      // ignore chat unread errors
    }

    const localWork = pendingIds.size > 0 || (await getOutboxEvents(getDeviceId())).length > 0;
    if (driverActiveRouteId.value) {
      if (!route.value || route.value.id !== driverActiveRouteId.value) {
        const cachedSnap = await loadRouteSnapshot(driverActiveRouteId.value);
        const activeRoute = cachedSnap ?? (await getDriverRoute(authToken.value, driverActiveRouteId.value));
        route.value = await applyOverlaysToRoute(activeRoute);
        await persistDriverRoute(route.value);
      } else {
        route.value = await applyOverlaysToRoute(route.value);
        await persistDriverRoute(route.value);
      }
    } else if (!localWork) {
      route.value = null;
      await persistDriverRoute(null);
    }
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы загрузить рейсы." })) {
      return;
    }
    const local = await loadActiveRoute();
    if (local) {
      route.value = await applyOverlaysToRoute(local);
    }
    if (!cache) {
      syncMessage.value = isOfflineLikeError(error)
        ? "Офлайн: нет сохранённых рейсов. Откройте список, когда появится сеть."
        : `Ошибка загрузки рейсов: ${(error as Error).message}`;
    }
  } finally {
    driverRoutesLoading.value = false;
  }
}

async function refreshRoute(): Promise<void> {
  if (!authToken.value || !isDriver.value) {
    return;
  }
  if (!hasNetwork()) {
    const local = await loadActiveRoute();
    if (local) {
      route.value = await applyOverlaysToRoute(local);
    }
    return;
  }
  try {
    const serverRoute = await getActiveRoute(authToken.value);
    const pending = await getPendingAccepts();
    const localWork = pending.length > 0 || (await getOutboxEvents(getDeviceId())).length > 0;
    if (!serverRoute && localWork && route.value) {
      route.value = await applyOverlaysToRoute(route.value);
      return;
    }
    const merged = await applyOverlaysToRoute(serverRoute);
    if (merged) {
      route.value = merged;
      await persistDriverRoute(merged);
    } else if (!localWork) {
      route.value = null;
      await persistDriverRoute(null);
    }
  } catch (error) {
    if (handleAuthError(error)) {
      return;
    }
    const local = await loadActiveRoute();
    if (local) {
      route.value = await applyOverlaysToRoute(local);
    }
  }
}

async function hydrateDriverRoutesFromCache(): Promise<void> {
  if (!isDriver.value) {
    return;
  }
  const cache = await loadDriverRoutesCache();
  const pending = await getPendingAccepts();
  const pendingIds = new Set(pending.map((item) => item.route_id));
  if (cache) {
    driverAssignedRoutes.value = applyPendingAcceptToLists(cache.assigned, pendingIds);
    driverHistoryRoutes.value = cache.history;
    driverActiveRouteId.value = pending[0]?.route_id ?? cache.active_route_id;
  }
  const local = await loadActiveRoute();
  if (local) {
    route.value = await applyOverlaysToRoute(local);
  }
  if (selectedDriverRoute.value) {
    const snap = await loadRouteSnapshot(selectedDriverRoute.value.id);
    if (snap) {
      selectedDriverRoute.value = await applyOverlaysToRoute(snap);
    }
  }
}

function onServiceWorkerMessage(event: MessageEvent): void {
  if (event.data?.type !== "DMK_ROUTES_PREFETCHED") {
    return;
  }
  void hydrateDriverRoutesFromCache();
}

function onForegroundResume(): void {
  if (!authToken.value) {
    return;
  }
  noteForegroundResume();
  if (realtimeSocketsAllowed) {
    forceReconnectRealtimeSockets();
  }
  startNotificationsPolling();
  void refreshNotifications();
  void flushPendingNotificationReads();
  void refreshRouteChatUnread();
  void ensureWebPushSubscription();
  if (isDriver.value) {
    void hydrateDriverRoutesFromCache();
    void refreshDriverData();
  } else if (isRouteManager.value) {
    void refreshAdminRoutes(routeFilters.value);
  }
}

function onVisibilityChange(): void {
  if (typeof document === "undefined") {
    return;
  }
  if (!authToken.value) {
    return;
  }
  if (document.visibilityState === "hidden") {
    if (isDriver.value) {
      void prefetchAssignedRoutesFromSession();
      void registerDriverBackgroundSync();
    }
    return;
  }
  if (document.visibilityState !== "visible") {
    return;
  }
  onForegroundResume();
}

function onPageShow(event: PageTransitionEvent): void {
  if (event.persisted) {
    onForegroundResume();
  }
}

function onPageHide(): void {
  if (!authToken.value || !isDriver.value) {
    return;
  }
  void prefetchAssignedRoutesFromSession();
  void registerDriverBackgroundSync();
}

function onOnline(): void {
  syncMessage.value = "Онлайн: синхронизация возобновлена";
  if (authToken.value) {
    onForegroundResume();
  }
  if (isDriver.value) {
    void (async () => {
      await prefetchAssignedRoutesFromSession();
      await syncOutboxInBackground();
      await refreshDriverRoutes();
    })();
  } else if (isRouteManager.value) {
    void refreshAdminRoutes(routeFilters.value);
  }
}

function onOffline(): void {
  syncMessage.value = "Офлайн: изменения сохраняются локально";
  closeNotificationsSocket();
  stopNotificationsPolling();
}

async function flushPendingAccepts(): Promise<void> {
  if (!authToken.value) {
    return;
  }
  const pending = await getPendingAccepts();
  for (const item of pending) {
    try {
      const serverRoute = await acceptRoute(authToken.value, item.route_id);
      await removePendingAccept(item.route_id);
      const merged = await applyOverlaysToRoute(serverRoute);
      if (merged && (!route.value || route.value.id === merged.id)) {
        route.value = merged;
        await persistDriverRoute(merged);
      }
      if (selectedDriverRoute.value?.id === item.route_id && merged) {
        selectedDriverRoute.value = merged;
      }
    } catch (error) {
      if (handleAuthError(error)) {
        return;
      }
      const message = ((error as Error)?.message || "").toLowerCase();
      if (message.includes("already") || message.includes("process")) {
        await removePendingAccept(item.route_id);
        continue;
      }
      if (!isOfflineLikeError(error)) {
        console.debug("[pwa-sync] pending accept failed", error);
      }
      break;
    }
  }
}

async function syncOutboxInBackground(): Promise<void> {
  if (!authToken.value || !isDriver.value) {
    return;
  }
  if (!hasNetwork() || syncing.value) {
    return;
  }
  const deviceId = getDeviceId();
  const gen = ++syncGeneration;
  syncing.value = true;
  setConnectionSyncing(true);
  if (syncWatchdogTimer !== null) {
    window.clearTimeout(syncWatchdogTimer);
  }
  syncWatchdogTimer = window.setTimeout(() => {
    if (gen !== syncGeneration) {
      return;
    }
    syncing.value = false;
    setConnectionSyncing(false);
    reportDebugError({
      source: "sync-watchdog",
      message: "Синхронизация зависла дольше 75с и была сброшена. Данные остаются на телефоне.",
      extra: { device_id: deviceId }
    });
  }, 75_000);
  try {
    await flushPendingAccepts();
    let outbox = (await getOutboxEvents(deviceId)).sort((a, b) => a.created_at.localeCompare(b.created_at));
    await refreshConnectionQueue();
    if (!outbox.length) {
      return;
    }

    for (const ev of outbox) {
      if (ev.to_status !== "docs") {
        continue;
      }
      const keys = ev.document_local_keys;
      if (!keys?.length || ev.document_file_ids?.length) {
        continue;
      }
      const blobs: Blob[] = [];
      let missing = false;
      for (const key of keys) {
        const row = await getPendingDocBlob(key);
        if (!row) {
          missing = true;
          break;
        }
        blobs.push(row.blob);
      }
      if (missing || blobs.length !== keys.length) {
        continue;
      }
      try {
        const prepared = await prepareDocumentImageBlobs(blobs);
        const { file_ids } = await uploadPointDocuments(authToken.value, ev.point_id, prepared, { timeoutMs: 45_000 });
        await updateOutboxEventByClientId(ev.client_event_id, {
          document_file_ids: file_ids,
          document_local_keys: []
        });
        await removePendingDocBlobs(keys);
      } catch (error) {
        reportDebugError({
          source: "sync.docs",
          error,
          extra: { point_id: ev.point_id, client_event_id: ev.client_event_id, files: blobs.length }
        });
        break;
      }
    }

    outbox = (await getOutboxEvents(deviceId)).sort((a, b) => a.created_at.localeCompare(b.created_at));
    const events: EventPayload[] = outbox
      .filter((event) => !(event.to_status === "docs" && event.document_local_keys?.length && !event.document_file_ids?.length))
      .map((event) => {
        const payload: EventPayload = {
          client_event_id: event.client_event_id,
          occurred_at_client: event.occurred_at_client,
          point_id: event.point_id,
          to_status: event.to_status,
          time_source: event.time_source ?? null,
          odometer: event.odometer ?? null,
          odometer_source: event.odometer_source ?? null,
          coordinates: null
        };
        if (event.document_file_ids?.length) {
          payload.document_file_ids = event.document_file_ids;
        }
        return payload;
      });
    if (!events.length) {
      return;
    }
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
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы продолжить синхронизацию." })) {
      return;
    }
    reportDebugError({ source: "sync.outbox", error });
  } finally {
    if (syncWatchdogTimer !== null) {
      window.clearTimeout(syncWatchdogTimer);
      syncWatchdogTimer = null;
    }
    if (gen === syncGeneration) {
      syncing.value = false;
      setConnectionSyncing(false);
    }
    await refreshConnectionQueue();
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
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы загрузить пользователей." })) {
      return;
    }
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
    routeLogistics.value = await listRouteLogistics(authToken.value);
  } catch (error) {
    routesError.value = `Ошибка загрузки водителей: ${(error as Error).message}`;
  }
}

async function refreshAdminRoutes(filters?: RouteFilters): Promise<void> {
  if (!authToken.value || !isRouteManager.value) {
    return;
  }
  if (refreshAdminRoutesInFlight) {
    return refreshAdminRoutesInFlight;
  }
  refreshAdminRoutesInFlight = (async () => {
    routesLoading.value = true;
    routesError.value = "";
    try {
      const effectiveFilters = filters ?? routeFilters.value;
      routeFilters.value = effectiveFilters;
      adminRoutes.value = await listAdminRoutes(authToken.value, effectiveFilters);

      try {
        const routeIds = adminRoutes.value.map((x) => x.id);
        const unread = await getChatUnreadSummary(authToken.value, routeIds);
        const map = { ...chatUnreadByRoute.value };
        unread.forEach((row) => {
          map[row.route_id] = row.unread_count;
        });
        chatUnreadByRoute.value = map;
      } catch {
        // ignore chat unread errors
      }

      if (selectedAdminRoute.value) {
        const selected = adminRoutes.value.find((item) => item.id === selectedAdminRoute.value?.id);
        if (selected) {
          selectedAdminRoute.value = await getAdminRoute(authToken.value, selected.id);
        } else if (currentSection.value === "admin_route_details") {
          selectedAdminRoute.value = null;
          goBack();
        }
      }
    } catch (error) {
      if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы загрузить рейсы." })) {
        return;
      }
      routesError.value = `Ошибка загрузки рейсов: ${(error as Error).message}`;
    } finally {
      routesLoading.value = false;
    }
  })().finally(() => {
    refreshAdminRoutesInFlight = null;
  });
  return refreshAdminRoutesInFlight;
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
    pushSection("admin_route_details");
  } catch (error) {
    routesError.value = `Ошибка создания рейса: ${(error as Error).message}`;
  } finally {
    routesLoading.value = false;
  }
}

async function doCreateAdminRouteFromOnec(payload: {
  raw_text: string;
  driver_user_id?: number | null;
  number_auto?: string;
  trailer_number?: string;
}): Promise<void> {
  if (!authToken.value || !isRouteManager.value) {
    return;
  }
  routesLoading.value = true;
  routesError.value = "";
  try {
    const routeCreated = await createAdminRouteFromOnec(authToken.value, payload);
    await refreshAdminRoutes(routeFilters.value);
    selectedAdminRoute.value = await getAdminRoute(authToken.value, routeCreated.id);
    pushSection("admin_route_details");
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
    created_by_user_id?: number;
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

async function doUpdateAdminRoutePoint(pointId: number, payload: Record<string, unknown>): Promise<void> {
  if (!authToken.value || !isRouteManager.value || !selectedAdminRoute.value) {
    return;
  }
  const routeId = selectedAdminRoute.value.id;
  const scrollY = appScrollEl.value?.scrollTop ?? 0;
  routesError.value = "";
  try {
    await updateAdminRoutePoint(
      authToken.value,
      pointId,
      payload as Parameters<typeof updateAdminRoutePoint>[2]
    );
    selectedAdminRoute.value = await getAdminRoute(authToken.value, routeId);
    await refreshAdminRoutes(routeFilters.value);
    requestAnimationFrame(() => {
      if (appScrollEl.value) {
        appScrollEl.value.scrollTop = scrollY;
      }
    });
  } catch (error) {
    routesError.value = `Ошибка редактирования точки: ${(error as Error).message}`;
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
    pushSection("admin_route_details");
  } catch (error) {
    routesError.value = `Ошибка загрузки рейса: ${(error as Error).message}`;
  } finally {
    routesLoading.value = false;
  }
}

function openAdminRouteList(): void {
  goBack();
}

async function doAssignAdminRoute(
  routeId: string,
  driverUserId: number,
  extras?: { number_auto?: string; trailer_number?: string }
): Promise<void> {
  if (!authToken.value || !isRouteManager.value) {
    return;
  }
  routesLoading.value = true;
  routesError.value = "";
  try {
    await assignAdminRouteDriver(authToken.value, routeId, driverUserId, extras);
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
    resetToSection("admin_routes");
    await refreshAdminRoutes(routeFilters.value);
    await refreshNotifications();
  } catch (error) {
    routesError.value = `Ошибка удаления рейса: ${(error as Error).message}`;
  } finally {
    routesLoading.value = false;
  }
}

function loadPendingNotificationReads(): number[] {
  try {
    const raw = localStorage.getItem(PENDING_NOTIFICATION_READS_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item): item is number => typeof item === "number" && Number.isFinite(item));
  } catch {
    return [];
  }
}

function savePendingNotificationReads(ids: number[]): void {
  const unique = Array.from(new Set(ids));
  if (!unique.length) {
    localStorage.removeItem(PENDING_NOTIFICATION_READS_KEY);
    return;
  }
  localStorage.setItem(PENDING_NOTIFICATION_READS_KEY, JSON.stringify(unique));
}

function queuePendingNotificationRead(notificationId: number): void {
  savePendingNotificationReads([...loadPendingNotificationReads(), notificationId]);
}

function applyLocalNotificationRead(notificationId: number): void {
  let changed = false;
  notifications.value = notifications.value.map((item) => {
    if (item.id !== notificationId || item.is_read) {
      return item;
    }
    changed = true;
    return { ...item, is_read: true };
  });
  if (changed) {
    unreadNotificationsCount.value = Math.max(0, unreadNotificationsCount.value - 1);
  }
}

async function flushPendingNotificationReads(): Promise<void> {
  if (!authToken.value || !hasNetwork() || isPageHidden()) {
    return;
  }
  const pending = loadPendingNotificationReads();
  if (!pending.length) {
    return;
  }
  const leftover: number[] = [];
  for (const notificationId of pending) {
    try {
      const updated = await markNotificationRead(authToken.value, notificationId);
      notifications.value = notifications.value.map((item) => (item.id === updated.id ? updated : item));
    } catch (error) {
      if (handleAuthError(error)) {
        leftover.push(notificationId, ...pending.slice(pending.indexOf(notificationId) + 1));
        break;
      }
      if (isOfflineLikeError(error) || isPageHidden()) {
        leftover.push(notificationId, ...pending.slice(pending.indexOf(notificationId) + 1));
        break;
      }
      leftover.push(notificationId);
    }
  }
  savePendingNotificationReads(leftover);
}

async function refreshNotifications(): Promise<void> {
  if (!authToken.value || notificationsLoading.value) {
    return;
  }
  if (!hasNetwork() || isPageHidden()) {
    return;
  }
  notificationsLoading.value = true;
  notificationsError.value = "";
  try {
    const latestNotifications = await listNotifications(authToken.value, 50);
    latestNotifications.forEach((item) => handleIncomingNotification(item, { playEffects: false, syncDriverState: true }));
    notifications.value = latestNotifications;
    try {
      unreadNotificationsCount.value = await getUnreadNotificationsCount(authToken.value);
    } catch (error) {
      if (!isOfflineLikeError(error) && !isPageHidden()) {
        throw error;
      }
    }
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы загрузить уведомления." })) {
      return;
    }
    if (isOfflineLikeError(error) || isPageHidden()) {
      return;
    }
    notificationsError.value = `Ошибка загрузки уведомлений: ${(error as Error).message}`;
  } finally {
    notificationsLoading.value = false;
  }
}

async function doMarkNotificationRead(notificationId: number): Promise<void> {
  if (!authToken.value) {
    return;
  }
  if (markReadInFlight.has(notificationId)) {
    return;
  }
  markReadInFlight.add(notificationId);
  applyLocalNotificationRead(notificationId);
  if (!hasNetwork() || isPageHidden()) {
    queuePendingNotificationRead(notificationId);
    markReadInFlight.delete(notificationId);
    return;
  }
  try {
    const updated = await markNotificationRead(authToken.value, notificationId);
    notifications.value = notifications.value.map((item) => (item.id === updated.id ? updated : item));
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново." })) {
      return;
    }
    if (isOfflineLikeError(error) || isPageHidden()) {
      queuePendingNotificationRead(notificationId);
      return;
    }
    notificationsError.value = `Ошибка отметки прочитанного: ${(error as Error).message}`;
  } finally {
    markReadInFlight.delete(notificationId);
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

function notificationPayloadRecord(item: NotificationDto): Record<string, unknown> | null {
  const p = item.payload;
  if (!p || typeof p !== "object" || Array.isArray(p)) {
    return null;
  }
  return p as Record<string, unknown>;
}

function notificationPayloadNumber(p: Record<string, unknown> | null, key: string): number | null {
  if (!p) return null;
  const v = p[key];
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function salaryBackSectionForNotification(): AppSection {
  if (isDriver.value) return "driver_salary";
  return "salary_accounting";
}

async function openRouteDetailsForRole(routeId: string): Promise<void> {
  if (!authToken.value) {
    return;
  }
  if (isDriver.value) {
    try {
      selectedDriverRoute.value = await getDriverRoute(authToken.value, routeId);
      pushSection("driver_route_details");
    } catch (error) {
      syncMessage.value = `Ошибка открытия рейса: ${(error as Error).message}`;
    }
    return;
  }
  if (isRouteManager.value) {
    try {
      selectedAdminRoute.value = await getAdminRoute(authToken.value, routeId);
      pushSection("admin_route_details");
    } catch (error) {
      routesError.value = `Ошибка открытия рейса: ${(error as Error).message}`;
    }
  }
}

async function openNotificationFromItem(item: NotificationDto): Promise<void> {
  if (!authToken.value || !authUser.value) {
    return;
  }
  const p = notificationPayloadRecord(item);
  const salaryId = p ? notificationPayloadNumber(p, "salary_id") : null;
  const roomId = p ? notificationPayloadNumber(p, "room_id") : null;
  const navigable =
    Boolean(item.route_id) || salaryId != null || roomId != null;
  if (!navigable) {
    return;
  }

  await doMarkNotificationRead(item.id);
  profileMenuOpen.value = false;
  notificationsError.value = "";

  const routeIdFromPayload =
    p && typeof p["route_id"] === "string" && (p["route_id"] as string).trim() ? (p["route_id"] as string) : null;

  if (item.event_type === "chat_message" && salaryId != null) {
    try {
      salaryCurrentRecord.value = await getSalary(authToken.value, salaryId);
      salaryDetailBackSection.value = salaryBackSectionForNotification();
      salaryChatSalaryId.value = salaryId;
      pushSection("salary_chat");
      await refreshSalaryChat();
      startSalaryChatPolling();
    } catch (error) {
      notificationsError.value = (error as Error).message;
    }
    return;
  }

  if (item.event_type === "chat_message" && roomId != null) {
    const titleHint = (item.title || "").replace(/^Чат:\s*/i, "").trim() || item.title || undefined;
    await openChatRoom(roomId, titleHint);
    return;
  }

  if (item.event_type === "chat_message") {
    const rid = routeIdFromPayload || item.route_id;
    if (rid) {
      await openChatForRoute(rid);
      return;
    }
  }

  if (salaryId != null) {
    try {
      const row = await getSalary(authToken.value, salaryId);
      openSalaryDetail(row, salaryBackSectionForNotification());
    } catch (error) {
      notificationsError.value = (error as Error).message;
    }
    return;
  }

  if (item.route_id) {
    await openRouteDetailsForRole(item.route_id);
  }
}

async function openActiveRouteFromHome(): Promise<void> {
  if (!route.value || !isDriver.value || !authToken.value) {
    return;
  }
  const routeId = route.value.id;
  selectedDriverRoute.value = await applyOverlaysToRoute(route.value);
  pushSection("driver_route_details");
  void refreshLogisticsContacts();
  if (!hasNetwork()) {
    return;
  }
  try {
    await refreshDriverData();
    const latest = route.value?.id === routeId ? route.value : await loadRouteSnapshot(routeId);
    if (latest) {
      selectedDriverRoute.value = await applyOverlaysToRoute(latest);
    }
    if (hasNetwork()) {
      try {
        const server = await applyOverlaysToRoute(await getDriverRoute(authToken.value, routeId));
        if (server) {
          selectedDriverRoute.value = server;
          await saveRouteSnapshot(server);
        }
      } catch {
        // keep local snapshot
      }
    }
  } catch (error) {
    if (!selectedDriverRoute.value) {
      syncMessage.value = `Ошибка загрузки деталей рейса: ${(error as Error).message}`;
    }
  }
}

async function refreshRouteChatUnread(): Promise<void> {
  if (!authToken.value) {
    return;
  }
  try {
    const unread = await getMyChatUnreadSummary(authToken.value);
    const map: Record<string, number> = {};
    unread.forEach((row) => {
      map[row.route_id] = row.unread_count;
    });
    chatUnreadByRoute.value = map;
  } catch {
    // ignore chat unread errors
  }
}

async function bootstrapByRole(user: AuthUser): Promise<void> {
  void refreshWebPushSubscriptionState();
  closeNotificationsSocket();
  closeChatSocket();
  allowRealtimeSockets();
  connectNotificationsSocket();
  startNotificationsPolling();
  try {
    if (isAdminRole(user.role_code)) {
      resetToSection("admin_routes");
      await refreshAdminUsers();
      await refreshRouteDrivers();
      await refreshAdminRoutes({ status: "process" });
    } else if (isRouteManagerRole(user.role_code)) {
      resetToSection("admin_routes");
      await refreshRouteDrivers();
      await refreshAdminRoutes({ status: "process" });
    } else {
      resetToSection("driver_home");
      await refreshDriverRoutes();
      await refreshRoute();
      await refreshRouteChatUnread();
      await syncOutboxInBackground();
      startBackgroundSyncLoop();
      if (typeof Notification !== "undefined" && Notification.permission === "granted") {
        void ensureWebPushSubscription();
      }
    }
    await refreshNotifications();
    await refreshLogisticsContacts();
  } finally {
    if (!realtimeSocketsAllowed) {
      allowRealtimeSockets();
    }
    if (!wsBusy(notificationsWs)) {
      connectNotificationsSocket();
    }
    startNotificationsPolling();
  }
}

function openRoleMainSection(section: AppSection): void {
  if (!authUser.value) {
    resetToSection("driver_home");
    return;
  }
  profileMenuOpen.value = false;
  if (section === "notifications") {
    resetToSection("notifications");
    return;
  }
  if (section === "chats") {
    resetToSection("chats");
    void refreshChatsHub();
    return;
  }
  if (section === "driver_salary" && authUser.value.role_code === "driver") {
    void openDriverSalarySection();
    return;
  }
  if (section === "salary_accounting" && (isAdmin.value || isAccountant.value)) {
    resetToSection("salary_accounting");
    salaryAccountantDrivers.value = [];
    salaryAccountantItems.value = [];
    salarySelectedDriver.value = null;
    salaryError.value = "";
    return;
  }
  if (section === "admin_users" && isAdminRole(authUser.value.role_code)) {
    resetToSection(section);
    return;
  }
  if (section === "admin_logistics_contacts" && isAdminRole(authUser.value.role_code)) {
    resetToSection(section);
    void refreshLogisticsContacts();
    return;
  }
  if ((section === "admin_routes" || section === "admin_route_details") && isRouteManagerRole(authUser.value.role_code)) {
    resetToSection(section === "admin_route_details" && !selectedAdminRoute.value ? "admin_routes" : section);
    return;
  }
  if ((section === "driver_home" || section === "driver_routes") && authUser.value.role_code === "driver") {
    resetToSection(section);
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

function selectBottomNav(item: BottomNavItem): void {
  openRoleMainSection(item.section as AppSection);
}

async function doLogin(loginValue: string, password: string): Promise<void> {
  authError.value = "";
  authLoading.value = true;
  try {
    const result = await loginRequest(loginValue, password);
    authToken.value = result.access_token;
    authUser.value = result.user;
    await persistAuth(result.access_token, result.user);
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
  const current =
    (selectedDriverRoute.value?.id === id ? selectedDriverRoute.value : null) ||
    (route.value?.id === id ? route.value : null) ||
    (await loadRouteSnapshot(id));
  if (!current) {
    syncMessage.value = "Нет сохранённых данных рейса. Откройте его, когда будет сеть.";
    return;
  }

  const locallyAccepted: RouteDto = {
    ...current,
    status: "process",
    accepted_at: current.accepted_at || new Date().toISOString()
  };
  route.value = locallyAccepted;
  driverActiveRouteId.value = id;
  if (selectedDriverRoute.value?.id === id) {
    selectedDriverRoute.value = locallyAccepted;
  }
  driverAssignedRoutes.value = applyPendingAcceptToLists(driverAssignedRoutes.value, new Set([id]));
  await persistDriverRoute(locallyAccepted);

  try {
    if (hasNetwork()) {
      const serverRoute = await acceptRoute(authToken.value, id);
      const merged = await applyOverlaysToRoute(serverRoute);
      if (merged) {
        route.value = merged;
        if (selectedDriverRoute.value?.id === id) {
          selectedDriverRoute.value = merged;
        }
        await persistDriverRoute(merged);
      }
      await removePendingAccept(id);
      await refreshDriverRoutes();
      await refreshNotifications();
      syncMessage.value = "Рейс принят";
      return;
    }
  } catch (error) {
    if (handleAuthError(error)) {
      return;
    }
    if (!isOfflineLikeError(error)) {
      const message = (error as Error).message || "";
      if (!/already|process/i.test(message)) {
        syncMessage.value = `Рейс сохранён локально. Синхронизация: ${message}`;
      }
    }
  }
  await addPendingAccept(id);
  syncMessage.value = "Рейс принят локально и отправится при появлении сети";
  void syncOutboxInBackground();
}

function openStatusConfirm(pointId: number): void {
  if (!isDriver.value) {
    return;
  }
  const base =
    currentSection.value === "driver_route_details" && selectedDriverRoute.value
      ? selectedDriverRoute.value
      : route.value;
  if (!base) {
    return;
  }
  const current = base.points.find((point) => point.id === pointId);
  if (!current) {
    return;
  }
  if (!nextStatus(current.status)) {
    return;
  }
  const initial = toDatetimeLocalValue(new Date());
  statusConfirm.value = {
    pointId,
    nextLabel: nextStatusLabel(current.status) || "",
    datetimeLocal: initial,
    initialDatetimeLocal: initial,
    showOdometer: true,
    odometer: "",
    initialOdometer: "",
    odometerPrefillSource: null,
    telemetryLoading: true
  };
  if (hasNetwork() && authToken.value) {
    void (async () => {
      try {
        const tel = await getPointTelemetry(authToken.value, pointId, { timeoutMs: 8000 });
        if (!statusConfirm.value || statusConfirm.value.pointId !== pointId) return;
        if (tel.odometer) {
          statusConfirm.value.odometer = tel.odometer;
          statusConfirm.value.initialOdometer = tel.odometer;
          statusConfirm.value.odometerPrefillSource = tel.odometer_source;
        }
      } catch {
        // ignore telemetry prefetch errors; driver can enter manually
      } finally {
        if (statusConfirm.value && statusConfirm.value.pointId === pointId) {
          statusConfirm.value.telemetryLoading = false;
        }
      }
    })();
  } else if (statusConfirm.value) {
    statusConfirm.value.telemetryLoading = false;
  }
}

function cancelStatusConfirm(): void {
  statusConfirm.value = null;
}

async function applyStatusConfirm(payload: {
  datetimeLocal: string;
  odometer: string;
  odometer_source: "manual" | "wialon" | null;
}): Promise<void> {
  const pending = statusConfirm.value;
  statusConfirm.value = null;
  if (!pending) {
    return;
  }
  try {
    const iso = fromDatetimeLocalToIso(payload.datetimeLocal);
    const timeSource: "device" | "manual" = pending.initialDatetimeLocal === payload.datetimeLocal ? "device" : "manual";
    const base =
      currentSection.value === "driver_route_details" && selectedDriverRoute.value
        ? selectedDriverRoute.value
        : route.value;
    const current = base?.points.find((point) => point.id === pending.pointId);
    if (!current) {
      return;
    }
    const to = nextStatus(current.status);
    if (to === "docs") {
      docsUpload.value = {
        pointId: pending.pointId,
        occurredAtIso: iso,
        timeSource,
        odometer: payload.odometer,
        odometer_source: payload.odometer_source
      };
      return;
    }
    await markPointNext(pending.pointId, iso, undefined, {
      timeSource,
      odometer: payload.odometer,
      odometer_source: payload.odometer_source
    });
  } catch (error) {
    syncMessage.value = (error as Error).message;
  }
}

function cancelDocsUpload(): void {
  if (docsUploadAbort) {
    try {
      docsUploadAbort.abort();
    } catch {
      // ignore
    }
    docsUploadAbort = null;
    docsUploading.value = false;
  }
  docsUpload.value = null;
}

async function applyDocsUpload(files: File[]): Promise<void> {
  const ctx = docsUpload.value;
  if (!ctx || !route.value || !files.length) {
    return;
  }
  docsUploading.value = true;
  docsUploadAbort = new AbortController();
  try {
    const localKeys: string[] = [];
    for (const file of files) {
      const key = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
      const buffer = await file.arrayBuffer();
      const blob = new Blob([buffer], { type: file.type || "image/jpeg" });
      await savePendingDocBlob({
        local_key: key,
        point_id: ctx.pointId,
        route_id: route.value.id,
        blob,
        content_type: blob.type || "image/jpeg",
        created_at: new Date().toISOString()
      });
      localKeys.push(key);
    }
    const attach = { localKeys };
    docsUpload.value = null;
    await markPointNext(
      ctx.pointId,
      ctx.occurredAtIso,
      attach,
      { timeSource: ctx.timeSource, odometer: ctx.odometer, odometer_source: ctx.odometer_source }
    );
    await refreshConnectionQueue();
    syncMessage.value = hasNetwork()
      ? "Фото сохранены на телефоне. Отправка на сервер в фоне"
      : "Фото сохранены на телефоне. Уйдут при появлении сети";
  } catch (error) {
    const e = error as { name?: string; message?: string };
    reportDebugError({ source: "docs.local-save", error, extra: { files: files.length, point_id: ctx.pointId } });
    if (e?.name === "AbortError") {
      syncMessage.value = "Сохранение документов отменено";
    } else {
      syncMessage.value = `Не удалось сохранить фото на телефоне: ${(error as Error).message}`;
    }
  } finally {
    docsUploading.value = false;
    docsUploadAbort = null;
  }
}

type DocsAttach = { fileIds: number[] } | { localKeys: string[] };

async function markPointNext(
  pointId: number,
  occurredAtOverride?: string,
  docsAttach?: DocsAttach,
  options?: { timeSource?: "device" | "manual"; odometer?: string; odometer_source?: "manual" | "wialon" | null }
): Promise<void> {
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
  if (toStatus === "docs") {
    if (docsAttach && "fileIds" in docsAttach) {
      if (!docsAttach.fileIds.length) {
        return;
      }
    } else if (docsAttach && "localKeys" in docsAttach) {
      if (!docsAttach.localKeys.length) {
        return;
      }
    } else {
      return;
    }
  }

  const occurredAt = occurredAtOverride ?? new Date().toISOString();
  const event: EventPayload = {
    client_event_id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    occurred_at_client: occurredAt,
    point_id: pointId,
    to_status: toStatus,
    time_source: options?.timeSource ?? "device",
    odometer: (options?.odometer || "").trim() || null,
    odometer_source: options?.odometer_source ?? null,
    coordinates: null
  };
  if (toStatus === "docs" && docsAttach) {
    if ("fileIds" in docsAttach) {
      event.document_file_ids = docsAttach.fileIds;
    } else {
      event.document_local_keys = docsAttach.localKeys;
    }
  }

  current.status = toStatus;
  if (selectedDriverRoute.value?.id === route.value.id) {
    const selectedPoint = selectedDriverRoute.value.points.find((point) => point.id === pointId);
    if (selectedPoint) {
      selectedPoint.status = toStatus;
    }
  }
  await savePointOverlay(route.value.id, pointId, toStatus, occurredAt);
  await persistDriverRoute(route.value);
  await addOutboxEvent({
    ...event,
    device_id: getDeviceId(),
    created_at: new Date().toISOString()
  });
  syncMessage.value = hasNetwork() ? "Изменение сохранено, синхронизация в фоне" : "Изменение сохранено локально";
  void refreshConnectionQueue();
  void syncOutboxInBackground();
  if (route.value?.status === "success") {
    route.value = null;
    selectedDriverRoute.value = null;
    await persistDriverRoute(null);
    resetToSection("driver_home");
  }
}

async function doRevertPoint(pointId: number): Promise<void> {
  if (!authToken.value || !isDriver.value) {
    return;
  }
  if (!hasNetwork()) {
    syncMessage.value = "Откат статуса недоступен без сети.";
    return;
  }
  try {
    const updated = await revertPointStatus(authToken.value, pointId);
    if (route.value?.id === updated.id) {
      route.value = await applyOverlaysToRoute(updated);
      await saveActiveRoute(route.value);
    }
    if (selectedDriverRoute.value?.id === updated.id) {
      selectedDriverRoute.value = updated;
    }
    await refreshDriverRoutes();
    await refreshNotifications();
    syncMessage.value = "Статус точки возвращён";
  } catch (error) {
    syncMessage.value = `Не удалось откатить статус: ${(error as Error).message}`;
  }
}

async function openDriverRouteDetails(routeId: string): Promise<void> {
  if (!authToken.value || !isDriver.value) {
    return;
  }
  const cached = await loadRouteSnapshot(routeId);
  if (cached) {
    selectedDriverRoute.value = await applyOverlaysToRoute(cached);
    pushSection("driver_route_details");
    void refreshLogisticsContacts();
  }
  if (!hasNetwork()) {
    if (!selectedDriverRoute.value || selectedDriverRoute.value.id !== routeId) {
      const local = route.value?.id === routeId ? route.value : await loadActiveRoute();
      if (local?.id === routeId) {
        selectedDriverRoute.value = await applyOverlaysToRoute(local);
        pushSection("driver_route_details");
      } else {
        syncMessage.value = "Нет сохранённых данных рейса. Откройте его, когда появится сеть.";
      }
    }
    return;
  }
  try {
    selectedDriverRoute.value = await applyOverlaysToRoute(await getDriverRoute(authToken.value, routeId));
    if (selectedDriverRoute.value) {
      await saveRouteSnapshot(selectedDriverRoute.value);
    }
    pushSection("driver_route_details");
    void refreshLogisticsContacts();
  } catch (error) {
    if (!selectedDriverRoute.value || selectedDriverRoute.value.id !== routeId) {
      syncMessage.value = `Ошибка загрузки деталей рейса: ${(error as Error).message}`;
    }
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
  pushSection("notifications");
  void refreshWebPushSubscriptionState();
  void refreshNotifications();
}

async function openChatForRoute(routeId: string): Promise<void> {
  if (!authToken.value) {
    return;
  }
  chatRouteId.value = routeId;
  pushSection("chat");
  await refreshChat();
  if (chatUnreadByRoute.value[routeId]) {
    chatUnreadByRoute.value = { ...chatUnreadByRoute.value, [routeId]: 0 };
  }
  startChatPolling();
}

async function refreshChat(options?: { silent?: boolean }): Promise<void> {
  if (!authToken.value || !chatRouteId.value) {
    return;
  }
  if (!options?.silent) {
    chatLoading.value = true;
  }
  chatError.value = "";
  try {
    chatMessages.value = await listRouteChatMessages(authToken.value, chatRouteId.value);
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы открыть чат." })) {
      return;
    }
    chatError.value = (error as Error).message;
  } finally {
    if (!options?.silent) {
      chatLoading.value = false;
    }
  }
}

async function sendChat(text: string): Promise<void> {
  if (!authToken.value || !chatRouteId.value) {
    return;
  }
  chatLoading.value = true;
  try {
    const created = await sendRouteChatMessage(authToken.value, chatRouteId.value, { text });
    const exists = chatMessages.value.some((m) => m.id === created.id);
    if (!exists) {
      chatMessages.value = [...chatMessages.value, created];
    }
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы отправить сообщение." })) {
      return;
    }
    chatError.value = (error as Error).message;
  } finally {
    chatLoading.value = false;
  }
}

async function refreshChatsHub(): Promise<void> {
  if (!authToken.value) return;
  chatsLoading.value = true;
  chatsError.value = "";
  roomUnreadBump.value = {};
  try {
    await postChatsBootstrap(authToken.value);
    const [rooms, users] = await Promise.all([listChatRooms(authToken.value), listChatUsers(authToken.value)]);
    chatsRooms.value = rooms;
    chatsUsers.value = users;
    if (authUser.value && isLogisticRole(authUser.value.role_code)) {
      logisticDriverChatRooms.value = await listLogisticDriverChatRooms(authToken.value);
    } else {
      logisticDriverChatRooms.value = [];
    }
    if (authUser.value && isAccountantRole(authUser.value.role_code)) {
      accountantDriverChatRooms.value = await listAccountantDriverChatRooms(authToken.value);
    } else {
      accountantDriverChatRooms.value = [];
    }
    if (authUser.value && isAdminRole(authUser.value.role_code)) {
      adminChatRoomsLoading.value = true;
      try {
        adminChatRoomsList.value = await listAdminChatRooms(authToken.value);
      } finally {
        adminChatRoomsLoading.value = false;
      }
    } else {
      adminChatRoomsList.value = [];
    }
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы открыть чаты." })) {
      return;
    }
    chatsError.value = (error as Error).message;
  } finally {
    chatsLoading.value = false;
  }
}

async function refreshAdminChatRoomsOnly(): Promise<void> {
  if (!authToken.value || !authUser.value || !isAdminRole(authUser.value.role_code)) {
    return;
  }
  adminChatRoomsLoading.value = true;
  try {
    adminChatRoomsList.value = await listAdminChatRooms(authToken.value);
  } catch (error) {
    chatsError.value = (error as Error).message;
  } finally {
    adminChatRoomsLoading.value = false;
  }
}

async function doAdminBroadcast(payload: { title: string; message: string; role_codes: RoleCode[] }): Promise<void> {
  if (!authToken.value) return;
  if (!payload.title.trim() || !payload.message.trim()) {
    syncMessage.value = "Укажите заголовок и текст рассылки";
    return;
  }
  try {
    const res = await adminBroadcastByRoles(authToken.value, {
      title: payload.title.trim(),
      message: payload.message.trim(),
      role_codes: payload.role_codes
    });
    syncMessage.value = `Рассылка отправлена (${res.recipient_count} получателей)`;
    await refreshNotifications();
  } catch (error) {
    syncMessage.value = `Ошибка рассылки: ${(error as Error).message}`;
  }
}

async function doAdminDeleteRoom(roomId: number): Promise<void> {
  if (!authToken.value) return;
  if (!window.confirm(`Удалить комнату #${roomId}? Сообщения будут удалены.`)) {
    return;
  }
  try {
    await adminDeleteChatRoom(authToken.value, roomId);
    syncMessage.value = "Комната удалена";
    adminChatsHubTick.value += 1;
    await refreshChatsHub();
  } catch (error) {
    syncMessage.value = `Не удалось удалить: ${(error as Error).message}`;
  }
}

async function doAdminCreateRoom(payload: {
  title: string;
  system_key: string | null;
  member_user_ids: number[];
  role_codes: string[];
}): Promise<void> {
  if (!authToken.value) return;
  try {
    await adminCreateChatRoom(authToken.value, {
      title: payload.title,
      system_key: payload.system_key || undefined,
      member_user_ids: payload.member_user_ids,
      role_codes: payload.role_codes
    });
    syncMessage.value = "Комната создана";
    adminChatsHubTick.value += 1;
    await refreshChatsHub();
  } catch (error) {
    syncMessage.value = `Не удалось создать: ${(error as Error).message}`;
  }
}

async function doAdminPatchRoom(payload: { roomId: number; title: string }): Promise<void> {
  if (!authToken.value) return;
  try {
    await adminPatchChatRoom(authToken.value, payload.roomId, payload.title);
    syncMessage.value = "Название обновлено";
    adminChatsHubTick.value += 1;
    await refreshChatsHub();
  } catch (error) {
    syncMessage.value = `Не удалось сохранить: ${(error as Error).message}`;
  }
}

async function openChatRoom(roomId: number, titleHint?: string): Promise<void> {
  if (!authToken.value) return;
  const nextBump = { ...roomUnreadBump.value };
  delete nextBump[roomId];
  roomUnreadBump.value = nextBump;
  chatRoomId.value = roomId;
  chatRoomTitle.value = titleHint || `#${roomId}`;
  pushSection("chat_room");
  await refreshChatRoom();
  startRoomChatPolling();
}

function closeChatRoomToHub(): void {
  stopRoomChatPolling();
  goBack();
}

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

async function openDriverSalarySection(): Promise<void> {
  if (!authToken.value) return;
  const d = new Date();
  const y = d.getFullYear();
  const m = d.getMonth();
  const last = new Date(y, m + 1, 0).getDate();
  salaryDriverFilterFrom.value = `01.${pad2(m + 1)}.${y}`;
  salaryDriverFilterTo.value = `${pad2(last)}.${pad2(m + 1)}.${y}`;
  resetToSection("driver_salary");
  await refreshDriverSalaryList(salaryDriverFilterFrom.value, salaryDriverFilterTo.value);
}

async function refreshDriverSalaryList(dateFrom?: string, dateTo?: string): Promise<void> {
  if (!authToken.value) return;
  salaryListLoading.value = true;
  salaryError.value = "";
  try {
    salaryListMine.value = await listMySalaries(authToken.value, dateFrom, dateTo);
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново." })) {
      return;
    }
    salaryError.value = (error as Error).message;
  } finally {
    salaryListLoading.value = false;
  }
}

async function onDriverSalaryRefresh(from?: string, to?: string): Promise<void> {
  if (from) salaryDriverFilterFrom.value = from;
  if (to) salaryDriverFilterTo.value = to;
  await refreshDriverSalaryList(salaryDriverFilterFrom.value, salaryDriverFilterTo.value);
}

async function exportDriverSalaryCsv(dateFrom: string, dateTo: string): Promise<void> {
  if (!authToken.value) return;
  try {
    const blob = await fetchMySalaryCsvBlob(authToken.value, dateFrom, dateTo);
    downloadBlob(blob, `расчеты_${dateFrom}_${dateTo}.csv`.replace(/\./g, "-"));
    syncMessage.value = "CSV сохранён";
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново." })) {
      return;
    }
    salaryError.value = (error as Error).message;
  }
}

async function exportAccountantSalaryCsv(dateFrom: string, dateTo: string): Promise<void> {
  if (!authToken.value || !salarySelectedDriver.value) return;
  try {
    const blob = await fetchDriverSalaryCsvBlob(authToken.value, salarySelectedDriver.value.id, dateFrom, dateTo);
    const name = (salarySelectedDriver.value.full_name || salarySelectedDriver.value.login || String(salarySelectedDriver.value.id)).replace(
      /\s+/g,
      "_"
    );
    downloadBlob(blob, `расчеты_${name}_${dateFrom}_${dateTo}.csv`.replace(/\./g, "-"));
    syncMessage.value = "CSV сохранён";
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново." })) {
      return;
    }
    salaryError.value = (error as Error).message;
  }
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.setTimeout(() => URL.revokeObjectURL(url), 15_000);
}

function openSalaryDetail(row: SalaryRecord, backSection: AppSection): void {
  salaryCurrentRecord.value = row;
  salaryDetailBackSection.value = backSection;
  pushSection("salary_detail");
}

function closeSalaryDetail(): void {
  goBack();
}

async function doSalaryConfirm(): Promise<void> {
  if (!authToken.value || !salaryCurrentRecord.value) return;
  salaryDetailBusy.value = true;
  try {
    const updated = await confirmSalary(authToken.value, salaryCurrentRecord.value.id);
    salaryCurrentRecord.value = updated;
    salaryListMine.value = salaryListMine.value.map((row) => (row.id === updated.id ? updated : row));
    salaryAccountantItems.value = salaryAccountantItems.value.map((row) => (row.id === updated.id ? updated : row));
    syncMessage.value = "Расчёт подтверждён";
  } catch (error) {
    syncMessage.value = (error as Error).message;
  } finally {
    salaryDetailBusy.value = false;
  }
}

async function doSalaryComment(text: string): Promise<void> {
  if (!authToken.value || !salaryCurrentRecord.value) return;
  salaryDetailBusy.value = true;
  try {
    const updated = await commentSalary(authToken.value, salaryCurrentRecord.value.id, text);
    salaryCurrentRecord.value = updated;
    salaryListMine.value = salaryListMine.value.map((row) => (row.id === updated.id ? updated : row));
    salaryAccountantItems.value = salaryAccountantItems.value.map((row) => (row.id === updated.id ? updated : row));
    syncMessage.value = "Комментарий отправлен";
  } catch (error) {
    syncMessage.value = (error as Error).message;
  } finally {
    salaryDetailBusy.value = false;
  }
}

async function doSalaryDelete(): Promise<void> {
  if (!authToken.value || !salaryCurrentRecord.value || !(isAdmin.value || isAccountant.value)) return;
  salaryDetailBusy.value = true;
  try {
    const deletedId = salaryCurrentRecord.value.id;
    await deleteSalary(authToken.value, deletedId);
    salaryCurrentRecord.value = null;
    salaryAccountantItems.value = salaryAccountantItems.value.filter((row) => row.id !== deletedId);
    salaryListMine.value = salaryListMine.value.filter((row) => row.id !== deletedId);
    syncMessage.value = "Расчёт удалён";
    closeSalaryDetail();
  } catch (error) {
    syncMessage.value = (error as Error).message;
  } finally {
    salaryDetailBusy.value = false;
  }
}

async function openSalaryChatFromDetail(): Promise<void> {
  if (!salaryCurrentRecord.value || !authToken.value) return;
  salaryChatSalaryId.value = salaryCurrentRecord.value.id;
  pushSection("salary_chat");
  await refreshSalaryChat();
  startSalaryChatPolling();
}

function closeSalaryChat(): void {
  stopSalaryChatPolling();
  goBack();
}

async function refreshSalaryChat(options?: { silent?: boolean }): Promise<void> {
  if (!authToken.value || !salaryChatSalaryId.value) return;
  if (!options?.silent) {
    salaryChatLoading.value = true;
  }
  salaryChatError.value = "";
  try {
    salaryChatMessages.value = await listSalaryChatMessages(authToken.value, salaryChatSalaryId.value);
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново." })) {
      return;
    }
    salaryChatError.value = (error as Error).message;
  } finally {
    if (!options?.silent) {
      salaryChatLoading.value = false;
    }
  }
}

async function sendSalaryChat(text: string): Promise<void> {
  if (!authToken.value || !salaryChatSalaryId.value) return;
  salaryChatLoading.value = true;
  try {
    const created = await sendSalaryChatMessage(authToken.value, salaryChatSalaryId.value, { text });
    const exists = salaryChatMessages.value.some((m) => m.id === created.id);
    if (!exists) {
      salaryChatMessages.value = [...salaryChatMessages.value, created];
    }
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла." })) {
      return;
    }
    salaryChatError.value = (error as Error).message;
  } finally {
    salaryChatLoading.value = false;
  }
}

async function uploadSalaryChatFiles(payload: { text: string; files: File[] }): Promise<void> {
  if (!authToken.value || !salaryChatSalaryId.value || !payload.files.length) return;
  salaryChatLoading.value = true;
  try {
    const created = await uploadSalaryChatAttachments(authToken.value, salaryChatSalaryId.value, payload.files, {
      text: payload.text
    });
    const exists = salaryChatMessages.value.some((m) => m.id === created.id);
    if (!exists) {
      salaryChatMessages.value = [...salaryChatMessages.value, created];
    }
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла." })) {
      return;
    }
    salaryChatError.value = (error as Error).message;
  } finally {
    salaryChatLoading.value = false;
  }
}

async function downloadSalaryChatAttachment(payload: { attachmentId: number; originalName: string }): Promise<void> {
  if (!authToken.value) return;
  try {
    const blob = await fetchSalaryChatAttachmentBlob(authToken.value, payload.attachmentId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = payload.originalName || `file-${payload.attachmentId}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
  } catch (error) {
    salaryChatError.value = `Не удалось скачать: ${(error as Error).message}`;
  }
}

async function searchSalaryDriversForAccounting(q: string): Promise<void> {
  if (!authToken.value || !q.trim()) return;
  salaryError.value = "";
  try {
    salaryAccountantDrivers.value = await lookupSalaryDrivers(authToken.value, q.trim());
  } catch (error) {
    salaryError.value = (error as Error).message;
  }
}

async function pickSalaryAccountantDriver(userId: number): Promise<void> {
  if (!authToken.value) return;
  const d = salaryAccountantDrivers.value.find((x) => x.id === userId);
  if (!d) return;
  salarySelectedDriver.value = { id: d.id, login: d.login, full_name: d.full_name };
  await refreshAccountantSalaryList();
}

async function refreshAccountantSalaryList(dateFrom?: string, dateTo?: string): Promise<void> {
  if (!authToken.value || !salarySelectedDriver.value) return;
  salaryListLoading.value = true;
  salaryError.value = "";
  try {
    const res = await listSalariesForDriver(authToken.value, salarySelectedDriver.value.id, dateFrom, dateTo);
    salaryAccountantItems.value = res.items;
  } catch (error) {
    salaryError.value = (error as Error).message;
  } finally {
    salaryListLoading.value = false;
  }
}

async function createSalaryFromAccountant(payload: { driver_user_id: number; salary_line: string }): Promise<void> {
  if (!authToken.value) return;
  salarySaving.value = true;
  salaryError.value = "";
  try {
    await createSalaryManual(authToken.value, payload);
    syncMessage.value = "Расчёт создан";
    await refreshAccountantSalaryList();
  } catch (error) {
    salaryError.value = (error as Error).message;
  } finally {
    salarySaving.value = false;
  }
}

async function refreshLogisticsContacts(): Promise<void> {
  if (!authToken.value) return;
  logisticsContactsLoading.value = true;
  logisticsContactsError.value = "";
  try {
    logisticsContacts.value = await listLogisticsContacts(authToken.value);
    const latest = logisticsContacts.value.map((item) => ({ name: item.name, phone: item.phone }));
    if (selectedDriverRoute.value) {
      selectedDriverRoute.value = { ...selectedDriverRoute.value, logistics_contacts: latest };
      await saveRouteSnapshot(selectedDriverRoute.value);
    }
    if (route.value) {
      route.value = { ...route.value, logistics_contacts: latest };
      await saveRouteSnapshot(route.value);
    }
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново." })) {
      return;
    }
    logisticsContactsError.value = (error as Error).message;
  } finally {
    logisticsContactsLoading.value = false;
  }
}

async function doSaveLogisticsContacts(items: Array<{ name: string; phone: string }>): Promise<void> {
  if (!authToken.value) return;
  logisticsContactsSaving.value = true;
  logisticsContactsError.value = "";
  try {
    logisticsContacts.value = await saveLogisticsContacts(authToken.value, items);
    syncMessage.value = "Контакты логистов сохранены";
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново." })) {
      return;
    }
    logisticsContactsError.value = (error as Error).message;
  } finally {
    logisticsContactsSaving.value = false;
  }
}

async function refreshChatRoom(options?: { silent?: boolean }): Promise<void> {
  if (!authToken.value || !chatRoomId.value) return;
  if (!options?.silent) {
    chatRoomLoading.value = true;
  }
  chatRoomError.value = "";
  try {
    chatRoomMessages.value = await listChatRoomMessages(authToken.value, chatRoomId.value);
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы открыть чат." })) {
      return;
    }
    chatRoomError.value = (error as Error).message;
  } finally {
    if (!options?.silent) {
      chatRoomLoading.value = false;
    }
  }
}

async function sendChatRoom(text: string): Promise<void> {
  if (!authToken.value || !chatRoomId.value) return;
  chatRoomLoading.value = true;
  try {
    const created = await sendChatRoomMessage(authToken.value, chatRoomId.value, { text });
    const exists = chatRoomMessages.value.some((m) => m.id === created.id);
    if (!exists) {
      chatRoomMessages.value = [...chatRoomMessages.value, created];
    }
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы отправить сообщение." })) {
      return;
    }
    chatRoomError.value = (error as Error).message;
  } finally {
    chatRoomLoading.value = false;
  }
}

async function uploadChatRoomFiles(payload: { text: string; files: File[] }): Promise<void> {
  if (!authToken.value || !chatRoomId.value) return;
  if (!payload.files.length) return;
  chatRoomLoading.value = true;
  try {
    const created = await uploadChatRoomAttachments(authToken.value, chatRoomId.value, payload.files, { text: payload.text });
    const exists = chatRoomMessages.value.some((m) => m.id === created.id);
    if (!exists) {
      chatRoomMessages.value = [...chatRoomMessages.value, created];
    }
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы отправить файлы." })) {
      return;
    }
    chatRoomError.value = (error as Error).message;
  } finally {
    chatRoomLoading.value = false;
  }
}

async function downloadChatRoomAttachment(payload: { attachmentId: number; originalName: string }): Promise<void> {
  if (!authToken.value) return;
  try {
    const blob = await fetchChatRoomAttachmentBlob(authToken.value, payload.attachmentId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = payload.originalName || `file-${payload.attachmentId}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
  } catch (error) {
    chatRoomError.value = `Не удалось скачать файл: ${(error as Error).message}`;
  }
}

async function openDirectWithUser(userId: number): Promise<void> {
  if (!authToken.value) return;
  try {
    const res = await openDirectChat(authToken.value, userId);
    await refreshChatsHub();
    await openChatRoom(res.room.id, res.room.title);
  } catch (error) {
    chatsError.value = (error as Error).message;
  }
}

async function uploadChatFiles(payload: { text: string; files: File[] }): Promise<void> {
  if (!authToken.value || !chatRouteId.value) {
    return;
  }
  if (!payload.files.length) {
    return;
  }
  chatLoading.value = true;
  try {
    const created = await uploadRouteChatAttachments(authToken.value, chatRouteId.value, payload.files, { text: payload.text });
    const exists = chatMessages.value.some((m) => m.id === created.id);
    if (!exists) {
      chatMessages.value = [...chatMessages.value, created];
    }
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы отправить файлы." })) {
      return;
    }
    chatError.value = (error as Error).message;
  } finally {
    chatLoading.value = false;
  }
}

async function downloadChatAttachment(payload: { attachmentId: number; originalName: string }): Promise<void> {
  if (!authToken.value) {
    return;
  }
  try {
    const blob = await fetchChatAttachmentBlob(authToken.value, payload.attachmentId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = payload.originalName || `file-${payload.attachmentId}`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
  } catch (error) {
    chatError.value = `Не удалось скачать файл: ${(error as Error).message}`;
  }
}

function openDriverRoutes(): void {
  profileMenuOpen.value = false;
  pushSection("driver_routes");
  void refreshDriverData();
}

function openDriverHome(): void {
  goBack();
}

function advanceActivePointFromHome(): void {
  if (!route.value) {
    return;
  }
  const activePoint = route.value.points.find((point) => !isPointDone(point.status));
  if (!activePoint) {
    return;
  }
  openStatusConfirm(activePoint.id);
}

function logout(): void {
  clearAuth();
}

async function resetConnections(): Promise<void> {
  if (!authToken.value || resettingConnections.value) {
    return;
  }
  profileMenuOpen.value = false;
  resettingConnections.value = true;
  syncMessage.value = "Переподключение…";
  try {
    denyRealtimeSockets();
    stopNotificationsPolling();
    stopChatPolling();
    stopRoomChatPolling();
    stopSalaryChatPolling();
    stopBackgroundSyncLoop();
    closeNotificationsSocket();
    closeChatSocket();
    await new Promise((resolve) => window.setTimeout(resolve, 400));
    restartConnectionWatch(API_BASE);
    await pingServer();
    await refreshNotifications();
    void refreshRouteChatUnread();
    if (isRouteManager.value) {
      await refreshAdminRoutes(routeFilters.value);
    }
    if (isDriver.value) {
      startBackgroundSyncLoop();
    }
    if (currentSection.value === "chat" && chatRouteId.value) {
      startChatPolling();
    }
    if (currentSection.value === "chat_room" && chatRoomId.value) {
      startRoomChatPolling();
    }
    if (currentSection.value === "salary_chat" && salaryChatSalaryId.value) {
      startSalaryChatPolling();
    }
    allowRealtimeSockets();
    connectNotificationsSocket();
    startNotificationsPolling();
    syncMessage.value = "Соединения сброшены";
  } finally {
    resettingConnections.value = false;
  }
}

function isEditableTarget(el: EventTarget | null): el is HTMLElement {
  if (!(el instanceof HTMLElement)) {
    return false;
  }
  const tag = el.tagName;
  if (tag === "TEXTAREA" || tag === "SELECT") {
    return true;
  }
  if (tag === "INPUT") {
    const type = ((el as HTMLInputElement).type || "text").toLowerCase();
    return !["button", "submit", "reset", "checkbox", "radio", "file", "hidden", "range", "color", "image"].includes(
      type
    );
  }
  return el.isContentEditable;
}

function updateViewportVars(): void {
  const vv = window.visualViewport;
  const height = Math.round(vv?.height ?? window.innerHeight);
  const offset = Math.round(vv?.offsetTop ?? 0);
  document.documentElement.style.setProperty("--vv-height", `${height}px`);
  document.documentElement.style.setProperty("--vv-offset", `${offset}px`);
  const focused = isEditableTarget(document.activeElement);
  const drop = window.innerHeight - height;
  const shortViewport = height < window.screen.height * 0.64;
  const open = focused && (drop > 120 || shortViewport);
  keyboardOpen.value = open;
  document.documentElement.classList.toggle("keyboard-open", open);
  if (open || offset > 0 || window.scrollY > 0) {
    window.scrollTo(0, 0);
  }
}

function scrollFocusedIntoView(): void {
  const el = document.activeElement;
  const scroller = appScrollEl.value;
  if (!isEditableTarget(el) || !scroller) {
    return;
  }
  const rect = el.getBoundingClientRect();
  const box = scroller.getBoundingClientRect();
  const pad = 24;
  if (rect.bottom > box.bottom - pad) {
    scroller.scrollTop += rect.bottom - (box.bottom - pad);
  } else if (rect.top < box.top + pad) {
    scroller.scrollTop -= box.top + pad - rect.top;
  }
}

function syncChatViewportLock(): void {
  updateViewportVars();
  if (isChatSection.value && !keyboardOpen.value) {
    window.scrollTo(0, 0);
    if (appScrollEl.value) {
      appScrollEl.value.scrollTop = 0;
    }
  }
}

function onViewportChange(): void {
  updateViewportVars();
  if (keyboardOpen.value) {
    void nextTick(() => scrollFocusedIntoView());
  }
}

watch(isChatSection, () => {
  syncChatViewportLock();
});

function onFocusIn(event: FocusEvent): void {
  if (!isEditableTarget(event.target)) {
    return;
  }
  window.setTimeout(() => {
    updateViewportVars();
    scrollFocusedIntoView();
  }, 320);
}

function onIosInputBlur(event: FocusEvent): void {
  if (!isEditableTarget(event.target)) {
    return;
  }
  window.setTimeout(() => {
    if (isEditableTarget(document.activeElement)) {
      return;
    }
    window.scrollTo(0, 0);
    updateViewportVars();
  }, 80);
}

onMounted(async () => {
  startConnectionWatch(API_BASE);
  const token = localStorage.getItem(TOKEN_STORAGE_KEY) || "";
  const rawUser = localStorage.getItem(USER_STORAGE_KEY);
  authToken.value = token;
  authUser.value = rawUser ? (JSON.parse(rawUser) as AuthUser) : null;
  if (token && authUser.value) {
    await persistAuth(token, authUser.value);
  }
  route.value = await loadActiveRoute();
  if (isDriver.value) {
    await hydrateDriverRoutesFromCache();
  }
  if (authUser.value) {
    openDefaultSectionByRole(authUser.value);
  }
  if (token && authUser.value) {
    await bootstrapByRole(authUser.value);
  }
  window.addEventListener("online", onOnline);
  window.addEventListener("offline", onOffline);
  window.addEventListener("mousedown", onDocumentClick);
  window.addEventListener("pagehide", onPageHide);
  window.addEventListener("pageshow", onPageShow);
  window.addEventListener("resize", onViewportChange);
  window.visualViewport?.addEventListener("resize", onViewportChange);
  window.visualViewport?.addEventListener("scroll", onViewportChange);
  document.addEventListener("visibilitychange", onVisibilityChange);
  document.addEventListener("focusin", onFocusIn);
  document.addEventListener("focusout", onIosInputBlur);
  syncChatViewportLock();
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.addEventListener("message", onServiceWorkerMessage);
  }
});

onUnmounted(() => {
  if (toastTimer) {
    window.clearTimeout(toastTimer);
  }
  if (syncWatchdogTimer !== null) {
    window.clearTimeout(syncWatchdogTimer);
  }
  stopConnectionWatch();
  stopWsWatchdog();
  stopBackgroundSyncLoop();
  closeNotificationsSocket();
  stopNotificationsPolling();
  closeChatSocket();
  stopChatPolling();
  stopRoomChatPolling();
  stopSalaryChatPolling();
  window.removeEventListener("online", onOnline);
  window.removeEventListener("offline", onOffline);
  window.removeEventListener("mousedown", onDocumentClick);
  window.removeEventListener("pagehide", onPageHide);
  window.removeEventListener("pageshow", onPageShow);
  window.removeEventListener("resize", onViewportChange);
  window.visualViewport?.removeEventListener("resize", onViewportChange);
  window.visualViewport?.removeEventListener("scroll", onViewportChange);
  document.removeEventListener("visibilitychange", onVisibilityChange);
  document.removeEventListener("focusin", onFocusIn);
  document.removeEventListener("focusout", onIosInputBlur);
  document.documentElement.classList.remove("chat-lock");
  document.documentElement.classList.remove("keyboard-open");
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.removeEventListener("message", onServiceWorkerMessage);
  }
});
</script>

<template>
  <div
    class="app-shell"
    :class="{
      'is-chat': isChatSection,
      'has-tabbar': showBottomNav && !keyboardOpen,
      'keyboard-open': keyboardOpen
    }"
  >
    <div ref="appScrollEl" class="app-scroll">
  <main
    class="container"
    :class="{
      'container--chat': isChatSection
    }"
  >
    <header class="topbar">
      <div class="topbar-side">
        <button v-if="isAuthed" class="icon-btn bell-btn" type="button" aria-label="Уведомления" @click="openNotifications">
          <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
            <path
              d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <path d="M10 21a2 2 0 0 0 4 0" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
          </svg>
          <span v-if="hasUnreadNotifications" class="notif-dot" />
        </button>
      </div>

      <div class="topbar-center">
        <p class="brand-mark">ДМК</p>
        <h1 class="topbar-title">{{ currentPageTitle }}</h1>
        <ConnectionStatusBadge :alert-count="isAdmin ? unreadDebugCount : 0" @open="onConnectionBadgeClick" />
      </div>

      <div class="topbar-side right">
        <HeaderNav
          v-if="showHeaderNav"
          :items="headerNavItems"
          :active-id="activeBottomNavId"
          :chats-unread="hasUnreadChatsNav"
          :routes-unread="hasUnreadRouteChats"
          @select="selectBottomNav"
        />
        <div v-if="isAuthed" class="profile-wrap">
          <button class="profile-btn" type="button" @click="toggleProfileMenu">
            <span class="avatar">{{ profileInitials }}</span>
            <span class="profile-label">{{ profileDisplayName }}</span>
            <span class="caret" :class="{ open: profileMenuOpen }">▾</span>
          </button>
          <Transition name="dropdown">
            <div v-if="profileMenuOpen" class="profile-dropdown">
              <p class="profile-name">{{ profileDisplayName }}</p>
              <p class="profile-role">{{ authUser?.role_label }}</p>
              <button
                v-for="item in profileMenuItems"
                :key="item.section"
                class="menu-item"
                :class="{ active: currentSection === item.section, 'tabbar-item': item.tabBar, 'header-nav-item': item.headerNav }"
                type="button"
                @click="selectProfileSection(item.section)"
              >
                {{ item.label }}
                <span v-if="item.section === 'chats' && hasUnreadChatsNav" class="notif-dot menu-dot" />
                <span
                  v-else-if="(item.section === 'admin_routes' || item.section === 'driver_routes') && hasUnreadRouteChats"
                  class="notif-dot menu-dot success-dot"
                />
              </button>
              <button class="menu-item" type="button" :disabled="resettingConnections" @click="resetConnections">
                {{ resettingConnections ? "Переподключение…" : "Переподключить" }}
              </button>
              <button class="menu-item danger" type="button" @click="logout">Выход</button>
            </div>
          </Transition>
        </div>
      </div>
    </header>

    <Transition name="page" mode="out-in">
      <div :key="isAuthed ? currentSection : 'login'" class="page-stage">
    <LoginView v-if="!isAuthed" :loading="authLoading" :error="authError" @submit="doLogin" />

    <section v-else-if="isRouteManager && currentSection === 'admin_routes'">
      <AdminRoutesView
        :routes="adminRoutes"
        :drivers="routeDrivers"
        :logistics="routeLogistics"
        :logistics-contacts="logisticsContacts"
        :current-user-id="authUser?.id ?? 0"
        :loading="routesLoading"
        :error="routesError"
        :unread-by-route="chatUnreadByRoute"
        :initial-filters="routeFilters"
        @refresh="refreshAdminRoutes"
        @create="doCreateAdminRoute"
        @create-onec="doCreateAdminRouteFromOnec"
        @select-route="doSelectAdminRoute"
      />
    </section>

    <section v-else-if="isRouteManager && currentSection === 'admin_route_details' && selectedAdminRoute">
      <AdminRouteDetailsView
        :route="selectedAdminRoute"
        :drivers="routeDrivers"
        :logistics="routeLogistics"
        :logistics-contacts="logisticsContacts"
        :loading="routesLoading"
        :auth-token="authToken"
        :unread-chat-count="chatUnreadByRoute[selectedAdminRoute.id] ?? 0"
        :error="routesError"
        @back="goBack"
        @assign-driver="doAssignAdminRoute"
        @cancel-route="doCancelAdminRoute"
        @delete-route="doDeleteAdminRoute"
        @update-route="doUpdateAdminRoute"
        @update-point="doUpdateAdminRoutePoint"
        @open-chat="openChatForRoute"
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

    <section v-else-if="isAdmin && currentSection === 'admin_logistics_contacts'">
      <AdminLogisticsContactsView
        :items="logisticsContacts"
        :loading="logisticsContactsLoading"
        :saving="logisticsContactsSaving"
        :error="logisticsContactsError"
        @refresh="refreshLogisticsContacts"
        @save="doSaveLogisticsContacts"
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
        @revert-active-point="doRevertPoint"
      />
    </section>

    <section v-else-if="isDriver && currentSection === 'driver_routes'">
      <DriverRoutesView
        :assigned="driverAssignedRoutes"
        :history="driverHistoryRoutes"
        :loading="driverRoutesLoading"
        :active-route-id="route?.id || null"
        :unread-by-route="chatUnreadByRoute"
        @back="goBack"
        @open-route="openDriverRouteDetails"
        @refresh="refreshDriverData"
      />
    </section>

    <section v-else-if="isDriver && currentSection === 'driver_route_details' && selectedDriverRoute">
      <DriverRouteDetailsView
        :route="selectedDriverRoute"
        :active-route-id="route?.id || null"
        :syncing="syncing"
        :can-accept-route="canAcceptSelectedDriverRoute"
        :unread-chat-count="chatUnreadByRoute[selectedDriverRoute.id] ?? 0"
        :logistics-contacts="logisticsContacts"
        @back="goBack"
        @advance-point="openStatusConfirm"
        @revert-point="doRevertPoint"
        @accept-route="() => doAcceptRoute(selectedDriverRoute.id)"
        @open-chat="openChatForRoute"
      />
    </section>

    <section v-else-if="currentSection === 'chat' && chatRouteId">
      <ChatView
        :route-id="chatRouteId"
        :items="chatMessages"
        :loading="chatLoading"
        :error="chatError"
        :can-send="Boolean(isAuthed)"
        :current-user-id="authUser?.id ?? null"
        @back="goBack"
        @send="sendChat"
        @upload="uploadChatFiles"
        @download="downloadChatAttachment"
      />
    </section>

    <section v-else-if="currentSection === 'chat_room' && chatRoomId">
      <ChatView
        :route-id="String(chatRoomId)"
        :title="chatRoomTitle"
        :items="chatRoomMessages"
        :loading="chatRoomLoading"
        :error="chatRoomError"
        :can-send="Boolean(isAuthed)"
        :current-user-id="authUser?.id ?? null"
        @back="closeChatRoomToHub"
        @send="sendChatRoom"
        @upload="uploadChatRoomFiles"
        @download="downloadChatRoomAttachment"
      />
    </section>

    <section v-else-if="isDriver && currentSection === 'driver_salary'">
      <DriverSalaryView
        :items="salaryListMine"
        :loading="salaryListLoading"
        :error="salaryError"
        :initial-from="salaryDriverFilterFrom"
        :initial-to="salaryDriverFilterTo"
        @back="goBack"
        @refresh="onDriverSalaryRefresh"
        @export-csv="exportDriverSalaryCsv"
        @select="(r) => openSalaryDetail(r, 'driver_salary')"
      />
    </section>

    <section v-else-if="(isAdmin || isAccountant) && currentSection === 'salary_accounting'">
      <AccountantSalaryView
        :drivers="salaryAccountantDrivers"
        :items="salaryAccountantItems"
        :selected-driver="salarySelectedDriver"
        :loading="salaryListLoading"
        :saving="salarySaving"
        :error="salaryError"
        @back="goBack"
        @search="(q) => void searchSalaryDriversForAccounting(q)"
        @pick-driver="(id) => void pickSalaryAccountantDriver(id)"
        @refresh-list="(a, b) => void refreshAccountantSalaryList(a, b)"
        @create="(p) => void createSalaryFromAccountant(p)"
        @select="(r) => openSalaryDetail(r, 'salary_accounting')"
        @export-csv="exportAccountantSalaryCsv"
      />
    </section>

    <section v-else-if="currentSection === 'salary_detail' && salaryCurrentRecord">
      <SalaryDetailView
        :record="salaryCurrentRecord"
        :is-driver="isDriver"
        :can-delete="isAdmin || isAccountant"
        :busy="salaryDetailBusy"
        @back="closeSalaryDetail"
        @confirm="doSalaryConfirm"
        @comment="doSalaryComment"
        @open-chat="openSalaryChatFromDetail"
        @remove="doSalaryDelete"
      />
    </section>

    <section v-else-if="currentSection === 'salary_chat' && salaryChatSalaryId">
      <ChatView
        :route-id="String(salaryChatSalaryId)"
        :title="`Чат расчёта #${salaryChatSalaryId}`"
        :items="salaryChatItemsForChatView"
        :loading="salaryChatLoading"
        :error="salaryChatError"
        :can-send="Boolean(isAuthed)"
        :current-user-id="authUser?.id ?? null"
        @back="closeSalaryChat"
        @send="sendSalaryChat"
        @upload="uploadSalaryChatFiles"
        @download="downloadSalaryChatAttachment"
      />
    </section>

    <section v-else-if="currentSection === 'chats'">
      <ChatsHubView
        :rooms="chatsRoomsForDisplay"
        :users="chatsUsers"
        :loading="chatsLoading"
        :error="chatsError"
        :logistic-driver-rooms="logisticDriverChatRoomsDisplay"
        :accountant-driver-rooms="accountantDriverChatRoomsDisplay"
        :is-logistic="isLogistic"
        :is-accountant="isAccountant"
        :is-driver="isDriver"
        :current-user-id="authUser?.id ?? null"
        :is-admin="isAdmin"
        :admin-rooms="adminChatRoomsList"
        :admin-rooms-loading="adminChatRoomsLoading"
        :admin-chat-tick="adminChatsHubTick"
        @back="goBack"
        @refresh="refreshChatsHub"
        @open-room="(id, title) => openChatRoom(id, title)"
        @open-direct-with="openDirectWithUser"
        @admin-broadcast="doAdminBroadcast"
        @admin-delete-room="doAdminDeleteRoom"
        @admin-refresh-rooms="refreshAdminChatRoomsOnly"
        @admin-create-room="doAdminCreateRoom"
        @admin-patch-room="doAdminPatchRoom"
      />
    </section>

    <section v-else-if="currentSection === 'notifications'">
      <NotificationsView
        :items="notifications"
        :loading="notificationsLoading"
        :error="notificationsError"
        :unread-count="unreadNotificationsCount"
        :can-push="pushIsSupported"
        :push-enabled="webPushSubscribed"
        :push-hint="pushHint"
        @refresh="refreshNotifications"
        @enable-push="trySubscribeWebPush"
        @disable-push="tryUnsubscribeWebPush"
        @mark-read="doMarkNotificationRead"
        @mark-all-read="doMarkAllNotificationsRead"
        @open-from-notification="openNotificationFromItem"
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
      </div>
    </Transition>
    </main>
    </div>

    <BottomNav
      v-if="showBottomNav && !keyboardOpen"
      :items="bottomNavItems"
      :active-id="activeBottomNavId"
      :chats-unread="hasUnreadChatsNav"
      :routes-unread="hasUnreadRouteChats"
      @select="selectBottomNav"
    />

    <Transition name="toast">
      <div v-if="isAuthed && toastVisible" class="app-toast" role="status">{{ toastText }}</div>
    </Transition>

    <StatusConfirmDialog
      v-if="isAuthed && statusConfirm"
      :open="true"
      :next-status-label="statusConfirm.nextLabel"
      :datetime-local="statusConfirm.datetimeLocal"
      :show-odometer="statusConfirm.showOdometer"
      :odometer="statusConfirm.odometer"
      :initial-odometer="statusConfirm.initialOdometer"
      :odometer-prefill-source="statusConfirm.odometerPrefillSource"
      :telemetry-loading="statusConfirm.telemetryLoading"
      @update:datetime-local="
        (v) => {
          if (statusConfirm) statusConfirm.datetimeLocal = v;
        }
      "
      @update:odometer="
        (v) => {
          if (statusConfirm) statusConfirm.odometer = v;
        }
      "
      @cancel="cancelStatusConfirm"
      @confirm="applyStatusConfirm($event)"
    />
    <DocsUploadDialog
      v-if="isDriver && docsUpload"
      :open="true"
      :uploading="docsUploading"
      @cancel="cancelDocsUpload"
      @confirm="applyDocsUpload($event)"
    />
    <MapsChooser />
    <AdminErrorDebugPanel v-if="isAdmin && adminDebugOpen" @close="adminDebugOpen = false" />
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  max-height: 100%;
  min-height: 0;
  overflow: hidden;
  overscroll-behavior: none;
}
.app-shell.keyboard-open {
  height: var(--vv-height, 100%);
  max-height: var(--vv-height, 100%);
  transform: translate3d(0, var(--vv-offset, 0px), 0);
}
.app-scroll {
  flex: 1 1 0;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior-y: contain;
}
.app-shell.is-chat .app-scroll {
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.container {
  max-width: none;
  width: 100%;
  margin: 0;
  padding: 0.85rem 1.5rem 1.25rem;
  color: var(--text);
  font-family: var(--font);
  box-sizing: border-box;
}
.container.container--chat {
  position: relative;
  flex: 1 1 auto;
  width: 100%;
  height: 100%;
  max-height: none;
  min-height: 0;
  margin: 0;
  padding: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  overscroll-behavior: none;
}
.container.container--chat > .topbar {
  flex-shrink: 0;
  margin: 0;
  padding: 0.7rem 1rem 0.55rem;
}
.container.container--chat > .page-stage {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.container.container--chat > .page-stage > section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.page-stage {
  min-width: 0;
  width: 100%;
}
.page-stage > section {
  width: 100%;
  max-width: none;
}
.topbar {
  position: sticky;
  top: 0;
  z-index: 30;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 0.7rem;
  margin: -0.85rem -1.5rem 0.95rem;
  padding: calc(0.55rem + env(safe-area-inset-top, 0px)) 1.5rem 0.65rem;
  background: rgba(3, 7, 18, 0.78);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--border);
}
.topbar-side {
  display: flex;
  align-items: center;
  min-width: 0;
}
.topbar-side.right {
  justify-content: flex-end;
  gap: 0.55rem;
}
.topbar-center {
  display: grid;
  justify-items: center;
  gap: 0.12rem;
  min-width: 0;
}
.brand-mark {
  margin: 0;
  font-size: 0.68rem;
  font-weight: 800;
  letter-spacing: 0.18em;
  color: #93c5fd;
}
.topbar-title {
  margin: 0;
  text-align: center;
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.icon-btn {
  width: 42px;
  height: 42px;
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.9);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  position: relative;
}
.notif-dot {
  position: absolute;
  top: 7px;
  right: 7px;
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: var(--danger);
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.18);
  animation: pulse-dot 1.8s ease-in-out infinite;
}
.profile-wrap {
  position: relative;
}
.profile-btn {
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.9);
  color: #fff;
  padding: 0.22rem 0.55rem 0.22rem 0.22rem;
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  max-width: 220px;
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: linear-gradient(180deg, #3b82f6, #1d4ed8);
  font-size: 0.72rem;
  font-weight: 700;
  flex-shrink: 0;
}
.profile-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.88rem;
}
.caret {
  font-size: 0.8rem;
  color: #cbd5e1;
  transition: transform 0.16s ease;
}
.caret.open {
  transform: rotate(180deg);
}
.profile-dropdown {
  position: absolute;
  right: 0;
  top: calc(100% + 0.45rem);
  z-index: 40;
  width: min(280px, 84vw);
  border: 1px solid var(--border);
  border-radius: 16px;
  background: rgba(11, 18, 32, 0.96);
  backdrop-filter: blur(16px);
  padding: 0.7rem;
  display: grid;
  gap: 0.35rem;
  box-shadow: var(--shadow);
}
.profile-name {
  margin: 0;
  font-weight: 700;
}
.profile-role {
  margin: 0 0 0.25rem;
  color: var(--text-muted);
  font-size: 0.85rem;
}
.menu-item {
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  color: #fff;
  padding: 0.52rem 0.65rem;
  text-align: left;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.menu-item.active {
  border-color: rgba(96, 165, 250, 0.55);
  background: var(--primary-soft);
}
.menu-item .menu-dot {
  position: static;
  flex-shrink: 0;
  animation: none;
}
.menu-item .success-dot {
  background: var(--success);
  box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.18);
}
.menu-item.danger {
  background: var(--danger-bg);
  border-color: var(--danger-bg);
  margin-top: 0.2rem;
}
.app-toast {
  position: fixed;
  left: 50%;
  bottom: calc(1rem + env(safe-area-inset-bottom, 0));
  transform: translateX(-50%);
  z-index: 80;
  max-width: min(92vw, 420px);
  padding: 0.7rem 0.95rem;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.94);
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  color: var(--text);
  font-size: 0.88rem;
  text-align: center;
}
button {
  border: none;
  border-radius: 10px;
  background: var(--primary-strong);
  color: #fff;
  padding: 0.4rem 0.7rem;
}
.card {
  padding: 1rem;
  border: 1px solid var(--border);
  background: var(--surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow-sm);
}
.hint {
  color: var(--text-muted);
}
@media (min-width: 761px) {
  .menu-item.header-nav-item {
    display: none;
  }
}
@media (max-width: 760px) {
  .container {
    padding: 0.7rem 0.75rem 1rem;
  }
  .container.container--chat {
    padding: 0;
  }
  .topbar {
    grid-template-columns: auto 1fr auto;
    margin: -0.7rem -0.75rem 0.85rem;
    padding-left: 0.75rem;
    padding-right: 0.75rem;
  }
  .topbar-title {
    font-size: 0.95rem;
  }
  .profile-label {
    display: none;
  }
  .profile-btn {
    padding: 0.18rem;
    max-width: none;
  }
  .menu-item.tabbar-item {
    display: none;
  }
  .app-shell.has-tabbar .app-toast {
    bottom: calc(4.7rem + env(safe-area-inset-bottom, 0));
  }
  .app-shell.has-tabbar :deep(.bottom-nav) {
    flex: 0 0 auto;
    max-height: calc(4.25rem + env(safe-area-inset-bottom, 0px));
  }
  .app-shell.has-tabbar :deep(.composer) {
    padding-bottom: 0.55rem;
  }
}
</style>
