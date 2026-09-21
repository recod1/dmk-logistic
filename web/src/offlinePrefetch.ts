import {
  loadAuthSession,
  loadDriverRoutesCache,
  saveActiveRoute,
  saveDriverRoutesCache,
  saveRouteSnapshot
} from "./db";
import { isPointDone } from "./status";
import type { DriverRouteListItem, PointStatus, RouteDto } from "./types";

export const DRIVER_PREFETCH_SYNC_TAG = "dmk-driver-prefetch";

export type PrefetchAssignedRoutesResponse = {
  items: RouteDto[];
  active_route_id: string | null;
  logistics_contacts?: Array<{ name: string; phone: string }>;
};

export function resolveApiBase(stored?: string): string {
  const origin = typeof self !== "undefined" ? self.location.origin : "";
  const base = (stored || "/api").trim() || "/api";
  if (/^https?:\/\//i.test(base)) {
    return base.replace(/\/$/, "");
  }
  const path = base.startsWith("/") ? base : `/${base}`;
  return `${origin}${path}`.replace(/\/$/, "");
}

export function routeToListItem(route: RouteDto): DriverRouteListItem {
  const points = route.points || [];
  const active = points.find((point) => !isPointDone(point.status)) ?? points[points.length - 1] ?? null;
  return {
    id: route.id,
    status: route.status,
    number_auto: route.number_auto || "",
    temperature: route.temperature || "",
    dispatcher_contacts: route.dispatcher_contacts || "",
    registration_number: route.registration_number || "",
    trailer_number: route.trailer_number || "",
    created_at: route.created_at,
    accepted_at: route.accepted_at,
    points_count: points.length,
    active_point_id: active?.id ?? null,
    active_point_status: (active?.status as PointStatus | null) ?? null,
    active_point_place: (active?.place_point || "").trim() || null,
    active_point_name: (active?.point_name || "").trim() || null,
    active_point_type: active?.type_point || null,
    active_point_date: (active?.date_point || "").trim() || null,
    active_point_time: (active?.point_time || "").trim() || null
  };
}

export async function persistPrefetchPayload(payload: PrefetchAssignedRoutesResponse): Promise<void> {
  const items = Array.isArray(payload.items) ? payload.items : [];
  for (const route of items) {
    if (route?.id) {
      await saveRouteSnapshot(route);
    }
  }
  const cache = await loadDriverRoutesCache();
  await saveDriverRoutesCache({
    assigned: items.map(routeToListItem),
    history: cache?.history ?? [],
    active_route_id: payload.active_route_id
  });
  const active =
    items.find((route) => route.id === payload.active_route_id) ?? items[0] ?? null;
  await saveActiveRoute(active);
}

export async function prefetchAssignedRoutesFromSession(): Promise<boolean> {
  const session = await loadAuthSession();
  if (!session?.token || session.roleCode !== "driver") {
    return false;
  }
  const apiBase = resolveApiBase(session.apiBase);
  const ctrl = new AbortController();
  const timer = globalThis.setTimeout(() => ctrl.abort(), 25_000);
  try {
    const response = await fetch(`${apiBase}/v1/mobile/routes/prefetch`, {
      method: "GET",
      cache: "no-store",
      signal: ctrl.signal,
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${session.token}`
      }
    });
    if (!response.ok) {
      return false;
    }
    const data = (await response.json()) as PrefetchAssignedRoutesResponse;
    await persistPrefetchPayload(data);
    return true;
  } catch {
    return false;
  } finally {
    globalThis.clearTimeout(timer);
  }
}
