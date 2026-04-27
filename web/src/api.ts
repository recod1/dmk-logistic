import type {
  ActiveRouteResponse,
  AdminRoute,
  AdminRouteCreatePayload,
  AdminRoutesListResponse,
  AdminUser,
  AdminUserCreatePayload,
  AdminUserUpdatePayload,
  AdminUsersListResponse,
  BatchResponse,
  DriversResponse,
  DriverRouteListItem,
  DriverOption,
  EventPayload,
  LoginResponse,
  NotificationDto,
  PointDto,
  RouteDto
} from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  status: number;
  bodyText: string;
  detail: string | null;

  constructor(message: string, opts: { status: number; bodyText: string; detail?: string | null }) {
    super(message);
    this.name = "ApiError";
    this.status = opts.status;
    this.bodyText = opts.bodyText;
    this.detail = opts.detail ?? null;
  }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    const bodyText = await response.text();
    let detail: string | null = null;
    try {
      const parsed = JSON.parse(bodyText) as { detail?: unknown };
      if (typeof parsed?.detail === "string") {
        detail = parsed.detail;
      }
    } catch {
      // ignore non-json body
    }
    const message = detail || bodyText || `HTTP ${response.status}`;
    throw new ApiError(message, { status: response.status, bodyText, detail });
  }
  return response.json() as Promise<T>;
}

export async function login(loginValue: string, password: string): Promise<LoginResponse> {
  return requestJson<LoginResponse>(`${API_BASE}/auth/login`, {
    method: "POST",
    body: JSON.stringify({ login: loginValue, password })
  });
}

export async function getActiveRoute(token: string): Promise<RouteDto | null> {
  const data = await requestJson<ActiveRouteResponse>(`${API_BASE}/v1/mobile/routes/active`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return data.route;
}

export async function listDriverRoutes(
  token: string,
  scope: "assigned" | "history" | "all" = "assigned"
): Promise<{ items: DriverRouteListItem[]; active_route_id: string | null }> {
  const qs = new URLSearchParams();
  qs.set("scope", scope);
  return requestJson<{ items: DriverRouteListItem[]; active_route_id: string | null }>(
    `${API_BASE}/v1/mobile/routes?${qs.toString()}`,
    {
      headers: {
        Authorization: `Bearer ${token}`
      }
    }
  );
}

export async function getDriverRoute(token: string, routeId: string): Promise<RouteDto> {
  const data = await requestJson<{ route: RouteDto }>(`${API_BASE}/v1/mobile/routes/${routeId}`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return data.route;
}

export async function getPointTelemetry(
  token: string,
  pointId: number
): Promise<{ odometer: string | null; odometer_source: "wialon" | null }> {
  return requestJson<{ odometer: string | null; odometer_source: "wialon" | null }>(
    `${API_BASE}/v1/mobile/points/${pointId}/telemetry`,
    {
      headers: {
        Authorization: `Bearer ${token}`
      }
    }
  );
}

export async function acceptRoute(token: string, routeId: string): Promise<RouteDto> {
  const data = await requestJson<{ route: RouteDto }>(`${API_BASE}/v1/mobile/routes/${routeId}/accept`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return data.route;
}

export async function sendEventsBatch(
  token: string,
  deviceId: string,
  events: EventPayload[]
): Promise<BatchResponse> {
  return requestJson<BatchResponse>(`${API_BASE}/v1/mobile/events:batch`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({
      device_id: deviceId,
      events
    })
  });
}

export async function uploadPointDocuments(
  token: string,
  pointId: number,
  blobs: Blob[],
  opts?: { signal?: AbortSignal }
): Promise<{ file_ids: number[] }> {
  const fd = new FormData();
  blobs.forEach((b, i) => {
    fd.append("files", b, `document-${i}.jpg`);
  });
  const url = `${API_BASE}/v1/mobile/points/${pointId}/documents`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: fd,
    signal: opts?.signal
  });
  if (!response.ok) {
    const text = await response.text();
    if (response.status === 413) {
      throw new Error(
        "Сервер отклонил файл как слишком большой (413). Уже ужато на устройстве: попробуйте меньше фото за раз или обратитесь к администратору — на nginx нужен client_max_body_size."
      );
    }
    const trimmed = text.length > 280 ? `${text.slice(0, 280)}…` : text;
    throw new Error(trimmed || `HTTP ${response.status}`);
  }
  return response.json() as Promise<{ file_ids: number[] }>;
}

export async function fetchPointDocumentBlob(
  token: string,
  imageId: number,
  opts?: { thumbnail?: boolean; signal?: AbortSignal }
): Promise<Blob> {
  const qs = opts?.thumbnail ? "?thumb=1" : "";
  const url = `${API_BASE}/v1/point-documents/${imageId}/file${qs}`;
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`
    },
    signal: opts?.signal,
    cache: "default"
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.blob();
}

export async function listAdminUsers(token: string): Promise<AdminUser[]> {
  const data = await requestJson<AdminUsersListResponse>(`${API_BASE}/v1/admin/users`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return data.items;
}

export async function createAdminUser(token: string, payload: AdminUserCreatePayload): Promise<AdminUser> {
  return requestJson<AdminUser>(`${API_BASE}/v1/admin/users`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });
}

export async function deleteAdminUser(token: string, userId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/v1/admin/users/${userId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `HTTP ${response.status}`);
  }
}

export async function updateAdminUser(
  token: string,
  userId: number,
  payload: AdminUserUpdatePayload
): Promise<AdminUser> {
  return requestJson<AdminUser>(`${API_BASE}/v1/admin/users/${userId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });
}

export async function listRouteDrivers(token: string): Promise<DriverOption[]> {
  const data = await requestJson<DriversResponse>(`${API_BASE}/v1/admin/routes/drivers`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return data.items;
}

export async function listAdminRoutes(
  token: string,
  params?: {
    status?: string;
    driver_user_id?: number;
    route_id?: string;
    number_auto?: string;
    driver_query?: string;
  }
): Promise<AdminRoute[]> {
  const qs = new URLSearchParams();
  if (params?.status) {
    qs.set("status", params.status);
  }
  if (typeof params?.driver_user_id === "number") {
    qs.set("driver_user_id", String(params.driver_user_id));
  }
  if (params?.route_id) {
    qs.set("route_id", params.route_id);
  }
  if (params?.number_auto) {
    qs.set("number_auto", params.number_auto);
  }
  if (params?.driver_query) {
    qs.set("driver_query", params.driver_query);
  }
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  const data = await requestJson<AdminRoutesListResponse>(`${API_BASE}/v1/admin/routes${suffix}`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return data.items;
}

export async function getAdminRoute(token: string, routeId: string): Promise<AdminRoute> {
  return requestJson<AdminRoute>(`${API_BASE}/v1/admin/routes/${routeId}`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
}

export async function createAdminRoute(token: string, payload: AdminRouteCreatePayload): Promise<AdminRoute> {
  return requestJson<AdminRoute>(`${API_BASE}/v1/admin/routes`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });
}

export async function createAdminRouteFromOnec(
  token: string,
  payload: { raw_text: string; driver_user_id?: number | null; number_auto?: string; trailer_number?: string }
): Promise<AdminRoute> {
  return requestJson<AdminRoute>(`${API_BASE}/v1/admin/routes/onec`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });
}

export async function assignAdminRouteDriver(token: string, routeId: string, driverUserId: number): Promise<AdminRoute> {
  return requestJson<AdminRoute>(`${API_BASE}/v1/admin/routes/${routeId}/assign`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({ driver_user_id: driverUserId })
  });
}

export async function cancelAdminRoute(token: string, routeId: string): Promise<AdminRoute> {
  return requestJson<AdminRoute>(`${API_BASE}/v1/admin/routes/${routeId}/cancel`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
}

export async function deleteAdminRoute(token: string, routeId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/v1/admin/routes/${routeId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `HTTP ${response.status}`);
  }
}

export async function updateAdminRoute(
  token: string,
  routeId: string,
  payload: {
    number_auto?: string;
    temperature?: string;
    dispatcher_contacts?: string;
    registration_number?: string;
    trailer_number?: string;
    points?: AdminRouteCreatePayload["points"];
  }
): Promise<AdminRoute> {
  return requestJson<AdminRoute>(`${API_BASE}/v1/admin/routes/${routeId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });
}

export async function updateAdminRoutePoint(
  token: string,
  pointId: number,
  payload: Partial<{
    type_point: string;
    place_point: string;
    date_point: string;
    point_name: string;
    point_contacts: string;
    point_time: string;
    point_note: string;
  }>
): Promise<PointDto> {
  return requestJson<PointDto>(`${API_BASE}/v1/admin/routes/points/${pointId}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });
}

export async function deleteAdminRoutePoint(token: string, pointId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/v1/admin/routes/points/${pointId}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `HTTP ${response.status}`);
  }
}

export async function listNotifications(token: string, limit = 50): Promise<NotificationDto[]> {
  const qs = new URLSearchParams();
  qs.set("limit", String(limit));
  const data = await requestJson<{ items: NotificationDto[] }>(`${API_BASE}/v1/notifications?${qs.toString()}`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return data.items;
}

export async function getUnreadNotificationsCount(token: string): Promise<number> {
  const data = await requestJson<{ unread_count: number }>(`${API_BASE}/v1/notifications/unread-count`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return data.unread_count ?? 0;
}

export async function markNotificationRead(token: string, notificationId: number): Promise<NotificationDto> {
  const data = await requestJson<{ item: NotificationDto }>(`${API_BASE}/v1/notifications/${notificationId}/read`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return data.item;
}

export async function markAllNotificationsRead(token: string): Promise<number> {
  const data = await requestJson<{ updated: number }>(`${API_BASE}/v1/notifications/read-all`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return data.updated ?? 0;
}

export async function getVapidPublicKey(token: string): Promise<{ public_key: string | null }> {
  return requestJson<{ public_key: string | null }>(`${API_BASE}/v1/notifications/push/vapid-public-key`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
}

export async function subscribeWebPush(
  token: string,
  payload: { endpoint: string; keys: { p256dh: string; auth: string } }
): Promise<void> {
  await requestJson<{ ok: boolean }>(`${API_BASE}/v1/notifications/push/subscribe`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });
}

export async function clearWebPushSubscriptions(token: string): Promise<{ deleted: number }> {
  const data = await requestJson<{ ok: boolean; deleted: number }>(
    `${API_BASE}/v1/notifications/push/subscriptions:clear`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`
      }
    }
  );
  return { deleted: data.deleted ?? 0 };
}

export async function revertPointStatus(token: string, pointId: number): Promise<RouteDto> {
  const data = await requestJson<{ route: RouteDto }>(`${API_BASE}/v1/mobile/points/${pointId}/status:revert`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return data.route;
}

export function notificationsWebSocketUrl(token: string): string {
  const base = new URL(API_BASE, window.location.origin);
  const wsProtocol = base.protocol === "https:" ? "wss:" : "ws:";
  const normalizedApiPath = base.pathname.replace(/\/$/, "");
  const wsPath = normalizedApiPath.endsWith("/v1")
    ? `${normalizedApiPath}/notifications/ws`
    : `${normalizedApiPath}/v1/notifications/ws`;
  const wsUrl = new URL(`${wsProtocol}//${base.host}${wsPath}`);
  wsUrl.searchParams.set("token", token);
  return wsUrl.toString();
}

export async function listRouteChatMessages(
  token: string,
  routeId: string
): Promise<
  Array<{
    id: number;
    route_id: string;
    user_id: number;
    author_name: string;
    text: string;
    created_at: string;
    attachments?: Array<{ id: number; original_name: string; content_type: string; file_size: number }>;
  }>
> {
  const data = await requestJson<{
    items: Array<{
      id: number;
      route_id: string;
      user_id: number;
      author_name: string;
      text: string;
      created_at: string;
      attachments?: Array<{ id: number; original_name: string; content_type: string; file_size: number }>;
    }>;
  }>(`${API_BASE}/v1/chat/routes/${encodeURIComponent(routeId)}/messages`, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  return data.items;
}

export async function sendRouteChatMessage(
  token: string,
  routeId: string,
  payload: { text: string }
): Promise<{
  id: number;
  route_id: string;
  user_id: number;
  author_name: string;
  text: string;
  created_at: string;
  attachments?: Array<{ id: number; original_name: string; content_type: string; file_size: number }>;
}> {
  return requestJson<{
    id: number;
    route_id: string;
    user_id: number;
    author_name: string;
    text: string;
    created_at: string;
    attachments?: Array<{ id: number; original_name: string; content_type: string; file_size: number }>;
  }>(
    `${API_BASE}/v1/chat/routes/${encodeURIComponent(routeId)}/messages`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify(payload)
    }
  );
}

export async function uploadRouteChatAttachments(
  token: string,
  routeId: string,
  files: File[],
  opts?: { text?: string }
): Promise<{
  id: number;
  route_id: string;
  user_id: number;
  author_name: string;
  text: string;
  created_at: string;
  attachments?: Array<{ id: number; original_name: string; content_type: string; file_size: number }>;
}> {
  const fd = new FormData();
  fd.set("text", (opts?.text || "").trim());
  files.forEach((f) => fd.append("files", f, f.name));
  const url = `${API_BASE}/v1/chat/routes/${encodeURIComponent(routeId)}/attachments`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: fd
  });
  if (!response.ok) {
    const text = await response.text();
    const trimmed = text.length > 280 ? `${text.slice(0, 280)}…` : text;
    throw new Error(trimmed || `HTTP ${response.status}`);
  }
  return response.json() as Promise<{
    id: number;
    route_id: string;
    user_id: number;
    author_name: string;
    text: string;
    created_at: string;
    attachments?: Array<{ id: number; original_name: string; content_type: string; file_size: number }>;
  }>;
}

export async function fetchChatAttachmentBlob(token: string, attachmentId: number): Promise<Blob> {
  const url = `${API_BASE}/v1/chat/attachments/${attachmentId}/file`;
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.blob();
}

// --- Generic chats (rooms) ---

export async function listChatUsers(token: string): Promise<
  Array<{ id: number; login: string; full_name: string | null; role_code: string; role_label: string }>
> {
  const data = await requestJson<{ items: Array<{ id: number; login: string; full_name: string | null; role_code: string; role_label: string }> }>(
    `${API_BASE}/v1/chats/users`,
    {
      headers: { Authorization: `Bearer ${token}` }
    }
  );
  return data.items;
}

export async function postChatsBootstrap(token: string): Promise<void> {
  await requestJson<{ ok: boolean }>(`${API_BASE}/v1/chats/bootstrap`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({})
  });
}

export async function listLogisticDriverChatRooms(
  token: string
): Promise<
  Array<{
    driver: { id: number; full_name: string | null; login: string };
    room: { id: number; kind: "direct" | "group"; title: string; system_key?: string | null; unread_count?: number };
  }>
> {
  const data = await requestJson<{
    items: Array<{
      driver: { id: number; full_name: string | null; login: string };
      room: { id: number; kind: "direct" | "group"; title: string; system_key?: string | null; unread_count?: number };
    }>;
  }>(`${API_BASE}/v1/chats/logistic/driver-rooms`, { headers: { Authorization: `Bearer ${token}` } });
  return data.items;
}

export async function listAccountantDriverChatRooms(
  token: string
): Promise<
  Array<{
    driver: { id: number; full_name: string | null; login: string };
    room: { id: number; kind: "direct" | "group"; title: string; system_key?: string | null; unread_count?: number };
  }>
> {
  const data = await requestJson<{
    items: Array<{
      driver: { id: number; full_name: string | null; login: string };
      room: { id: number; kind: "direct" | "group"; title: string; system_key?: string | null; unread_count?: number };
    }>;
  }>(`${API_BASE}/v1/chats/accountant/driver-rooms`, { headers: { Authorization: `Bearer ${token}` } });
  return data.items;
}

export async function listChatRooms(
  token: string,
  kind?: "direct" | "group"
): Promise<Array<{ id: number; kind: "direct" | "group"; title: string; system_key?: string | null; unread_count?: number }>> {
  const qs = new URLSearchParams();
  if (kind) qs.set("kind", kind);
  const data = await requestJson<{ items: Array<{ id: number; kind: "direct" | "group"; title: string; system_key?: string | null; unread_count?: number }> }>(
    `${API_BASE}/v1/chats/rooms?${qs.toString()}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return data.items;
}

export async function openDirectChat(token: string, userId: number): Promise<{ room: { id: number; kind: "direct" | "group"; title: string } }> {
  return requestJson<{ room: { id: number; kind: "direct" | "group"; title: string } }>(`${API_BASE}/v1/chats/direct`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ user_id: userId })
  });
}

export async function listChatRoomMessages(
  token: string,
  roomId: number
): Promise<
  Array<{
    id: number;
    room_id: number;
    user_id: number;
    author_name: string;
    text: string;
    created_at: string;
    attachments?: Array<{ id: number; original_name: string; content_type: string; file_size: number }>;
  }>
> {
  const data = await requestJson<{ items: any[] }>(`${API_BASE}/v1/chats/rooms/${roomId}/messages`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return data.items;
}

export async function sendChatRoomMessage(
  token: string,
  roomId: number,
  payload: { text: string }
): Promise<any> {
  return requestJson<any>(`${API_BASE}/v1/chats/rooms/${roomId}/messages`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload)
  });
}

export async function uploadChatRoomAttachments(
  token: string,
  roomId: number,
  files: File[],
  opts?: { text?: string }
): Promise<any> {
  const fd = new FormData();
  fd.set("text", (opts?.text || "").trim());
  files.forEach((f) => fd.append("files", f, f.name));
  const url = `${API_BASE}/v1/chats/rooms/${roomId}/attachments`;
  const response = await fetch(url, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: fd });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

export async function fetchChatRoomAttachmentBlob(token: string, attachmentId: number): Promise<Blob> {
  const url = `${API_BASE}/v1/chats/attachments/${attachmentId}/file`;
  const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.blob();
}

export type AdminChatRoomRow = {
  id: number;
  kind: string;
  title: string;
  system_key: string | null;
  member_user_ids: number[];
  role_codes: string[];
  created_at: string;
};

export async function listAdminChatRooms(token: string): Promise<AdminChatRoomRow[]> {
  const data = await requestJson<{ items: AdminChatRoomRow[] }>(`${API_BASE}/v1/admin/chats/rooms`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return data.items;
}

export async function adminCreateChatRoom(
  token: string,
  payload: { title: string; system_key?: string | null; member_user_ids: number[]; role_codes: string[] }
): Promise<AdminChatRoomRow> {
  return requestJson<AdminChatRoomRow>(`${API_BASE}/v1/admin/chats/rooms`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      title: payload.title.trim(),
      system_key: payload.system_key?.trim() || null,
      member_user_ids: payload.member_user_ids,
      role_codes: payload.role_codes
    })
  });
}

export async function adminPatchChatRoom(token: string, roomId: number, title: string): Promise<AdminChatRoomRow> {
  return requestJson<AdminChatRoomRow>(`${API_BASE}/v1/admin/chats/rooms/${roomId}`, {
    method: "PATCH",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ title: title.trim() })
  });
}

export async function adminDeleteChatRoom(token: string, roomId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/v1/admin/chats/rooms/${roomId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
}

export async function adminBroadcastByRoles(
  token: string,
  payload: { title: string; message: string; role_codes: string[]; skip_self?: boolean }
): Promise<{ recipient_count: number }> {
  return requestJson<{ recipient_count: number }>(`${API_BASE}/v1/admin/chats/broadcast`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ ...payload, skip_self: payload.skip_self ?? true })
  });
}

// --- Salary (зарплата, как в боте) ---

export type SalaryRecord = {
  id: number;
  id_driver: string;
  date_salary: string;
  type_route: string;
  sum_status: number;
  sum_daily: number;
  load_2_trips: number;
  calc_shuttle: number;
  sum_load_unload: number;
  sum_curtain: number;
  sum_return: number;
  sum_add_shuttle: number;
  sum_add_point: number;
  sum_gas_station: number;
  pallets_hyper: number;
  pallets_metro: number;
  pallets_ashan: number;
  rate_3km: number;
  rate_3_5km: number;
  rate_5km: number;
  rate_10km: number;
  rate_12km: number;
  rate_12_5km: number;
  mileage: number;
  sum_cell_compensation: number;
  experience: number;
  percent_10: number;
  sum_bonus: number;
  withhold: number;
  compensation: number;
  dr: number;
  sum_without_daily_dr_bonus_exp: number;
  sum_without_daily_dr_bonus: number;
  total: number;
  load_address: string;
  unload_address: string;
  transport: string;
  trailer_number: string;
  route_number: string;
  status_driver: string;
  comment_driver: string;
  created_at: string;
};

export async function lookupSalaryDrivers(
  token: string,
  q: string
): Promise<Array<{ id: number; login: string; full_name: string | null; legacy_tg_id: string | null }>> {
  const qs = new URLSearchParams({ q });
  const data = await requestJson<{ items: Array<{ id: number; login: string; full_name: string | null; legacy_tg_id: string | null }> }>(
    `${API_BASE}/v1/salary/lookup/drivers?${qs.toString()}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return data.items;
}

export async function createSalaryManual(token: string, payload: { driver_user_id: number; salary_line: string }): Promise<SalaryRecord> {
  return requestJson<SalaryRecord>(`${API_BASE}/v1/salary`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload)
  });
}

export async function listMySalaries(token: string, dateFrom?: string, dateTo?: string): Promise<SalaryRecord[]> {
  const qs = new URLSearchParams();
  if (dateFrom) qs.set("date_from", dateFrom);
  if (dateTo) qs.set("date_to", dateTo);
  const suf = qs.toString() ? `?${qs.toString()}` : "";
  const data = await requestJson<{ items: SalaryRecord[] }>(`${API_BASE}/v1/salary/mine${suf}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return data.items;
}

export async function fetchMySalaryCsvBlob(token: string, dateFrom: string, dateTo: string): Promise<Blob> {
  const qs = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  const url = `${API_BASE}/v1/salary/mine/export.csv?${qs.toString()}`;
  const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.blob();
}

export async function listSalariesForDriver(
  token: string,
  driverUserId: number,
  dateFrom?: string,
  dateTo?: string
): Promise<{ items: SalaryRecord[]; driver: { id: number; full_name: string | null; login: string } }> {
  const qs = new URLSearchParams();
  if (dateFrom) qs.set("date_from", dateFrom);
  if (dateTo) qs.set("date_to", dateTo);
  const suf = qs.toString() ? `?${qs.toString()}` : "";
  return requestJson<{ items: SalaryRecord[]; driver: { id: number; full_name: string | null; login: string } }>(
    `${API_BASE}/v1/salary/for-driver/${driverUserId}${suf}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
}

export async function getSalary(token: string, salaryId: number): Promise<SalaryRecord> {
  return requestJson<SalaryRecord>(`${API_BASE}/v1/salary/${salaryId}`, {
    headers: { Authorization: `Bearer ${token}` }
  });
}

export async function confirmSalary(token: string, salaryId: number): Promise<SalaryRecord> {
  return requestJson<SalaryRecord>(`${API_BASE}/v1/salary/${salaryId}/confirm`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({})
  });
}

export async function commentSalary(token: string, salaryId: number, text: string): Promise<SalaryRecord> {
  return requestJson<SalaryRecord>(`${API_BASE}/v1/salary/${salaryId}/comment`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ text })
  });
}

export async function listSalaryChatMessages(token: string, salaryId: number): Promise<any[]> {
  const data = await requestJson<{ items: any[] }>(`${API_BASE}/v1/salary/${salaryId}/chat/messages`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return data.items;
}

export async function sendSalaryChatMessage(token: string, salaryId: number, payload: { text: string }): Promise<any> {
  return requestJson<any>(`${API_BASE}/v1/salary/${salaryId}/chat/messages`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload)
  });
}

export async function uploadSalaryChatAttachments(
  token: string,
  salaryId: number,
  files: File[],
  opts?: { text?: string }
): Promise<any> {
  const fd = new FormData();
  fd.set("text", (opts?.text || "").trim());
  files.forEach((f) => fd.append("files", f, f.name));
  const url = `${API_BASE}/v1/salary/${salaryId}/chat/attachments`;
  const response = await fetch(url, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: fd });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

export async function fetchSalaryChatAttachmentBlob(token: string, attachmentId: number): Promise<Blob> {
  const url = `${API_BASE}/v1/salary/chat/attachments/${attachmentId}/file`;
  const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.blob();
}

export function chatWebSocketUrl(token: string): string {
  const base = new URL(API_BASE, window.location.origin);
  const wsProtocol = base.protocol === "https:" ? "wss:" : "ws:";
  const normalizedApiPath = base.pathname.replace(/\/$/, "");
  const wsPath = normalizedApiPath.endsWith("/v1") ? `${normalizedApiPath}/chat/ws` : `${normalizedApiPath}/v1/chat/ws`;
  const wsUrl = new URL(`${wsProtocol}//${base.host}${wsPath}`);
  wsUrl.searchParams.set("token", token);
  return wsUrl.toString();
}

export async function getChatUnreadSummary(
  token: string,
  routeIds: string[]
): Promise<Array<{ route_id: string; unread_count: number }>> {
  const data = await requestJson<{ items: Array<{ route_id: string; unread_count: number }> }>(`${API_BASE}/v1/chat/unread-summary`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    },
    body: JSON.stringify({ route_ids: routeIds })
  });
  return data.items;
}
