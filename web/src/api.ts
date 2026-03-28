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

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `HTTP ${response.status}`);
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
  blobs: Blob[]
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
    body: fd
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json() as Promise<{ file_ids: number[] }>;
}

export async function fetchPointDocumentBlob(
  token: string,
  imageId: number
): Promise<Blob> {
  const url = `${API_BASE}/v1/point-documents/${imageId}/file`;
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
