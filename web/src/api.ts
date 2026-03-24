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
  DriverOption,
  EventPayload,
  LoginResponse,
  RouteDto
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

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
  params?: { status?: string; driver_user_id?: number }
): Promise<AdminRoute[]> {
  const qs = new URLSearchParams();
  if (params?.status) {
    qs.set("status", params.status);
  }
  if (typeof params?.driver_user_id === "number") {
    qs.set("driver_user_id", String(params.driver_user_id));
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

export async function completeAdminRoute(token: string, routeId: string): Promise<AdminRoute> {
  return requestJson<AdminRoute>(`${API_BASE}/v1/admin/routes/${routeId}/complete`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`
    }
  });
}
