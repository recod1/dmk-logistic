<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watchEffect } from "vue";
import type { RoleCode } from "./roles";

import AdminRouteDetailsView from "./components/AdminRouteDetailsView.vue";
import AdminRoutesView from "./components/AdminRoutesView.vue";
import AdminUsersView from "./components/AdminUsersView.vue";
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
import NotificationsView from "./components/NotificationsView.vue";
import StatusConfirmDialog from "./components/StatusConfirmDialog.vue";
import {
  ApiError,
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
  listMySalaries,
  fetchMySalaryCsvBlob,
  lookupSalaryDrivers,
  createSalaryManual,
  listSalariesForDriver,
  getSalary,
  confirmSalary,
  commentSalary,
  listSalaryChatMessages,
  sendSalaryChatMessage,
  uploadSalaryChatAttachments,
  fetchSalaryChatAttachmentBlob,
  listAdminRoutes,
  listAdminUsers,
  listDriverRoutes,
  listNotifications,
  listRouteDrivers,
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
  updateAdminUser,
  uploadPointDocuments
} from "./api";
import {
  addOutboxEvent,
  getOutboxEvents,
  getPendingDocBlob,
  getPointOverlays,
  loadActiveRoute,
  removeOutboxByClientEventIds,
  removePendingDocBlobs,
  removePointOverlays,
  saveActiveRoute,
  savePendingDocBlob,
  savePointOverlay,
  updateOutboxEventByClientId
} from "./db";
import { fromDatetimeLocalToIso, toDatetimeLocalValue } from "./datetimeLocal";
import { prepareDocumentImageBlobs, prepareDocumentImageFiles } from "./imageUploadPrep";
import { isAccountantRole, isAdminRole, isLogisticRole, isRouteManagerRole } from "./roles";
import { isPointDone, nextStatus, nextStatusLabel } from "./status";
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
  | "chat"
  | "chat_room"
  | "chats"
  | "notifications"
  | "admin_users"
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

const chatRouteId = ref<string | null>(null);
const chatMessages = ref<Array<{ id: number; route_id: string; user_id: number; author_name: string; text: string; created_at: string }>>([]);
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
} | null>(null);
const docsUpload = ref<{
  pointId: number;
  occurredAtIso: string;
  timeSource: "device" | "manual";
  odometer: string;
  odometer_source: "manual" | "wialon" | null;
} | null>(null);
const docsUploading = ref(false);
let docsUploadAbort: AbortController | null = null;

let syncIntervalId: number | null = null;
let notificationsWs: WebSocket | null = null;
let notificationsWsReconnectTimer: number | null = null;
let notificationsPingInterval: number | null = null;
let notificationsPollInterval: number | null = null;

let chatWs: WebSocket | null = null;
let chatWsReconnectTimer: number | null = null;
let chatPingInterval: number | null = null;
let chatPollInterval: number | null = null;
let roomChatPollInterval: number | null = null;
let salaryChatPollInterval: number | null = null;

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

const isAuthed = computed(() => Boolean(authToken.value));
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
  if (chatsRoomsForDisplay.value.some((r) => (r.unread_count ?? 0) > 0)) return true;
  if (logisticDriverChatRoomsDisplay.value.some((row) => (row.room.unread_count ?? 0) > 0)) return true;
  if (accountantDriverChatRoomsDisplay.value.some((row) => (row.room.unread_count ?? 0) > 0)) return true;
  return false;
});

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
    const base = currentPageTitle.value;
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
  return (
    selectedDriverRoute.value.status === "new" && selectedDriverRoute.value.id === driverActiveRouteId.value
  );
});

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
  if (currentSection.value === "chats") {
    return "ДМК - Чаты";
  }
  if (currentSection.value === "chat_room") {
    return "ДМК - Чаты";
  }
  if (currentSection.value === "driver_salary" || currentSection.value === "salary_accounting") {
    return "ДМК - Зарплата";
  }
  if (currentSection.value === "salary_detail") {
    return "ДМК - Расчёт";
  }
  if (currentSection.value === "salary_chat") {
    return "ДМК - Чат расчёта";
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
      { section: "chats", label: "Чаты" },
      { section: "salary_accounting", label: "Зарплата" },
      { section: "admin_users", label: "Пользователи" }
    ];
  }
  if (isRouteManagerRole(authUser.value.role_code)) {
    const items: Array<{ section: AppSection; label: string }> = [
      { section: "admin_routes", label: "Рейсы" },
      { section: "chats", label: "Чаты" }
    ];
    if (isAccountantRole(authUser.value.role_code)) {
      items.push({ section: "salary_accounting", label: "Зарплата" });
    }
    return items;
  }
  return [
    { section: "driver_home", label: "Главная" },
    { section: "driver_routes", label: "Рейсы" },
    { section: "chats", label: "Чаты" },
    { section: "driver_salary", label: "Зарплата" }
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

function stopNotificationsPolling(): void {
  if (notificationsPollInterval !== null) {
    window.clearInterval(notificationsPollInterval);
    notificationsPollInterval = null;
  }
}

function startNotificationsPolling(): void {
  stopNotificationsPolling();
  // Fallback for environments where WS delivery is unreliable:
  // periodically refresh notifications while the app is running.
  notificationsPollInterval = window.setInterval(() => {
    if (!authToken.value) {
      stopNotificationsPolling();
      return;
    }
    void refreshNotifications();
  }, 5000);
}

function closeChatSocket(): void {
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
    void refreshChatRoom();
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
    void refreshSalaryChat();
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
    void refreshChat();
  }, 2500);
}

function scheduleChatReconnect(): void {
  if (!authToken.value) {
    return;
  }
  if (chatWsReconnectTimer !== null) {
    return;
  }
  chatWsReconnectTimer = window.setTimeout(() => {
    chatWsReconnectTimer = null;
    connectChatSocket();
  }, 2500);
}

function connectChatSocket(): void {
  if (!authToken.value) {
    return;
  }
  closeChatSocket();
  try {
    const ws = new WebSocket(chatWebSocketUrl(authToken.value));
    chatWs = ws;
    ws.onopen = () => {
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
          };
          if (chatRouteId.value && item.route_id === chatRouteId.value) {
            const exists = chatMessages.value.some((m) => m.id === item.id);
            if (!exists) {
              chatMessages.value = [...chatMessages.value, item];
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
          };
          if (currentSection.value === "chat_room" && chatRoomId.value && item.room_id === chatRoomId.value) {
            const exists = chatRoomMessages.value.some((m) => m.id === item.id);
            if (!exists) {
              chatRoomMessages.value = [...chatRoomMessages.value, item];
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
          };
          if (
            currentSection.value === "salary_chat" &&
            salaryChatSalaryId.value &&
            item.salary_id === salaryChatSalaryId.value
          ) {
            const exists = salaryChatMessages.value.some((m) => m.id === item.id);
            if (!exists) {
              salaryChatMessages.value = [...salaryChatMessages.value, item];
            }
          }
        }
      } catch {
        // ignore
      }
    };
    ws.onclose = () => {
      chatWs = null;
      scheduleChatReconnect();
    };
    ws.onerror = () => {
      chatWs = null;
      scheduleChatReconnect();
    };
  } catch {
    scheduleChatReconnect();
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
      if (useLegacyBrowserNotification.value) {
        showBrowserPushNotification(item);
      }
    }
    if (!item.is_read) {
      unreadNotificationsCount.value += 1;
    }
  }

  if (syncDriverState && item.event_type === "route_deleted" && isDriver.value) {
    // Only force-close the details view when we know which route was deleted
    // and it matches the currently opened route. Some backends may emit route_deleted
    // without route_id — in that case just refresh driver data without navigation.
    if (item.route_id && selectedDriverRoute.value?.id === item.route_id) {
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
  driverRoutesLoading.value = true;
  try {
    const assigned = await listDriverRoutes(authToken.value, "assigned");
    const history = await listDriverRoutes(authToken.value, "history");
    driverAssignedRoutes.value = assigned.items;
    driverHistoryRoutes.value = history.items;
    driverActiveRouteId.value = assigned.active_route_id ?? null;

    try {
      const routeIds = [...assigned.items.map((x) => x.id), ...history.items.map((x) => x.id)];
      const unread = await getChatUnreadSummary(authToken.value, routeIds);
      const map: Record<string, number> = {};
      unread.forEach((row) => {
        map[row.route_id] = row.unread_count;
      });
      chatUnreadByRoute.value = map;
    } catch {
      // ignore chat unread errors
    }

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
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы загрузить рейсы." })) {
      return;
    }
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
    if (handleAuthError(error)) {
      return;
    }
    syncMessage.value = `Режим офлайн: ${(error as Error).message}`;
  }
}

function onVisibilityChange(): void {
  if (typeof document === "undefined" || document.visibilityState !== "visible") {
    return;
  }
  if (!authToken.value) {
    return;
  }
  void refreshNotifications();
  if (isDriver.value) {
    void refreshDriverData();
  } else if (isRouteManager.value) {
    void refreshAdminRoutes(routeFilters.value);
  }
}

function onOnline(): void {
  syncMessage.value = "Онлайн: синхронизация возобновлена";
  if (authToken.value) {
    connectNotificationsSocket();
    void refreshNotifications();
    void refreshWebPushSubscriptionState();
    startNotificationsPolling();
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
  stopNotificationsPolling();
}

async function syncOutboxInBackground(): Promise<void> {
  if (!authToken.value || !isDriver.value) {
    return;
  }
  if (!navigator.onLine || syncing.value) {
    return;
  }
  const deviceId = getDeviceId();
  let outbox = await getOutboxEvents(deviceId);
  if (!outbox.length) {
    return;
  }

  syncing.value = true;
  try {
    outbox = outbox.sort((a, b) => a.created_at.localeCompare(b.created_at));

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
        const { file_ids } = await uploadPointDocuments(authToken.value, ev.point_id, prepared);
        await updateOutboxEventByClientId(ev.client_event_id, {
          document_file_ids: file_ids,
          document_local_keys: []
        });
        await removePendingDocBlobs(keys);
      } catch (error) {
        console.debug("[pwa-sync] point documents upload failed", error);
      }
    }

    outbox = (await getOutboxEvents(deviceId)).sort((a, b) => a.created_at.localeCompare(b.created_at));
    const docsBlocked = outbox.some(
      (ev) => ev.to_status === "docs" && ev.document_local_keys?.length && !ev.document_file_ids?.length
    );
    if (docsBlocked) {
      return;
    }

    const events: EventPayload[] = outbox.map((event) => {
      const payload: EventPayload = {
        client_event_id: event.client_event_id,
        occurred_at_client: event.occurred_at_client,
        point_id: event.point_id,
        to_status: event.to_status,
        odometer: event.odometer ?? null,
        odometer_source: event.odometer_source ?? null,
        coordinates: null
      };
      if (event.document_file_ids?.length) {
        payload.document_file_ids = event.document_file_ids;
      }
      return payload;
    });
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

    try {
      const routeIds = adminRoutes.value.map((x) => x.id);
      const unread = await getChatUnreadSummary(authToken.value, routeIds);
      const map: Record<string, number> = {};
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
        currentSection.value = "admin_routes";
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
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы загрузить уведомления." })) {
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
      currentSection.value = "salary_chat";
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
  connectNotificationsSocket();
  connectChatSocket();
  startNotificationsPolling();
  void refreshWebPushSubscriptionState();
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
  if (section === "chats") {
    currentSection.value = "chats";
    void refreshChatsHub();
    return;
  }
  if (section === "driver_salary" && authUser.value.role_code === "driver") {
    void openDriverSalarySection();
    return;
  }
  if (section === "salary_accounting" && (isAdmin.value || isAccountant.value)) {
    currentSection.value = "salary_accounting";
    salaryAccountantDrivers.value = [];
    salaryAccountantItems.value = [];
    salarySelectedDriver.value = null;
    salaryError.value = "";
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
  const pointIndex = base.points.findIndex((p) => p.id === pointId);
  const to = nextStatus(current.status);
  const showOdometer =
    (current.status === "new" && pointIndex === 0 && to === "process") ||
    (current.status === "process" && to === "registration") ||
    (current.status === "load" && pointIndex === base.points.length - 1 && to === "docs");
  const initial = toDatetimeLocalValue(new Date());
  statusConfirm.value = {
    pointId,
    nextLabel: nextStatusLabel(current.status) || "",
    datetimeLocal: initial,
    initialDatetimeLocal: initial,
    showOdometer,
    odometer: "",
    initialOdometer: "",
    odometerPrefillSource: null
  };
  if (showOdometer && navigator.onLine && authToken.value) {
    void (async () => {
      try {
        const tel = await getPointTelemetry(authToken.value, pointId);
        if (!statusConfirm.value || statusConfirm.value.pointId !== pointId) return;
        if (tel.odometer) {
          statusConfirm.value.odometer = tel.odometer;
          statusConfirm.value.initialOdometer = tel.odometer;
          statusConfirm.value.odometerPrefillSource = tel.odometer_source;
        }
      } catch {
        // ignore telemetry prefetch errors; driver can enter manually
      }
    })();
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
  if (!ctx || !route.value || !authToken.value || !files.length) {
    return;
  }
  docsUploading.value = true;
  docsUploadAbort = new AbortController();
  try {
    const blobs = await prepareDocumentImageFiles(files);
    if (navigator.onLine) {
      const { file_ids } = await uploadPointDocuments(authToken.value, ctx.pointId, blobs, { signal: docsUploadAbort.signal });
      docsUpload.value = null;
      await markPointNext(
        ctx.pointId,
        ctx.occurredAtIso,
        { fileIds: file_ids },
        { timeSource: ctx.timeSource, odometer: ctx.odometer, odometer_source: ctx.odometer_source }
      );
    } else {
      const localKeys: string[] = [];
      for (const blob of blobs) {
        const key = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
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
      docsUpload.value = null;
      await markPointNext(
        ctx.pointId,
        ctx.occurredAtIso,
        { localKeys },
        { timeSource: ctx.timeSource, odometer: ctx.odometer, odometer_source: ctx.odometer_source }
      );
    }
  } catch (error) {
    const e = error as { name?: string; message?: string };
    if (e?.name === "AbortError") {
      syncMessage.value = "Загрузка документов отменена";
    } else {
      syncMessage.value = (error as Error).message;
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

async function doRevertPoint(pointId: number): Promise<void> {
  if (!authToken.value || !isDriver.value) {
    return;
  }
  if (!navigator.onLine) {
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
  void refreshWebPushSubscriptionState();
  void refreshNotifications();
}

async function openChatForRoute(routeId: string): Promise<void> {
  if (!authToken.value) {
    return;
  }
  chatRouteId.value = routeId;
  currentSection.value = "chat";
  await refreshChat();
  if (chatUnreadByRoute.value[routeId]) {
    chatUnreadByRoute.value = { ...chatUnreadByRoute.value, [routeId]: 0 };
  }
  startChatPolling();
}

async function refreshChat(): Promise<void> {
  if (!authToken.value || !chatRouteId.value) {
    return;
  }
  chatLoading.value = true;
  chatError.value = "";
  try {
    chatMessages.value = await listRouteChatMessages(authToken.value, chatRouteId.value);
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы открыть чат." })) {
      return;
    }
    chatError.value = (error as Error).message;
  } finally {
    chatLoading.value = false;
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
  currentSection.value = "chat_room";
  await refreshChatRoom();
  startRoomChatPolling();
}

function closeChatRoomToHub(): void {
  stopRoomChatPolling();
  currentSection.value = "chats";
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
  currentSection.value = "driver_salary";
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
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `расчеты_${dateFrom}_${dateTo}.csv`.replace(/\./g, "-");
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.setTimeout(() => URL.revokeObjectURL(url), 15_000);
    syncMessage.value = "CSV сохранён";
  } catch (error) {
    salaryError.value = (error as Error).message;
  }
}

function openSalaryDetail(row: SalaryRecord, backSection: AppSection): void {
  salaryCurrentRecord.value = row;
  salaryDetailBackSection.value = backSection;
  currentSection.value = "salary_detail";
}

function closeSalaryDetail(): void {
  currentSection.value = salaryDetailBackSection.value;
}

async function reloadSalaryCurrent(): Promise<void> {
  if (!authToken.value || !salaryCurrentRecord.value) return;
  try {
    salaryCurrentRecord.value = await getSalary(authToken.value, salaryCurrentRecord.value.id);
    if (salaryDetailBackSection.value === "driver_salary") {
      await refreshDriverSalaryList(salaryDriverFilterFrom.value, salaryDriverFilterTo.value);
    } else if (salarySelectedDriver.value) {
      await refreshAccountantSalaryList();
    }
  } catch {
    // ignore
  }
}

async function doSalaryConfirm(): Promise<void> {
  if (!authToken.value || !salaryCurrentRecord.value) return;
  salaryDetailBusy.value = true;
  try {
    salaryCurrentRecord.value = await confirmSalary(authToken.value, salaryCurrentRecord.value.id);
    syncMessage.value = "Расчёт подтверждён";
    await reloadSalaryCurrent();
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
    salaryCurrentRecord.value = await commentSalary(authToken.value, salaryCurrentRecord.value.id, text);
    syncMessage.value = "Комментарий отправлен";
    await reloadSalaryCurrent();
  } catch (error) {
    syncMessage.value = (error as Error).message;
  } finally {
    salaryDetailBusy.value = false;
  }
}

async function openSalaryChatFromDetail(): Promise<void> {
  if (!salaryCurrentRecord.value || !authToken.value) return;
  salaryChatSalaryId.value = salaryCurrentRecord.value.id;
  currentSection.value = "salary_chat";
  await refreshSalaryChat();
  startSalaryChatPolling();
}

function closeSalaryChat(): void {
  stopSalaryChatPolling();
  currentSection.value = "salary_detail";
}

async function refreshSalaryChat(): Promise<void> {
  if (!authToken.value || !salaryChatSalaryId.value) return;
  salaryChatLoading.value = true;
  salaryChatError.value = "";
  try {
    salaryChatMessages.value = await listSalaryChatMessages(authToken.value, salaryChatSalaryId.value);
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново." })) {
      return;
    }
    salaryChatError.value = (error as Error).message;
  } finally {
    salaryChatLoading.value = false;
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

async function refreshChatRoom(): Promise<void> {
  if (!authToken.value || !chatRoomId.value) return;
  chatRoomLoading.value = true;
  chatRoomError.value = "";
  try {
    chatRoomMessages.value = await listChatRoomMessages(authToken.value, chatRoomId.value);
  } catch (error) {
    if (handleAuthError(error, { userMessage: "Сессия истекла. Войдите заново, чтобы открыть чат." })) {
      return;
    }
    chatRoomError.value = (error as Error).message;
  } finally {
    chatRoomLoading.value = false;
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
  openStatusConfirm(activePoint.id);
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
  document.addEventListener("visibilitychange", onVisibilityChange);
});

onUnmounted(() => {
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
  document.removeEventListener("visibilitychange", onVisibilityChange);
});
</script>

<template>
  <main
    class="container"
    :class="{
      'container--chat': isAuthed && (currentSection === 'chat' || currentSection === 'chat_room' || currentSection === 'salary_chat')
    }"
  >
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
              <span v-if="item.section === 'chats' && hasUnreadGenericChats" class="notif-dot menu-dot" />
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
        :unread-by-route="chatUnreadByRoute"
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
        :loading="routesLoading"
        :auth-token="authToken"
        :unread-chat-count="chatUnreadByRoute[selectedAdminRoute.id] ?? 0"
        @back="openAdminRouteList"
        @assign-driver="doAssignAdminRoute"
        @cancel-route="doCancelAdminRoute"
        @delete-route="doDeleteAdminRoute"
        @update-route="doUpdateAdminRoute"
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
        :can-accept-route="canAcceptSelectedDriverRoute"
        :unread-chat-count="chatUnreadByRoute[selectedDriverRoute.id] ?? 0"
        @back="openDriverRoutes"
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
        @back="() => (currentSection = isDriver ? 'driver_route_details' : 'admin_route_details')"
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
        @back="openDriverHome"
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
        @back="() => (currentSection = 'admin_routes')"
        @search="(q) => void searchSalaryDriversForAccounting(q)"
        @pick-driver="(id) => void pickSalaryAccountantDriver(id)"
        @refresh-list="(a, b) => void refreshAccountantSalaryList(a, b)"
        @create="(p) => void createSalaryFromAccountant(p)"
        @select="(r) => openSalaryDetail(r, 'salary_accounting')"
      />
    </section>

    <section v-else-if="currentSection === 'salary_detail' && salaryCurrentRecord">
      <SalaryDetailView
        :record="salaryCurrentRecord"
        :is-driver="isDriver"
        :busy="salaryDetailBusy"
        @back="closeSalaryDetail"
        @confirm="doSalaryConfirm"
        @comment="doSalaryComment"
        @open-chat="openSalaryChatFromDetail"
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
        @back="() => (currentSection = isDriver ? 'driver_home' : isRouteManager ? 'admin_routes' : 'driver_home')"
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

    <StatusConfirmDialog
      v-if="isAuthed && statusConfirm"
      :open="true"
      :next-status-label="statusConfirm.nextLabel"
      :datetime-local="statusConfirm.datetimeLocal"
      :show-odometer="statusConfirm.showOdometer"
      :odometer="statusConfirm.odometer"
      :initial-odometer="statusConfirm.initialOdometer"
      :odometer-prefill-source="statusConfirm.odometerPrefillSource"
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
  </main>
</template>

<style scoped>
.container {
  max-width: 1100px;
  margin: 0 auto;
  padding: 1rem;
  color: #f9fafb;
  font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
  overflow-x: hidden;
}
.container.container--chat {
  max-width: none;
  margin: 0;
  width: 100%;
  min-height: 100dvh;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  padding: 0;
  box-sizing: border-box;
}
.container.container--chat > .topbar {
  flex-shrink: 0;
  margin-bottom: 0;
  padding: 0.85rem 1rem 0.65rem;
}
.container.container--chat > section {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.menu-item .menu-dot {
  position: static;
  flex-shrink: 0;
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
