import Dexie, { type EntityTable } from "dexie";

import type { EventPayload, PointStatus, RouteDto } from "./types";

export interface ActiveRouteSnapshot {
  key: "active";
  route: RouteDto | null;
  updatedAt: string;
}

export interface OutboxEvent extends EventPayload {
  id?: number;
  device_id: string;
  created_at: string;
}

export interface PointStatusOverlay {
  id?: number;
  route_id: string;
  point_id: number;
  status: Exclude<PointStatus, "new">;
  occurred_at_client: string;
  updated_at: string;
}

const db = new Dexie("dmk-mobile-db") as Dexie & {
  activeRoute: EntityTable<ActiveRouteSnapshot, "key">;
  outbox: EntityTable<OutboxEvent, "id">;
  pointOverlay: EntityTable<PointStatusOverlay, "id">;
};

db.version(1).stores({
  activeRoute: "key",
  outbox: "++id,client_event_id,point_id,created_at"
});

db.version(2).stores({
  activeRoute: "key",
  outbox: "++id,client_event_id,point_id,created_at",
  pointOverlay: "++id,route_id,point_id,[route_id+point_id],updated_at"
});

db.version(3).stores({
  activeRoute: "key",
  outbox: "++id,client_event_id,point_id,created_at",
  pointOverlay: "++id,route_id,point_id,[route_id+point_id],updated_at"
});

function toPlainObject<T>(value: T): T {
  if (value === null || value === undefined) {
    return value;
  }
  if (typeof structuredClone === "function") {
    try {
      return structuredClone(value);
    } catch {
      // Vue reactive proxies may throw DataCloneError with structuredClone.
    }
  }
  return JSON.parse(JSON.stringify(value)) as T;
}

export async function saveActiveRoute(route: RouteDto | null): Promise<void> {
  await db.activeRoute.put({
    key: "active",
    route: toPlainObject(route),
    updatedAt: new Date().toISOString()
  });
}

export async function loadActiveRoute(): Promise<RouteDto | null> {
  const row = await db.activeRoute.get("active");
  return row?.route ?? null;
}

export async function addOutboxEvent(event: OutboxEvent): Promise<void> {
  await db.outbox.add(event);
}

export async function getOutboxEvents(deviceId: string): Promise<OutboxEvent[]> {
  return db.outbox.where("created_at").above("").filter((item) => item.device_id === deviceId).toArray();
}

export async function removeOutboxByClientEventIds(ids: string[]): Promise<void> {
  if (!ids.length) {
    return;
  }
  const rows = await db.outbox.where("client_event_id").anyOf(ids).toArray();
  if (!rows.length) {
    return;
  }
  await db.outbox.bulkDelete(rows.map((row) => row.id!).filter(Boolean));
}

export async function savePointOverlay(
  routeId: string,
  pointId: number,
  status: Exclude<PointStatus, "new">,
  occurredAtClient: string
): Promise<void> {
  const existing = await db.pointOverlay.where("[route_id+point_id]").equals([routeId, pointId]).first();
  const payload: PointStatusOverlay = {
    route_id: routeId,
    point_id: pointId,
    status,
    occurred_at_client: occurredAtClient,
    updated_at: new Date().toISOString()
  };
  if (existing?.id) {
    await db.pointOverlay.update(existing.id, payload);
    return;
  }
  await db.pointOverlay.add(payload);
}

export async function getPointOverlays(routeId: string): Promise<PointStatusOverlay[]> {
  return db.pointOverlay.where("route_id").equals(routeId).sortBy("updated_at");
}

export async function removePointOverlays(routeId: string, pointIds: number[]): Promise<void> {
  if (!pointIds.length) {
    return;
  }
  const rows = await db.pointOverlay.where("route_id").equals(routeId).toArray();
  const idsToDelete = rows.filter((row) => pointIds.includes(row.point_id)).map((row) => row.id!).filter(Boolean);
  if (!idsToDelete.length) {
    return;
  }
  await db.pointOverlay.bulkDelete(idsToDelete);
}

export default db;

