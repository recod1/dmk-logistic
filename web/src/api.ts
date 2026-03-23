import type { ActiveRouteResponse, BatchResponse, EventPayload, LoginResponse, RouteDto } from "./types";

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

